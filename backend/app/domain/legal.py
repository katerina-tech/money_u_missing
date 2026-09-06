"""German legal, tax and administrative knowledge - as versioned data.

The rule that shapes this module: **no number that changes with legislation is
allowed to live only inside a prompt.** The Kleinunternehmer threshold, the
Sparer-Pauschbetrag, the Minijob ceiling and the Grundfreibetrag all move, and a
model that learned last year's value will state it with the same fluency as this
year's. So each is a :class:`LegalFact` row with an effective period, a source
URL and a verification timestamp, and a fact past its review horizon is reported
as NEEDS_REVIEW instead of being answered from.

This module is decision-support, not Steuerberatung and not Rechtsberatung. That
is enforced behaviourally, not by a disclaimer: :class:`CitedAnswer` cannot be
constructed without citations, and :mod:`app.services.tax_education` refuses to
answer when retrieval comes back empty or stale.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from app.domain.enums import LegalCategory, LegalVerificationStatus, TrustLabel
from app.domain.evidence import utcnow


class LegalFact(BaseModel):
    """One versioned, source-backed rule or threshold."""

    model_config = ConfigDict(extra="forbid")

    id: str
    jurisdiction: str = "DE"
    category: LegalCategory
    title: str
    summary: str

    #: The machine-readable part, when there is one - e.g.
    #: ``{"threshold_eur": 25000, "applies_to": "previous_calendar_year"}``.
    #: Free-form because thresholds, rates and date rules do not share a shape.
    structured_value: dict[str, object] = Field(default_factory=dict)

    effective_from: date | None = None
    effective_to: date | None = None

    source_name: str
    source_url: HttpUrl | None = None

    retrieved_at: datetime | None = None
    last_verified_at: datetime | None = None
    verification_status: LegalVerificationStatus = LegalVerificationStatus.UNKNOWN

    #: Set when the entry is a placeholder in the source registry that no one
    #: has populated from the authority yet. Such entries are never quoted.
    content_available: bool = True

    @model_validator(mode="after")
    def _period_ordered(self) -> LegalFact:
        if self.effective_from and self.effective_to and self.effective_from > self.effective_to:
            raise ValueError("effective_from must not be after effective_to")
        return self

    def in_effect(self, on: date | None = None) -> bool:
        """Whether the fact applies on a given date. Unknown bounds mean open-ended."""
        day = on or date.today()
        started = not self.effective_from or day >= self.effective_from
        not_ended = not self.effective_to or day <= self.effective_to
        return started and not_ended

    def effective_status(
        self, *, max_age: timedelta, now: datetime | None = None, on: date | None = None
    ) -> LegalVerificationStatus:
        """The status to act on, after applying the freshness horizon.

        A stored VERIFIED does not stay VERIFIED forever. If nobody has
        re-checked the source within ``max_age``, or the fact's own effective
        period has ended, this returns EXPIRED/NEEDS_REVIEW - and the answer
        layer then declines rather than repeating a number that may have moved.
        """
        if not self.content_available:
            return LegalVerificationStatus.UNKNOWN
        if not self.in_effect(on):
            return LegalVerificationStatus.EXPIRED
        reference = self.last_verified_at or self.retrieved_at
        if reference is None:
            return LegalVerificationStatus.UNKNOWN
        if (now or utcnow()) - reference > max_age:
            return LegalVerificationStatus.NEEDS_REVIEW
        return self.verification_status

    def trust(self, *, max_age: timedelta, now: datetime | None = None) -> TrustLabel:
        return {
            LegalVerificationStatus.VERIFIED: TrustLabel.VERIFIED,
            LegalVerificationStatus.NEEDS_REVIEW: TrustLabel.NEEDS_REVIEW,
            LegalVerificationStatus.EXPIRED: TrustLabel.OUTDATED,
            LegalVerificationStatus.UNKNOWN: TrustLabel.UNKNOWN,
        }[self.effective_status(max_age=max_age, now=now)]


class KnowledgeDocument(BaseModel):
    """A source document in the retrieval corpus."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    source_name: str
    source_url: HttpUrl | None = None
    jurisdiction: str = "DE"
    topic: LegalCategory
    #: The year the content describes, which is not the year it was fetched.
    effective_year: int | None = None
    retrieved_at: datetime | None = None
    #: False for registry entries awaiting ingestion from the authority.
    content_available: bool = True
    checksum: str | None = None


class KnowledgeChunk(BaseModel):
    """A retrievable passage. Metadata travels with it so citations are exact."""

    model_config = ConfigDict(extra="forbid")

    id: str
    document_id: str
    ordinal: int
    text: str

    source_name: str
    source_url: HttpUrl | None = None
    title: str
    jurisdiction: str = "DE"
    topic: LegalCategory
    effective_year: int | None = None
    retrieved_at: datetime | None = None


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_name: str
    source_url: HttpUrl | None = None
    title: str
    chunk_id: str
    effective_year: int | None = None
    retrieved_at: datetime | None = None
    #: The passage actually relied on, so a reader can check the claim without
    #: leaving the page.
    excerpt: str


class CitedAnswer(BaseModel):
    """An answer that cannot exist without its sources.

    ``citations`` is validated non-empty whenever ``answered`` is True. That is
    the mechanism behind the product rule "do not answer a regulatory question
    from model memory": there is no way to construct a positive answer object
    without having retrieved something to point at.
    """

    model_config = ConfigDict(extra="forbid")

    question: str
    answered: bool
    #: Empty when ``answered`` is False; the refusal text is in ``refusal``.
    answer: str = ""
    citations: list[Citation] = Field(default_factory=list)
    facts_used: list[str] = Field(default_factory=list)
    #: Populated when retrieval succeeded but the underlying facts are past
    #: their review horizon. The UI shows this above the answer.
    staleness_warnings: list[str] = Field(default_factory=list)
    refusal: str | None = None
    #: Things the user should verify with an actual adviser or authority. Always
    #: concrete questions, never a generic "consult a professional".
    questions_to_verify: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _answers_are_cited(self) -> CitedAnswer:
        if self.answered and not self.citations:
            raise ValueError("an answered response must carry at least one citation")
        if not self.answered and not self.refusal:
            raise ValueError("an unanswered response must explain why")
        return self

    @classmethod
    def refuse(cls, question: str, reason: str) -> CitedAnswer:
        return cls(question=question, answered=False, refusal=reason)


class GermanyCheck(BaseModel):
    """Opportunity-specific administrative context.

    Every item is a *consideration* or a *question*, never a determination. The
    module does not compute a tax amount, does not classify the user's activity
    as freiberuflich or gewerblich, and says so - because that classification
    turns on facts the product cannot see and is contested even between tax
    offices.
    """

    model_config = ConfigDict(extra="forbid")

    opportunity_id: str
    #: "This may constitute self-employed activity", etc.
    considerations: list[str] = Field(default_factory=list)
    questions_to_check: list[str] = Field(default_factory=list)
    #: Extra guidance shown only when the user has explicitly disclosed benefit
    #: receipt. Never triggered by inference.
    benefit_notes: list[str] = Field(default_factory=list)
    #: Relevant employment-contract considerations when the user is an employee.
    employment_notes: list[str] = Field(default_factory=list)
    official_sources: list[Citation] = Field(default_factory=list)
    facts_referenced: list[str] = Field(default_factory=list)
    #: True when one or more referenced facts are past their review horizon.
    needs_verification: bool = False
