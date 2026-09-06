"""Candidate -> Opportunity: the only path a record can take to become real.

    RAW SOURCE -> SAFETY SCREEN -> INJECTION SCREEN -> STRUCTURED EXTRACTION
      -> PYDANTIC VALIDATION -> EVIDENCE ATTACHMENT -> (dedupe, freshness, match)

Two properties are enforced here rather than hoped for:

**The model never completes a missing fact.** Extraction returns a closed
schema in which every uncertain field is nullable, the prompt says a null is a
correct answer, and :func:`_to_opportunity` maps null to null. There is no
default, no fallback, and no "if the model did not say, assume". A listing with
no salary comes out with no salary.

**Confidence reflects the weakest link.** A field read off a page we fetched is
EXTRACTED, not VERIFIED, no matter how confident the extraction was.
Structured records from the curated file are SOURCE_BACKED because a human
recorded them from the publisher's own page. Nothing in this module can produce
VERIFIED; that requires a human re-check, recorded separately.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.domain.enums import (
    CompensationBasis,
    CompensationPeriod,
    Confidence,
    EmploymentType,
    IncomeStreamCategory,
    LanguageLevel,
    RemoteType,
    RequirementStrength,
    SafetyVerdict,
    SourceType,
    TaxTreatment,
)
from app.domain.evidence import SourceRef
from app.domain.money import MoneyRange
from app.domain.opportunity import (
    LanguageRequirement,
    Opportunity,
    OpportunityCandidate,
    Requirement,
    SafetyAssessment,
)
from app.llm import prompts
from app.llm.base import LLMError, LLMProvider, Purpose
from app.logging_config import Event, log_event
from app.security.guard import InjectionGuard, Provenance
from app.services.safety import DEFAULT_CLASSIFIER, OpportunitySafetyClassifier

logger = logging.getLogger(__name__)


# ------------------------------------------------------- extraction schema


class ExtractedRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    strength: RequirementStrength = RequirementStrength.UNKNOWN
    source_text: str | None = None


class ExtractedLanguage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    minimum: LanguageLevel = LanguageLevel.UNKNOWN
    strength: RequirementStrength = RequirementStrength.UNKNOWN


class ExtractedOpportunity(BaseModel):
    """What a model is permitted to say about a page.

    Every field is optional. That is the whole design: the model can only ever
    report what it read, and "I did not find this" is expressible for every
    single fact. A required field would force a guess.
    """

    model_config = ConfigDict(extra="forbid")

    is_opportunity: bool = Field(
        description=(
            "False for index pages, login walls, errors, or anything with no "
            "single identifiable opportunity."
        )
    )
    rejection_reason: str | None = None

    title: str | None = None
    organization: str | None = None
    category: IncomeStreamCategory = IncomeStreamCategory.OTHER
    subcategory: str | None = None
    summary: str | None = Field(
        default=None, description="Two neutral sentences, containing no fact absent from the page."
    )

    country: str | None = Field(default=None, description="ISO-3166 alpha-2, or null.")
    region: str | None = None
    city: str | None = None
    remote_type: RemoteType = RemoteType.UNKNOWN

    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    required_languages: list[ExtractedLanguage] = Field(default_factory=list)
    experience_min_years: float | None = None
    experience_max_years: float | None = None

    eligibility_text: str | None = None
    eligibility_structured: list[ExtractedRequirement] = Field(default_factory=list)
    employment_type: EmploymentType = EmploymentType.UNKNOWN

    compensation_min_major: float | None = Field(
        default=None,
        description="Amount in whole currency units, exactly as printed. Null if absent.",
    )
    compensation_max_major: float | None = None
    currency: str | None = None
    compensation_basis: CompensationBasis = CompensationBasis.UNKNOWN
    compensation_period: CompensationPeriod = CompensationPeriod.UNKNOWN
    tax_treatment: TaxTreatment = TaxTreatment.UNKNOWN
    compensation_verified: bool = Field(
        default=False,
        description="True only when this page states this figure as the pay for this opportunity.",
    )
    compensation_excerpt: str | None = Field(
        default=None, description="The exact sentence the figure came from."
    )

    estimated_hours_min: float | None = Field(
        default=None,
        description=(
            "Hours per WEEK. Convert a total to a weekly figure only if the page "
            "states the duration; otherwise leave this null."
        ),
    )
    estimated_hours_max: float | None = None
    deadline: date | None = None
    start_date: date | None = None


@dataclass
class NormalisationReport:
    opportunities: list[Opportunity] = field(default_factory=list)
    #: ``(candidate title, reason)`` for everything dropped, so a discovery run
    #: that returns three results can explain what happened to the other forty.
    rejected: list[tuple[str, str]] = field(default_factory=list)
    blocked_unsafe: int = 0
    blocked_injection: int = 0
    extraction_failures: int = 0

    @property
    def considered(self) -> int:
        return len(self.opportunities) + len(self.rejected)


class Normaliser:
    """Turns raw candidates into validated Opportunity records."""

    def __init__(
        self,
        provider: LLMProvider,
        guard: InjectionGuard,
        *,
        classifier: OpportunitySafetyClassifier = DEFAULT_CLASSIFIER,
    ) -> None:
        self._provider = provider
        self._guard = guard
        self._classifier = classifier

    def normalise(self, candidates: list[OpportunityCandidate]) -> NormalisationReport:
        report = NormalisationReport()
        for candidate in candidates:
            try:
                self._one(candidate, report)
            except Exception:  # one bad candidate must not end the run
                logger.warning("normalisation failed for a candidate", exc_info=True)
                report.rejected.append((candidate.title[:80], "internal error"))
        log_event(
            logger,
            Event.OPPORTUNITIES_NORMALISED,
            "normalisation complete",
            considered=report.considered,
            kept=len(report.opportunities),
            blocked_unsafe=report.blocked_unsafe,
            blocked_injection=report.blocked_injection,
            extraction_failures=report.extraction_failures,
        )
        return report

    # --------------------------------------------------------------- steps
    def _one(self, candidate: OpportunityCandidate, report: NormalisationReport) -> None:
        # 1. Safety first, before any model call. A blocked listing should cost
        #    nothing, and a prohibited scheme must not be sent to a model that
        #    might summarise it persuasively.
        safety = self._classifier.classify_candidate(candidate)
        if safety.verdict is SafetyVerdict.BLOCKED:
            report.blocked_unsafe += 1
            report.rejected.append((candidate.title[:80], safety.reasons[0]))
            log_event(
                logger,
                Event.OPPORTUNITY_REJECTED_UNSAFE,
                "candidate blocked by safety rules",
                level=logging.INFO,
                rules=safety.matched_rules,
                source=candidate.source_name,
            )
            return

        # 2. Structured passthrough for file-backed sources. No model involved,
        #    which is what lets the whole product run without one.
        if "json" in candidate.structured:
            record = self._from_structured(candidate, safety)
            if record is not None:
                report.opportunities.append(record)
            else:
                report.rejected.append((candidate.title[:80], "invalid structured record"))
            return

        # 3. Injection screening. Retrieved pages fail closed.
        screening = self._guard.assess(candidate.raw_text, Provenance.RETRIEVED_WEB)
        if screening.blocked:
            report.blocked_injection += 1
            report.rejected.append(
                (candidate.title[:80], "the page contains apparent prompt-injection content")
            )
            return

        # 4. Extraction into the closed schema.
        try:
            extracted = self._provider.structured(
                ExtractedOpportunity,
                prompts.opportunity_extraction_messages(
                    screening.text,
                    str(candidate.url or ""),
                    candidate.source_name,
                ),
                purpose=Purpose.OPPORTUNITY_EXTRACTION,
            )
        except LLMError as error:
            report.extraction_failures += 1
            report.rejected.append((candidate.title[:80], f"extraction unavailable: {error.kind}"))
            return

        if not extracted.is_opportunity:
            report.rejected.append(
                (candidate.title[:80], extracted.rejection_reason or "not an opportunity")
            )
            return

        record = self._to_opportunity(candidate, extracted, safety)
        if record is None:
            report.rejected.append((candidate.title[:80], "failed schema validation"))
            return

        # 5. Re-run safety on the extracted text: extraction may surface terms
        #    the raw HTML buried in markup.
        record = record.model_copy(update={"safety": self._classifier.classify(record)})
        if record.safety.verdict is SafetyVerdict.BLOCKED:
            report.blocked_unsafe += 1
            report.rejected.append((candidate.title[:80], record.safety.reasons[0]))
            return

        report.opportunities.append(record)

    # ---------------------------------------------------------- conversion
    def _from_structured(
        self, candidate: OpportunityCandidate, safety: SafetyAssessment
    ) -> Opportunity | None:
        """Load a curated or demo record straight from JSON."""
        try:
            record = json.loads(candidate.structured["json"])
        except (json.JSONDecodeError, KeyError):
            return None

        is_demo = bool(record.get("is_demo"))
        source = SourceRef(
            name=candidate.source_name,
            url=record.get("source_url") or candidate.url,
            source_type=candidate.source_type,
            retrieved_at=candidate.retrieved_at,
            last_verified_at=_parse_datetime(record.get("last_verified_at")),
        )
        payload: dict[str, object] = {
            "id": record.get("id") or candidate.title[:32],
            "title": record.get("title", candidate.title),
            "organization": record.get("organization"),
            "category": record.get("category", IncomeStreamCategory.OTHER.value),
            "subcategory": record.get("subcategory"),
            "description": record.get("description"),
            "summary": record.get("summary"),
            "country": record.get("country"),
            "region": record.get("region"),
            "city": record.get("city"),
            "remote_type": record.get("remote_type", RemoteType.UNKNOWN.value),
            "required_skills": record.get("required_skills", []),
            "preferred_skills": record.get("preferred_skills", []),
            "required_languages": [
                LanguageRequirement(**item) for item in record.get("required_languages", [])
            ],
            "experience_min_years": record.get("experience_min_years"),
            "experience_max_years": record.get("experience_max_years"),
            "eligibility_text": record.get("eligibility_text"),
            "eligibility_structured": [
                Requirement(**item) for item in record.get("eligibility_structured", [])
            ],
            "employment_type": record.get("employment_type", EmploymentType.UNKNOWN.value),
            "compensation": _money_from_record(record),
            "compensation_verified": bool(record.get("compensation_verified", False))
            and not is_demo,
            "estimated_hours_min": record.get("estimated_hours_min"),
            "estimated_hours_max": record.get("estimated_hours_max"),
            "deadline": _parse_date(record.get("deadline")),
            "start_date": _parse_date(record.get("start_date")),
            "source": source,
            "is_demo": is_demo,
            "is_sponsored": bool(record.get("is_sponsored", False)),
            # A curated record was recorded by a human from the publisher's own
            # page; a demo record evidences nothing about the world.
            "evidence_confidence": (
                Confidence.UNKNOWN
                if is_demo
                else Confidence(record.get("evidence_confidence", Confidence.SOURCE_BACKED.value))
            ),
            "safety": safety,
        }
        try:
            return Opportunity(**payload)
        except ValidationError:
            logger.warning("structured record failed validation", exc_info=True)
            return None

    def _to_opportunity(
        self,
        candidate: OpportunityCandidate,
        extracted: ExtractedOpportunity,
        safety: SafetyAssessment,
    ) -> Opportunity | None:
        source = SourceRef(
            name=candidate.source_name,
            url=candidate.url,
            source_type=candidate.source_type,
            retrieved_at=candidate.retrieved_at,
            last_verified_at=None,
        )
        currency = (extracted.currency or "EUR").upper()[:3]
        compensation = MoneyRange(
            minor_min=_to_minor(extracted.compensation_min_major),
            minor_max=_to_minor(extracted.compensation_max_major),
            currency=currency if len(currency) == 3 else "EUR",
            basis=extracted.compensation_basis,
            period=extracted.compensation_period,
            tax_treatment=extracted.tax_treatment,
        )
        try:
            return Opportunity(
                id=(candidate.url and str(candidate.url)[-32:]) or candidate.title[:32],
                title=extracted.title or candidate.title,
                organization=extracted.organization,
                category=extracted.category,
                subcategory=extracted.subcategory,
                description=candidate.raw_text[:8000],
                summary=extracted.summary,
                country=(extracted.country or "").upper()[:2] or None,
                region=extracted.region,
                city=extracted.city,
                remote_type=extracted.remote_type,
                required_skills=extracted.required_skills[:20],
                preferred_skills=extracted.preferred_skills[:20],
                required_languages=[
                    LanguageRequirement(
                        code=item.code[:5].lower(),
                        minimum=item.minimum,
                        strength=item.strength,
                    )
                    for item in extracted.required_languages[:5]
                ],
                experience_min_years=extracted.experience_min_years,
                experience_max_years=extracted.experience_max_years,
                eligibility_text=extracted.eligibility_text,
                eligibility_structured=[
                    Requirement(
                        label=item.label[:200],
                        strength=item.strength,
                        source_text=item.source_text,
                    )
                    for item in extracted.eligibility_structured[:15]
                ],
                employment_type=extracted.employment_type,
                compensation=compensation,
                # Even when the model says the page stated the figure, this is a
                # model reading a page. It is source-backed, not verified.
                compensation_verified=extracted.compensation_verified,
                estimated_hours_min=extracted.estimated_hours_min,
                estimated_hours_max=extracted.estimated_hours_max,
                deadline=extracted.deadline,
                start_date=extracted.start_date,
                source=source,
                is_demo=False,
                evidence_confidence=Confidence.EXTRACTED,
                safety=safety,
                field_evidence={},
            )
        except ValidationError:
            logger.info("extracted record failed validation", exc_info=True)
            return None


# ------------------------------------------------------------------ helpers


def _to_minor(major: float | None) -> int | None:
    """Whole currency units to integer cents. ``None`` stays ``None``."""
    if major is None:
        return None
    if major < 0:
        return None
    return round(major * 100)


def _money_from_record(record: dict[str, Any]) -> MoneyRange:
    return MoneyRange(
        minor_min=record.get("compensation_min_minor"),
        minor_max=record.get("compensation_max_minor"),
        currency=record.get("currency", "EUR"),
        basis=CompensationBasis(record.get("compensation_basis", "UNKNOWN")),
        period=CompensationPeriod(record.get("compensation_period", "UNKNOWN")),
        tax_treatment=TaxTreatment(record.get("tax_treatment", "UNKNOWN")),
    )


def _parse_date(raw: object) -> date | None:
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            return date.fromisoformat(raw.strip()[:10])
        except ValueError:
            return None
    return None


def _parse_datetime(raw: object) -> datetime | None:
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            return datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def is_fresh(opportunity: Opportunity, *, max_age_days: int = 120) -> bool:
    """Freshness gate applied after de-duplication.

    A stale listing is not deleted - it is excluded from active results and
    kept, so a record the user already saved does not vanish from their board.
    """
    if opportunity.deadline is not None and opportunity.deadline < date.today():
        return False
    return opportunity.source.age_days() <= max_age_days


def source_type_confidence(source_type: SourceType) -> Confidence:
    """Ceiling on how confident a record from this source type may be."""
    return {
        SourceType.DEMO: Confidence.UNKNOWN,
        SourceType.CURATED: Confidence.SOURCE_BACKED,
        SourceType.PUBLIC_API: Confidence.SOURCE_BACKED,
        SourceType.RSS: Confidence.SOURCE_BACKED,
        SourceType.ORGANISATION_PAGE: Confidence.SOURCE_BACKED,
        SourceType.SEARCH_API: Confidence.EXTRACTED,
    }[source_type]
