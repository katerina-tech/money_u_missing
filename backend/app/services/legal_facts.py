"""Versioned legal facts: the numbers that change, kept out of prompts.

Every German threshold this product touches moves. The Kleinunternehmer limit,
the Sparer-Pauschbetrag, the Minijob ceiling, the Grundfreibetrag - each has a
different revision cycle, and a language model states last year's value with
exactly the same fluency as this year's.

So they live here as rows with an effective period, a source URL and a
verification timestamp, and a fact past its review horizon is reported as
NEEDS_REVIEW rather than quoted. That is the mechanism behind the product
promise that stale means stale, not confident.

Nothing in this repository ships a legal *value* that was not read from the
authority named in its ``source_url``. Where a value could not be confirmed at
the time of writing, the row exists with ``content_available=False`` and is
listed as NOT YET VERIFIED - visible, and never quoted.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import LegalFactRow
from app.domain.enums import LegalCategory, LegalVerificationStatus, TrustLabel
from app.domain.legal import LegalFact

logger = logging.getLogger(__name__)


class LegalFactRepository:
    """Reads and writes versioned legal facts."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    @property
    def max_age(self) -> timedelta:
        return timedelta(days=self._settings.legal_fact_max_age_days)

    # ------------------------------------------------------------- reading
    def get(self, session: Session, fact_id: str) -> LegalFact | None:
        row = session.get(LegalFactRow, fact_id)
        return _to_domain(row) if row else None

    def for_topics(
        self, session: Session, topics: list[LegalCategory], *, on: date | None = None
    ) -> list[LegalFact]:
        """Facts for the given topics that are in effect on ``on``.

        Facts whose effective period has ended are excluded from the result but
        remain in the table: the 2024 threshold is still the right answer to a
        question about 2024, and deleting history would make that unanswerable.
        """
        if not topics:
            return []
        rows = session.execute(
            select(LegalFactRow).where(
                LegalFactRow.category.in_([t.value for t in topics]),
                LegalFactRow.jurisdiction == "DE",
            )
        ).scalars()
        facts = [_to_domain(row) for row in rows]
        return [f for f in facts if f.in_effect(on) and f.content_available]

    def all(self, session: Session) -> list[LegalFact]:
        rows = session.execute(select(LegalFactRow).order_by(LegalFactRow.category)).scalars()
        return [_to_domain(row) for row in rows]

    def status_report(self, session: Session) -> dict[str, object]:
        """Coverage and staleness. Surfaced as a metric - see docs/METRICS.md.

        ``stale_fact_rate`` is one of the product's honesty metrics: if it
        climbs, the KEEP module is quietly degrading and the answer layer is
        refusing more often, which users experience as the product getting less
        useful for no visible reason.
        """
        facts = self.all(session)
        counts: dict[str, int] = {}
        for fact in facts:
            status = fact.effective_status(max_age=self.max_age)
            counts[status.value] = counts.get(status.value, 0) + 1
        verified = counts.get(LegalVerificationStatus.VERIFIED.value, 0)
        return {
            "total": len(facts),
            "by_status": counts,
            "unavailable": sum(1 for f in facts if not f.content_available),
            "stale_fact_rate": round(1 - (verified / len(facts)), 4) if facts else None,
            "max_age_days": self._settings.legal_fact_max_age_days,
        }

    def trust(self, fact: LegalFact) -> TrustLabel:
        return fact.trust(max_age=self.max_age)

    # ------------------------------------------------------------- writing
    def upsert(self, session: Session, fact: LegalFact) -> None:
        row = session.get(LegalFactRow, fact.id)
        values = {
            "jurisdiction": fact.jurisdiction,
            "category": fact.category.value,
            "title": fact.title,
            "summary": fact.summary,
            "structured_value": fact.structured_value,
            "effective_from": fact.effective_from,
            "effective_to": fact.effective_to,
            "source_name": fact.source_name,
            "source_url": str(fact.source_url) if fact.source_url else None,
            "retrieved_at": fact.retrieved_at,
            "last_verified_at": fact.last_verified_at,
            "verification_status": fact.verification_status.value,
            "content_available": fact.content_available,
        }
        if row is None:
            session.add(LegalFactRow(id=fact.id, **values))
        else:
            for key, value in values.items():
                setattr(row, key, value)

    def load_from_file(self, session: Session, path: Path) -> int:
        """Load the registry file. Returns how many rows were written."""
        if not path.exists():
            logger.warning("legal fact registry %s is missing", path)
            return 0
        payload = json.loads(path.read_text(encoding="utf-8"))
        written = 0
        for record in payload.get("facts", []):
            try:
                fact = LegalFact(
                    id=record["id"],
                    jurisdiction=record.get("jurisdiction", "DE"),
                    category=LegalCategory(record["category"]),
                    title=record["title"],
                    summary=record["summary"],
                    structured_value=record.get("structured_value", {}),
                    effective_from=_date(record.get("effective_from")),
                    effective_to=_date(record.get("effective_to")),
                    source_name=record["source_name"],
                    source_url=record.get("source_url"),
                    retrieved_at=_stamp(record.get("retrieved_at")),
                    last_verified_at=_stamp(record.get("last_verified_at")),
                    verification_status=LegalVerificationStatus(
                        record.get("verification_status", "UNKNOWN")
                    ),
                    content_available=bool(record.get("content_available", True)),
                )
            except (KeyError, ValueError):
                logger.warning("skipping malformed legal fact %r", record.get("id"), exc_info=True)
                continue
            self.upsert(session, fact)
            written += 1
        return written


def _to_domain(row: LegalFactRow) -> LegalFact:
    return LegalFact(
        id=row.id,
        jurisdiction=row.jurisdiction,
        category=LegalCategory(row.category),
        title=row.title,
        summary=row.summary,
        structured_value=row.structured_value,
        effective_from=row.effective_from,
        effective_to=row.effective_to,
        source_name=row.source_name,
        source_url=row.source_url,
        retrieved_at=row.retrieved_at,
        last_verified_at=row.last_verified_at,
        verification_status=LegalVerificationStatus(row.verification_status),
        content_available=row.content_available,
    )


def _date(raw: object) -> date | None:
    if isinstance(raw, str) and raw.strip():
        try:
            return date.fromisoformat(raw.strip()[:10])
        except ValueError:
            return None
    return None


def _stamp(raw: object) -> datetime | None:
    if isinstance(raw, str) and raw.strip():
        try:
            return datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    return None
