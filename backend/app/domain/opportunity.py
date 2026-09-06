"""The Opportunity: a real, sourced, citable earning possibility.

This is the product's central object and its hardest constraint. An Opportunity
may only exist because a source published it. There is no code path anywhere in
this repository that constructs one from a model's imagination - the language
model plans queries and reads retrieved pages, and :mod:`app.services.normalize`
validates what it read against this schema, but the model never authors a
record. See docs/DATA_PROVENANCE.md.

Consequences visible in the schema:

* Every optional field is genuinely optional and defaults to ``None``. A
  missing deadline is a missing deadline, not "no deadline".
* :class:`Requirement` carries a strength, so an unstated requirement neither
  disqualifies the user nor is waved through as satisfied.
* :attr:`Opportunity.is_demo` is mandatory-by-default-True at the seed layer,
  so a fixture cannot accidentally masquerade as a live listing.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from app.domain.enums import (
    Confidence,
    EmploymentType,
    IncomeStreamCategory,
    LanguageLevel,
    RemoteType,
    RequirementStrength,
    SafetyVerdict,
    SourceType,
    TrustLabel,
)
from app.domain.evidence import Evidenced, SourceRef, freshness_score, trust_label, utcnow
from app.domain.money import MoneyRange

#: Query parameters that identify a click, not a document. Stripped before an
#: opportunity is fingerprinted so the same listing arriving via a search API
#: and via an RSS feed collapses into one record.
_TRACKING_PARAMS = re.compile(
    r"^(utm_[a-z_]+|gclid|fbclid|mc_[a-z]+|ref|referrer|source|campaign|trk|" r"sessionid|sid)$",
    re.IGNORECASE,
)


def canonical_url(raw: str | None) -> str | None:
    """Reduce a URL to what identifies the document.

    Lowercases the host, drops the fragment, removes tracking parameters and
    normalises a trailing slash. Deliberately keeps meaningful query strings:
    ``?id=8123`` is the listing, and stripping it would merge every job on a
    site into one.
    """
    if not raw:
        return None
    try:
        parts = urlsplit(raw.strip())
    except ValueError:
        return None
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return None
    kept = [
        pair
        for pair in parts.query.split("&")
        if pair and not _TRACKING_PARAMS.match(pair.split("=", 1)[0])
    ]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), path, "&".join(sorted(kept)), "")
    )


def normalise_title(raw: str) -> str:
    """Fold a title for comparison: lowercase, punctuation-stripped, de-spaced."""
    folded = re.sub(r"[^a-z0-9\s]+", " ", raw.lower())
    return " ".join(folded.split())


class Requirement(BaseModel):
    """One eligibility condition, with the strength that decides its effect."""

    model_config = ConfigDict(extra="forbid")

    label: str
    strength: RequirementStrength = RequirementStrength.UNKNOWN
    #: Verbatim from the source where possible, so the UI can quote rather than
    #: paraphrase a condition the user will be held to.
    source_text: str | None = None


class LanguageRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    minimum: LanguageLevel = LanguageLevel.UNKNOWN
    strength: RequirementStrength = RequirementStrength.UNKNOWN


class SafetyAssessment(BaseModel):
    """Output of :class:`app.services.safety.OpportunitySafetyClassifier`."""

    model_config = ConfigDict(extra="forbid")

    verdict: SafetyVerdict = SafetyVerdict.ALLOWED
    reasons: list[str] = Field(default_factory=list)
    #: Which prohibited-category rules fired, for auditability.
    matched_rules: list[str] = Field(default_factory=list)


class Opportunity(BaseModel):
    """A real earning opportunity, as published by an identifiable source."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    organization: str | None = None

    category: IncomeStreamCategory = IncomeStreamCategory.OTHER
    subcategory: str | None = None

    description: str | None = None
    #: Short neutral restatement. May be model-written, and is labelled as such
    #: in the UI; it never carries a fact absent from ``description``.
    summary: str | None = None

    country: str | None = None
    region: str | None = None
    city: str | None = None
    remote_type: RemoteType = RemoteType.UNKNOWN

    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    required_languages: list[LanguageRequirement] = Field(default_factory=list)
    experience_min_years: float | None = Field(default=None, ge=0, le=70)
    experience_max_years: float | None = Field(default=None, ge=0, le=70)

    eligibility_text: str | None = None
    eligibility_structured: list[Requirement] = Field(default_factory=list)

    employment_type: EmploymentType = EmploymentType.UNKNOWN

    compensation: MoneyRange = Field(default_factory=MoneyRange)
    #: True only when the source states the figure on the page we retrieved.
    #: A recruiter's estimate, a salary-comparison site or a model's guess do
    #: not qualify.
    compensation_verified: bool = False

    #: Hours **per week**, always. The matching engine compares these directly
    #: against the user's stated weekly availability, so a record expressing
    #: total project hours here would silently produce a wrong availability
    #: score rather than an obviously wrong one.
    estimated_hours_min: float | None = Field(default=None, ge=0)
    estimated_hours_max: float | None = Field(default=None, ge=0)

    deadline: date | None = None
    start_date: date | None = None

    source: SourceRef
    #: Additional sources that produced the same record. Kept for provenance
    #: after de-duplication rather than discarded with the duplicate.
    corroborating_sources: list[SourceRef] = Field(default_factory=list)

    is_active: bool = True
    is_demo: bool = False
    #: Sponsored placements must be visible as such and must never be allowed to
    #: influence ranking - see docs/BUSINESS_MODEL.md.
    is_sponsored: bool = False

    evidence_confidence: Confidence = Confidence.UNKNOWN
    safety: SafetyAssessment = Field(default_factory=SafetyAssessment)

    #: Per-field provenance for the values a user will act on. The plain fields
    #: above are what the app reads; these carry "and how do we know".
    field_evidence: dict[str, Evidenced[str]] = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    @model_validator(mode="after")
    def _coherent(self) -> Opportunity:
        if (
            self.experience_min_years is not None
            and self.experience_max_years is not None
            and self.experience_min_years > self.experience_max_years
        ):
            raise ValueError("experience_min_years must not exceed experience_max_years")
        if (
            self.estimated_hours_min is not None
            and self.estimated_hours_max is not None
            and self.estimated_hours_min > self.estimated_hours_max
        ):
            raise ValueError("estimated_hours_min must not exceed estimated_hours_max")
        # A demo record must never claim verified compensation: that pairing is
        # exactly the confusion the demo mode exists to avoid.
        if self.is_demo and self.compensation_verified:
            raise ValueError("demo opportunities cannot claim compensation_verified")
        return self

    # ------------------------------------------------------------- identity
    @property
    def canonical_source_url(self) -> str | None:
        return canonical_url(str(self.source.url)) if self.source.url else None

    def fingerprint(self) -> str:
        """Deterministic identity for de-duplication.

        Canonical URL when there is one, because that is the strongest signal a
        listing is the same listing. Otherwise organisation + folded title +
        deadline, which is what distinguishes two annual rounds of the same
        grant from one another.
        """
        url = self.canonical_source_url
        if url:
            basis = f"url:{url}"
        else:
            basis = "|".join(
                [
                    "org:" + (self.organization or "").strip().lower(),
                    "title:" + normalise_title(self.title),
                    "deadline:" + (self.deadline.isoformat() if self.deadline else ""),
                ]
            )
        return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:32]

    # ---------------------------------------------------------------- trust
    @property
    def trust(self) -> TrustLabel:
        return trust_label(
            confidence=self.evidence_confidence,
            is_demo=self.is_demo,
            source=self.source,
            max_age_days=None,
        )

    def freshness(self, *, now: datetime | None = None) -> float:
        return freshness_score(self.source, now=now)

    # ------------------------------------------------------------ knowledge
    def known_facts(self) -> list[str]:
        """What we can state, for the "What we know" panel."""
        facts: list[str] = []
        if self.organization:
            facts.append(f"Published by {self.organization}.")
        if self.compensation.known and self.compensation_verified:
            facts.append("Compensation is stated by the source.")
        if self.remote_type is not RemoteType.UNKNOWN:
            facts.append(f"Work arrangement: {self.remote_type.value.lower()}.")
        if self.deadline:
            facts.append(f"Application deadline: {self.deadline.isoformat()}.")
        if self.estimated_hours_min is not None or self.estimated_hours_max is not None:
            facts.append("The source indicates a time commitment.")
        if self.eligibility_structured:
            hard = sum(
                1 for r in self.eligibility_structured if r.strength is RequirementStrength.HARD
            )
            if hard:
                facts.append(f"{hard} stated hard requirement(s).")
        return facts

    def unknown_facts(self) -> list[str]:
        """What we deliberately do not claim, for the "What we do not know" panel.

        This list is as important as the match score. It is the difference
        between a recommendation the user can calibrate and one they have to
        take on faith.
        """
        gaps: list[str] = []
        if not self.compensation.known:
            gaps.append("Compensation is not published by the source.")
        elif not self.compensation_verified:
            gaps.append("Compensation appears in the listing but we could not verify it.")
        if self.compensation.known and self.compensation.tax_treatment.value == "UNKNOWN":
            gaps.append("Whether the amount is gross or net is not stated.")
        if self.estimated_hours_min is None and self.estimated_hours_max is None:
            gaps.append("Time commitment is not published.")
        if self.deadline is None:
            gaps.append("No deadline is published; this may be ongoing or may have closed.")
        if not self.eligibility_structured and not self.eligibility_text:
            gaps.append("Eligibility conditions are not published in a structured form.")
        if self.remote_type is RemoteType.UNKNOWN:
            gaps.append("Remote/onsite arrangement is not stated.")
        for requirement in self.eligibility_structured:
            if requirement.strength is RequirementStrength.UNKNOWN:
                gaps.append(f"Unclear whether '{requirement.label}' is mandatory.")
        return gaps


class OpportunityCandidate(BaseModel):
    """Raw material from a source, before extraction and validation.

    The deliberate gap between this and :class:`Opportunity` is the pipeline's
    safety property: everything a source hands us lands here as untrusted text
    and can only become an Opportunity by passing injection screening, model
    extraction into a closed schema, and validation.
    """

    model_config = ConfigDict(extra="forbid")

    source_name: str
    source_type: SourceType
    url: HttpUrl | None = None
    title: str
    #: Untrusted. Never placed in a system message; always fenced and screened.
    raw_text: str
    published_at: datetime | None = None
    retrieved_at: datetime = Field(default_factory=utcnow)
    #: Anything the source gave us in structured form (an API's own fields).
    structured: dict[str, str] = Field(default_factory=dict)

    def to_source_ref(self) -> SourceRef:
        return SourceRef(
            name=self.source_name,
            url=self.url,
            source_type=self.source_type,
            retrieved_at=self.retrieved_at,
            last_verified_at=None,
        )
