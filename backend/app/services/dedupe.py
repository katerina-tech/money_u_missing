"""De-duplication across sources.

The same fellowship appears in an RSS feed, on the organisation's own page and
in three search results. Showing it five times destroys the product's core
claim - that it gives you *one* prioritised map rather than more tabs.

Deterministic first, fuzzy only where deterministic cannot decide:

1. **Canonical URL.** Tracking parameters stripped, host lowercased, fragment
   dropped. Two records pointing at the same document are the same record.
2. **Organisation + normalised title + deadline.** This is what separates the
   2026 round of a grant from the 2025 round: same organisation, same title,
   different deadline, genuinely different opportunity.
3. **Token similarity**, only within the same organisation and only when
   neither has a URL to compare. Cross-organisation fuzzy matching is not
   attempted, because merging two different organisations' listings is a far
   worse failure than showing a near-duplicate.

Merging keeps the *best-evidenced* record and attaches the others as
corroborating sources, so provenance survives de-duplication instead of being
thrown away with the duplicate.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from app.domain.enums import Confidence, SourceType
from app.domain.opportunity import Opportunity, normalise_title

#: Above this Jaccard similarity, two titles from the same organisation with no
#: distinguishing URL are treated as the same listing. Set high on purpose:
#: "Data Engineer" and "Senior Data Engineer" must stay separate.
SIMILARITY_THRESHOLD = 0.82

#: Words that carry no distinguishing information in an opportunity title.
_STOPWORDS = frozenset(
    {
        "a", "an", "the", "and", "or", "for", "of", "in", "at", "to", "with",
        "der", "die", "das", "und", "oder", "fuer", "für", "von", "im", "mit",
        "m", "w", "d", "mwd", "mfd", "remote", "parttime", "fulltime",
    }
)

#: How much we trust each source type when choosing which duplicate to keep.
#: An organisation's own page beats a search-engine snippet about it.
_SOURCE_RANK: dict[SourceType, int] = {
    SourceType.CURATED: 5,
    SourceType.ORGANISATION_PAGE: 4,
    SourceType.PUBLIC_API: 4,
    SourceType.RSS: 3,
    SourceType.SEARCH_API: 2,
    SourceType.DEMO: 1,
}

_CONFIDENCE_RANK: dict[Confidence, int] = {
    Confidence.VERIFIED: 5,
    Confidence.SOURCE_BACKED: 4,
    Confidence.EXTRACTED: 3,
    Confidence.UNVERIFIED: 2,
    Confidence.UNKNOWN: 1,
}


@dataclass
class DedupeReport:
    kept: list[Opportunity] = field(default_factory=list)
    #: ``duplicate_id -> kept_id``, so a log can explain what disappeared.
    merged: dict[str, str] = field(default_factory=dict)

    @property
    def removed_count(self) -> int:
        return len(self.merged)


def _tokens(title: str) -> frozenset[str]:
    words = re.findall(r"[a-z0-9]+", normalise_title(title))
    return frozenset(w for w in words if w not in _STOPWORDS and len(w) > 1)


def similarity(left: str, right: str) -> float:
    """Jaccard similarity over meaningful title tokens."""
    a, b = _tokens(left), _tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _quality(opportunity: Opportunity) -> tuple[int, int, int, float]:
    """Sort key for choosing the survivor. Higher is better on every element."""
    return (
        _SOURCE_RANK.get(opportunity.source.source_type, 0),
        _CONFIDENCE_RANK[opportunity.evidence_confidence],
        # More published detail is better - it is what the user reads.
        sum(
            1
            for present in (
                opportunity.compensation.known,
                opportunity.deadline is not None,
                bool(opportunity.eligibility_structured),
                opportunity.estimated_hours_min is not None,
                bool(opportunity.description),
            )
            if present
        ),
        -opportunity.source.age_days(),
    )


def _merge_into(winner: Opportunity, loser: Opportunity) -> Opportunity:
    """Keep the winner, absorb what the loser knew that the winner did not.

    Only *absence* is filled. A conflicting value is never overwritten: two
    sources disagreeing about compensation is exactly the case where picking
    one silently would be inventing certainty.
    """
    updates: dict[str, object] = {
        "corroborating_sources": [
            *winner.corroborating_sources,
            loser.source,
            *loser.corroborating_sources,
        ]
    }
    if winner.description is None and loser.description:
        updates["description"] = loser.description
    if winner.deadline is None and loser.deadline is not None:
        updates["deadline"] = loser.deadline
    if not winner.compensation.known and loser.compensation.known:
        updates["compensation"] = loser.compensation
        updates["compensation_verified"] = loser.compensation_verified
    if not winner.required_skills and loser.required_skills:
        updates["required_skills"] = loser.required_skills
    if not winner.eligibility_structured and loser.eligibility_structured:
        updates["eligibility_structured"] = loser.eligibility_structured
    if winner.organization is None and loser.organization:
        updates["organization"] = loser.organization

    # Corroboration from an independent source is real evidence, so a record
    # confirmed by two sources may be promoted - but never to VERIFIED, which
    # requires a human or a structured feed.
    if (
        winner.evidence_confidence is Confidence.EXTRACTED
        and loser.source.source_type is not winner.source.source_type
    ):
        updates["evidence_confidence"] = Confidence.SOURCE_BACKED

    return winner.model_copy(update=updates)


def deduplicate(opportunities: list[Opportunity]) -> DedupeReport:
    """Collapse duplicates, keeping the best-evidenced record of each."""
    report = DedupeReport()
    by_fingerprint: dict[str, Opportunity] = {}

    # Pass 1: exact identity (canonical URL, or org+title+deadline).
    for opportunity in sorted(opportunities, key=_quality, reverse=True):
        key = opportunity.fingerprint()
        existing = by_fingerprint.get(key)
        if existing is None:
            by_fingerprint[key] = opportunity
        else:
            by_fingerprint[key] = _merge_into(existing, opportunity)
            report.merged[opportunity.id] = existing.id

    # Pass 2: fuzzy, within an organisation, only for records with no URL to
    # compare. A URL is authoritative; if both have one and they differ, they
    # are different documents and we do not second-guess that.
    grouped: dict[str, list[Opportunity]] = defaultdict(list)
    for opportunity in by_fingerprint.values():
        grouped[(opportunity.organization or "").strip().lower()].append(opportunity)

    survivors: list[Opportunity] = []
    for organisation, group in grouped.items():
        if not organisation or len(group) == 1:
            survivors.extend(group)
            continue
        kept: list[Opportunity] = []
        for candidate in sorted(group, key=_quality, reverse=True):
            match = next(
                (
                    existing
                    for existing in kept
                    if existing.canonical_source_url is None
                    and candidate.canonical_source_url is None
                    and existing.deadline == candidate.deadline
                    and similarity(existing.title, candidate.title) >= SIMILARITY_THRESHOLD
                ),
                None,
            )
            if match is None:
                kept.append(candidate)
            else:
                kept[kept.index(match)] = _merge_into(match, candidate)
                report.merged[candidate.id] = match.id
        survivors.extend(kept)

    report.kept = sorted(survivors, key=lambda o: (o.source.age_days(), o.title))
    return report
