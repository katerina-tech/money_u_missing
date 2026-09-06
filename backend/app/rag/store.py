"""The knowledge store: ingestion and retrieval over the German corpus.

Retrieval is hybrid where dense embeddings are configured and purely lexical
otherwise, fused by reciprocal rank. On Postgres with pgvector the dense half
runs as an ANN query in the database; on SQLite it is a numpy scan over the
corpus, which at this size is faster than the round trip would be.

The metadata travelling with every chunk - source name, URL, topic, effective
year, retrieval date - is not decoration. It is what makes
:class:`~app.domain.legal.Citation` constructible, and a citation is what the
answer layer refuses to answer without.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.base import pgvector_available
from app.db.models import KnowledgeChunkRow, KnowledgeDocumentRow
from app.domain.enums import LegalCategory
from app.domain.legal import KnowledgeChunk
from app.rag.chunking import chunk_markdown
from app.rag.embeddings import (
    BM25Index,
    Embedder,
    build_embedder,
    cosine_similarity,
    reciprocal_rank_fusion,
)

logger = logging.getLogger(__name__)


class CorpusStats(TypedDict):
    """Reported by the capability endpoint, so it is a typed contract.

    A plain ``dict[str, object]`` here meant the API layer had to cast every
    field, which is exactly where a wrong key becomes a runtime error nobody
    catches until a reviewer loads the page.
    """

    documents: int
    chunks: int
    embedded_chunks: int
    retrieval_mode: str
    embedder: str
    pgvector: bool


def _checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


class KnowledgeStore:
    """Ingests documents and retrieves passages with their provenance."""

    def __init__(self, settings: Settings | None = None, embedder: Embedder | None = None) -> None:
        self._settings = settings or get_settings()
        self._embedder = embedder if embedder is not None else build_embedder(self._settings)
        self._bm25 = BM25Index()
        self._loaded = False

    # ------------------------------------------------------------ ingestion
    def ingest_document(
        self,
        session: Session,
        *,
        document_id: str,
        title: str,
        source_name: str,
        source_url: str | None,
        topic: LegalCategory,
        text: str,
        effective_year: int | None = None,
        retrieved_at: datetime | None = None,
    ) -> int:
        """Ingest or re-ingest one document. Returns the number of chunks written.

        Idempotent by checksum: re-running the seed does not re-embed unchanged
        documents, which matters when embedding costs money.
        """
        checksum = _checksum(text)
        existing = session.get(KnowledgeDocumentRow, document_id)
        if existing is not None and existing.checksum == checksum:
            return 0

        if existing is not None:
            session.query(KnowledgeChunkRow).filter_by(document_id=document_id).delete()
            session.delete(existing)
            session.flush()

        stamp = retrieved_at or datetime.now(UTC)
        session.add(
            KnowledgeDocumentRow(
                id=document_id,
                title=title,
                source_name=source_name,
                source_url=source_url,
                jurisdiction="DE",
                topic=topic.value,
                effective_year=effective_year,
                retrieved_at=stamp,
                content_available=True,
                checksum=checksum,
            )
        )
        # Flush before adding chunks. There is no ORM relationship between the
        # document and its chunks - the metadata is denormalised onto each chunk
        # so a citation needs no join - so SQLAlchemy cannot infer the insert
        # ordering, and an autoflush triggered mid-loop would try to write a
        # child before its parent exists.
        session.flush()

        chunks = chunk_markdown(
            text, size=self._settings.chunk_size, overlap=self._settings.chunk_overlap
        )
        vectors: list[list[float]] | None = None
        if self._embedder.available and chunks:
            try:
                vectors = self._embedder.embed([c.text for c in chunks])
            except Exception:  # embedding is an upgrade, not a requirement
                logger.warning("embedding failed; storing chunks without vectors", exc_info=True)
                vectors = None

        for index, chunk in enumerate(chunks):
            session.add(
                KnowledgeChunkRow(
                    id=f"{document_id}:{chunk.ordinal}",
                    document_id=document_id,
                    ordinal=chunk.ordinal,
                    text=chunk.text,
                    source_name=source_name,
                    source_url=source_url,
                    title=title,
                    jurisdiction="DE",
                    topic=topic.value,
                    effective_year=effective_year,
                    retrieved_at=stamp,
                    embedding=vectors[index] if vectors else None,
                    token_estimate=chunk.token_estimate,
                )
            )
        self._loaded = False
        return len(chunks)

    def ingest_directory(self, session: Session, directory: Path) -> dict[str, int]:
        """Ingest every ``.md`` file, reading metadata from its front matter.

        Front matter is required. A document with no source URL and no topic
        cannot produce a usable citation, so ingesting it would create a
        passage the answer layer must then refuse to cite - a silent hole.
        """
        written: dict[str, int] = {}
        for path in sorted(directory.glob("*.md")):
            raw = path.read_text(encoding="utf-8")
            meta, body = _split_front_matter(raw)
            if not meta.get("source_url") or not meta.get("topic"):
                logger.warning("skipping %s: front matter needs source_url and topic", path.name)
                continue
            try:
                topic = LegalCategory(meta["topic"])
            except ValueError:
                logger.warning("skipping %s: unknown topic %r", path.name, meta["topic"])
                continue
            written[path.stem] = self.ingest_document(
                session,
                document_id=path.stem,
                title=meta.get("title", path.stem),
                source_name=meta.get("source_name", "unknown"),
                source_url=meta.get("source_url"),
                topic=topic,
                text=body,
                effective_year=int(meta["effective_year"])
                if str(meta.get("effective_year", "")).isdigit()
                else None,
                retrieved_at=_parse_stamp(meta.get("retrieved_at")),
            )
        return written

    # ------------------------------------------------------------ retrieval
    def _load_index(self, session: Session) -> list[KnowledgeChunkRow]:
        rows = list(session.execute(select(KnowledgeChunkRow)).scalars())
        if not self._loaded:
            self._bm25.build([(row.id, row.text) for row in rows])
            self._loaded = True
        return rows

    def retrieve(
        self,
        session: Session,
        query: str,
        *,
        top_k: int | None = None,
        topics: list[LegalCategory] | None = None,
    ) -> list[KnowledgeChunk]:
        """Return the best passages, with metadata attached for citation."""
        top_k = top_k or self._settings.rag_top_k
        rows = self._load_index(session)
        if not rows:
            return []

        by_id = {row.id: row for row in rows}
        allowed = (
            {row.id for row in rows if row.topic in {t.value for t in topics}}
            if topics
            else set(by_id)
        )

        lexical = [
            (chunk_id, score)
            for chunk_id, score in self._bm25.search(query, top_k * 3)
            if chunk_id in allowed
        ]
        rankings = [lexical]

        dense = self._dense_search(session, query, rows, top_k * 3, allowed)
        if dense:
            rankings.append(dense)

        fused = reciprocal_rank_fusion(rankings) if len(rankings) > 1 else lexical
        return [_to_chunk(by_id[chunk_id]) for chunk_id, _ in fused[:top_k] if chunk_id in by_id]

    def _dense_search(
        self,
        session: Session,
        query: str,
        rows: list[KnowledgeChunkRow],
        limit: int,
        allowed: set[str],
    ) -> list[tuple[str, float]]:
        if not self._embedder.available:
            return []
        try:
            vector = self._embedder.embed([query])[0]
        except Exception:
            logger.warning("query embedding failed; using lexical results only", exc_info=True)
            return []

        if pgvector_available():
            return self._pgvector_search(session, vector, limit, allowed)

        embedded = [(row.id, row.embedding) for row in rows if row.embedding]
        if not embedded:
            return []
        matrix = np.array([vec for _, vec in embedded], dtype=float)
        scores = cosine_similarity(vector, matrix)
        order = np.argsort(-scores)[: limit * 2]
        return [
            (embedded[i][0], float(scores[i]))
            for i in order
            if embedded[i][0] in allowed
        ][:limit]

    def _pgvector_search(
        self, session: Session, vector: list[float], limit: int, allowed: set[str]
    ) -> list[tuple[str, float]]:
        from sqlalchemy import text as sql_text

        try:
            result = session.execute(
                sql_text(
                    "SELECT id, 1 - (embedding <=> CAST(:v AS vector)) AS score "
                    "FROM knowledge_chunks WHERE embedding IS NOT NULL "
                    "ORDER BY embedding <=> CAST(:v AS vector) LIMIT :k"
                ),
                {"v": str(vector), "k": limit * 2},
            )
            return [(row[0], float(row[1])) for row in result if row[0] in allowed][:limit]
        except Exception:  # pragma: no cover - depends on server state
            logger.warning("pgvector query failed; falling back to numpy", exc_info=True)
            return []

    # ------------------------------------------------------------- reporting
    def stats(self, session: Session) -> CorpusStats:
        documents = session.execute(select(KnowledgeDocumentRow)).scalars().all()
        chunk_count = session.query(KnowledgeChunkRow).count()
        embedded = (
            session.query(KnowledgeChunkRow)
            .filter(KnowledgeChunkRow.embedding.isnot(None))
            .count()
        )
        return CorpusStats(
            documents=len(documents),
            chunks=chunk_count,
            embedded_chunks=embedded,
            retrieval_mode="hybrid" if embedded else "lexical",
            embedder=self._embedder.name,
            pgvector=pgvector_available(),
        )

    def invalidate(self) -> None:
        self._loaded = False


def _to_chunk(row: KnowledgeChunkRow) -> KnowledgeChunk:
    return KnowledgeChunk(
        id=row.id,
        document_id=row.document_id,
        ordinal=row.ordinal,
        text=row.text,
        source_name=row.source_name,
        source_url=row.source_url,
        title=row.title,
        jurisdiction=row.jurisdiction,
        topic=LegalCategory(row.topic),
        effective_year=row.effective_year,
        retrieved_at=row.retrieved_at,
    )


def _split_front_matter(raw: str) -> tuple[dict[str, str], str]:
    """Parse a simple ``key: value`` front-matter block delimited by ``---``."""
    if not raw.startswith("---"):
        return {}, raw
    end = raw.find("\n---", 3)
    if end == -1:
        return {}, raw
    block = raw[3:end]
    body = raw[end + 4 :].lstrip("\n")
    meta: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip().strip('"')
    return meta, body


def _parse_stamp(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)
