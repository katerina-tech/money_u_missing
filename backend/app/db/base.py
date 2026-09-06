"""Engine, session and dialect-portable column types.

One URL decides everything. ``MYM_DATABASE_URL`` unset gives SQLite in a local
file, which is what makes ``make dev``, ``make test`` and the accelerator demo
work on a laptop with no services running. Set it to a Postgres URL and the same
code runs against Postgres with pgvector, which is the production target.

The portability is confined to this module - two custom column types and one
capability probe. No repository, service or route contains a dialect branch.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, ClassVar

from sqlalchemy import JSON, DateTime, Dialect, Engine, create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import Text, TypeDecorator

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

#: Dimension of the on-device embedding model (BAAI/bge-small-en-v1.5). Fixed at
#: the column level because pgvector needs a declared width; switching backends
#: is therefore a migration, not a silent corruption of an existing index.
EMBEDDING_DIM = 384


class Base(DeclarativeBase):
    """Declarative base. ``type_annotation_map`` keeps model code free of dialect types."""

    type_annotation_map: ClassVar[dict[Any, Any]] = {dict[str, Any]: JSON, list[str]: JSON}


class UtcDateTime(TypeDecorator[datetime]):
    """A timestamp that is always timezone-aware UTC, on every dialect.

    Postgres round-trips ``TIMESTAMPTZ`` correctly; SQLite has no timezone type
    and hands back naive datetimes regardless of ``timezone=True``. Left alone,
    that difference is invisible until something subtracts a stored timestamp
    from ``datetime.now(UTC)`` and raises - or, far worse, until a comparison
    silently succeeds against a value that is actually local time.

    This product's freshness and staleness logic is entirely built on such
    subtractions, so the normalisation happens here rather than at each call
    site: an aware value goes in, an aware value comes out.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            # A naive value reaching the database is a bug upstream, but storing
            # it as if it were UTC is better than storing it ambiguously.
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class Vector(TypeDecorator[list[float]]):
    """A float vector: ``pgvector`` on Postgres, JSON text elsewhere.

    Storing vectors as JSON on SQLite is not a performance compromise worth
    worrying about here - the corpus is a few hundred chunks of curated German
    tax guidance, and an exhaustive numpy scan over it takes under a
    millisecond. On Postgres the real type is used so the ANN index in the
    migration is available.
    """

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> Any:
        if dialect.name == "postgresql":
            try:
                from pgvector.sqlalchemy import Vector as PGVector

                return dialect.type_descriptor(PGVector(EMBEDDING_DIM))
            except ImportError:
                # Postgres without the pgvector package installed: fall back to
                # text rather than failing to import the models. The RAG store
                # probes for the real type and uses numpy scanning if absent.
                logger.warning("pgvector not installed; storing embeddings as text")
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value: list[float] | None, dialect: Dialect) -> Any:
        if value is None:
            return None
        if dialect.name == "postgresql":
            try:
                import pgvector.sqlalchemy  # noqa: F401

                return value
            except ImportError:
                pass
        return json.dumps([round(float(v), 6) for v in value])

    def process_result_value(self, value: Any, dialect: Dialect) -> list[float] | None:
        if value is None:
            return None
        if isinstance(value, str):
            return [float(v) for v in json.loads(value)]
        return [float(v) for v in value]


class StringList(TypeDecorator[list[str]]):
    """A list of strings as JSON. Portable and, at these sizes, entirely adequate."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: list[str] | None, dialect: Dialect) -> str | None:
        return None if value is None else json.dumps(value, ensure_ascii=False)

    def process_result_value(self, value: str | None, dialect: Dialect) -> list[str]:
        if not value:
            return []
        parsed = json.loads(value)
        return [str(v) for v in parsed]


class JsonDict(TypeDecorator[dict[str, Any]]):
    """A JSON object, portable across dialects."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: dict[str, Any] | None, dialect: Dialect) -> str | None:
        return None if value is None else json.dumps(value, ensure_ascii=False, default=str)

    def process_result_value(self, value: str | None, dialect: Dialect) -> dict[str, Any]:
        if not value:
            return {}
        parsed = json.loads(value)
        return dict(parsed)


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def create_app_engine(settings: Settings | None = None) -> Engine:
    settings = settings or get_settings()
    url = settings.resolved_database_url
    kwargs: dict[str, Any] = {"echo": settings.database_echo, "future": True}
    if url.startswith("sqlite"):
        # check_same_thread=False because FastAPI runs sync handlers in a
        # threadpool; each request still gets its own Session.
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_pre_ping"] = True
        kwargs["pool_size"] = 5
        kwargs["max_overflow"] = 10
    engine = create_engine(url, **kwargs)

    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_connection: Any, _record: Any) -> None:
            cursor = dbapi_connection.cursor()
            # Foreign keys are OFF by default in SQLite, which would silently
            # disable every ON DELETE CASCADE the schema relies on for account
            # deletion - a GDPR-relevant behaviour, not a nicety.
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    return engine


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_app_engine()
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _session_factory


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope. Commits on success, rolls back on any exception."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_engine() -> None:
    """Drop cached engine and session factory. Used by tests between databases."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


def pgvector_available(engine: Engine | None = None) -> bool:
    """Whether ANN search is usable, rather than whether Postgres is in use.

    Checked at runtime instead of assumed from the URL: a managed Postgres may
    not have the extension enabled, and the retriever needs to fall back to a
    numpy scan quietly rather than raise on the first tax question.
    """
    engine = engine or get_engine()
    if engine.dialect.name != "postgresql":
        return False
    try:
        with engine.connect() as connection:
            found = connection.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            ).scalar()
        return bool(found)
    except Exception:  # pragma: no cover - depends on server state
        logger.warning("could not probe for pgvector; assuming unavailable")
        return False
