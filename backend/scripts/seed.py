"""Prepare a runnable database: schema, knowledge corpus, legal facts, sources.

Idempotent. Running it twice changes nothing the second time, which matters
because it is wired into ``make dev`` and people re-run it without thinking.

Deliberately does NOT create opportunity rows. Opportunities enter the database
through the discovery pipeline, so that even the demo data has passed safety
classification, validation and de-duplication - the same path a real listing
takes. Seeding them directly would create the one class of row whose provenance
nobody could account for.

Run with:  python -m scripts.seed
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.db.base import Base, create_app_engine, session_scope
from app.db.models import OpportunitySource
from app.rag.store import KnowledgeStore
from app.services.legal_facts import LegalFactRepository
from app.sources.registry import FEEDS, SourceRegistry


def ensure_schema() -> None:
    """Create tables if they are absent.

    Alembic owns migrations; this exists so ``make seed`` works on a fresh
    clone before anyone has run ``alembic upgrade head``, and is a no-op
    afterwards.
    """
    Base.metadata.create_all(create_app_engine())


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the Money You're Missing database.")
    parser.add_argument(
        "--rebuild-knowledge",
        action="store_true",
        help="Re-chunk and re-embed the corpus even if the checksums match.",
    )
    args = parser.parse_args()

    settings = get_settings()
    ensure_schema()

    with session_scope() as session:
        facts = LegalFactRepository(settings)
        written = facts.load_from_file(session, settings.data_dir / "legal_facts.json")
        print(f"legal facts: {written} loaded")

        store = KnowledgeStore(settings)
        if args.rebuild_knowledge:
            from app.db.models import KnowledgeChunkRow, KnowledgeDocumentRow

            session.query(KnowledgeChunkRow).delete()
            session.query(KnowledgeDocumentRow).delete()
            session.flush()
        counts = store.ingest_directory(session, settings.knowledge_dir)
        total = sum(counts.values())
        print(
            f"knowledge: {len(counts)} document(s), {total} chunk(s) written"
            + (" (unchanged documents skipped)" if total == 0 else "")
        )

        registry = SourceRegistry(settings)
        for source in registry.build():
            row = session.get(OpportunitySource, source.id)
            values = {
                "name": source.name,
                "source_type": source.source_type.value,
                "access_basis": source.access_basis,
                "is_enabled": True,
            }
            if row is None:
                session.add(OpportunitySource(id=source.id, **values))
            else:
                for key, value in values.items():
                    setattr(row, key, value)
        for feed in FEEDS:
            if feed.verified:
                continue
            # Registered but disabled, so the gap is visible in
            # GET /api/provenance rather than silently absent.
            if session.get(OpportunitySource, feed.source_id) is None:
                session.add(
                    OpportunitySource(
                        id=feed.source_id,
                        name=feed.name,
                        source_type="RSS",
                        base_url=feed.feed_url,
                        is_enabled=False,
                        access_basis=feed.access_basis,
                        last_error="NOT YET VERIFIED - feed availability unconfirmed.",
                    )
                )
        pending = sum(1 for feed in FEEDS if not feed.verified)
        print(f"sources: {len(registry.build())} enabled, {pending} pending verification")

        report = facts.status_report(session)
        print(f"fact status: {report['by_status']}  stale_rate={report['stale_fact_rate']}")
        print(f"corpus: {store.stats(session)}")

    print("\nSeed complete. Start the API with: make dev")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
