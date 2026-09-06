"""File-backed sources: demo fixtures and the curated dataset.

These are what make the product work with no credentials, no network and no
spend - which matters for three different audiences: a developer cloning the
repo, an accelerator jury clicking through in a room with bad wifi, and the
test suite.

The two are separated by exactly one field, and it is the important one.
:class:`DemoOpportunitySource` sets ``is_demo=True`` on every record it
produces, and the schema forbids a demo record from claiming verified
compensation. :class:`CuratedOpportunitySource` carries real records with real
source URLs that a human checked, and refuses to load one without provenance.

Both bypass model extraction, because their JSON is already structured - so
they are also the path that proves the pipeline does not *require* an LLM.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.domain.enums import SourceType
from app.domain.opportunity import OpportunityCandidate
from app.sources.base import OpportunitySource, SearchPlan, SourceHealth, SourceResult

logger = logging.getLogger(__name__)


class _JsonFileSource(OpportunitySource):
    """Shared loading, filtering and validation for the two file-backed sources."""

    def __init__(self, path: Path) -> None:
        self._path = path

    # -------------------------------------------------------------- loading
    def _load(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("could not read %s", self._path, exc_info=True)
            return []
        records = payload.get("opportunities") if isinstance(payload, dict) else payload
        return [r for r in (records or []) if isinstance(r, dict)]

    def _matches(self, record: dict[str, Any], plan: SearchPlan) -> bool:
        """Filter on jurisdiction only, then rank-in on keyword relevance.

        Deliberately *not* filtered by remote type, hours or category, even
        though the plan carries all three. Those are the user's preferences, and
        preferences are scored by :mod:`app.services.matching`, not used to hide
        things. A hybrid role at eight hours a week that pays three times the
        rate is exactly the money someone is missing; removing it here would
        mean the user never learns it existed, and the honest "80% match, but it
        is hybrid and exceeds your stated hours" card could never be shown.

        The plan's constraints do still narrow *live* search, where each result
        costs an API call and a page fetch. For a local file there is no such
        cost, so the only filter that earns its place is jurisdiction.
        """
        wanted_countries = {c.upper() for c in plan.countries}
        country = record.get("country")
        if wanted_countries and country and str(country).upper() not in wanted_countries:
            return False
        return self._keyword_hit(record, plan)

    def _keyword_hit(self, record: dict[str, Any], plan: SearchPlan) -> bool:
        """Loose relevance gate. Category membership alone is enough to pass.

        A record in a category the plan is looking for is relevant by
        construction, regardless of whether any query term happens to appear in
        its prose - a grant listing rarely repeats the words of the query that
        should find it.
        """
        if not plan.queries:
            return True
        if plan.categories and record.get("category") in {c.value for c in plan.categories}:
            return True
        haystack = " ".join(
            str(record.get(field, ""))
            for field in ("title", "organization", "description", "subcategory")
        ).lower()
        haystack += " " + " ".join(
            str(s).lower()
            for field in ("required_skills", "preferred_skills")
            for s in record.get(field, [])
        )
        terms = {
            word
            for query in plan.queries
            for word in query.text.lower().split()
            if len(word) > 3
        }
        return any(term in haystack for term in terms)

    def _to_candidate(self, record: dict[str, Any]) -> OpportunityCandidate:
        return OpportunityCandidate(
            source_name=self.name,
            source_type=self.source_type,
            url=record.get("source_url"),
            title=str(record.get("title", "Untitled")),
            # The structured payload is what normalisation actually reads. The
            # raw text exists so safety classification sees the same words a
            # scraped listing would have shown it.
            raw_text=" ".join(
                str(record.get(field, ""))
                for field in ("title", "organization", "description", "eligibility_text")
            ),
            structured={"json": json.dumps(record, ensure_ascii=False)},
        )

    def search(self, plan: SearchPlan) -> SourceResult:
        try:
            records = [r for r in self._load() if self._matches(r, plan)]
        except Exception as error:  # a malformed fixture must not break discovery
            return self._failed(error)
        return self._succeeded([self._to_candidate(r) for r in records], queries_run=1)

    def health_check(self) -> SourceHealth:
        exists = self._path.exists()
        return SourceHealth(
            source_id=self.id,
            ok=exists,
            detail="" if exists else f"{self._path.name} is missing",
        )


class DemoOpportunitySource(_JsonFileSource):
    """Fictional opportunities for the demo. Every record is marked DEMO.

    The fixtures use invented organisation names that could not be mistaken for
    real ones, and the UI badges them. A jury must never leave the room thinking
    they saw a live offer.
    """

    id = "demo"
    name = "Demo dataset"
    source_type = SourceType.DEMO
    access_basis = "Fictional data authored for this repository. Not real listings."

    def _to_candidate(self, record: dict[str, Any]) -> OpportunityCandidate:
        # Forced here rather than trusted from the file, so a fixture cannot
        # accidentally present itself as live.
        record = {**record, "is_demo": True, "compensation_verified": False}
        return super()._to_candidate(record)


class CuratedOpportunitySource(_JsonFileSource):
    """Real, human-checked opportunities with real source URLs.

    Refuses to load a record without a source URL. Curation is the claim that a
    person looked at the page; a record with nothing to point at cannot support
    that claim and is dropped with a warning rather than shown unverifiable.
    """

    id = "curated"
    name = "Curated dataset"
    source_type = SourceType.CURATED
    access_basis = (
        "Publicly listed opportunities recorded manually from each organisation's "
        "own published page. No automated collection; see docs/DATA_PROVENANCE.md."
    )

    def _load(self) -> list[dict[str, Any]]:
        records = super()._load()
        kept: list[dict[str, Any]] = []
        for record in records:
            if not record.get("source_url"):
                logger.warning(
                    "curated record %r has no source_url and was dropped",
                    record.get("title", "?"),
                )
                continue
            kept.append({**record, "is_demo": False})
        return kept
