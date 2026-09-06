"""CV text -> a profile draft the user reviews before anything uses it.

Two things about this module are load-bearing for the product's promises.

**The output is a draft, not a profile.** :class:`~app.domain.profile.ProfileDraft`
is a different type from :class:`~app.domain.profile.UserProfile`, and discovery
takes the latter. It is therefore impossible - not merely discouraged - for
model-extracted data to reach a recommendation without a human confirming it.

**Sensitive fields are absent from the extraction schema entirely.** Work
status, benefit receipt, tax registration, age, nationality and family
situation cannot be extracted, because there are no fields for them here. A
prompt instruction not to infer them would be a request; their absence from the
schema is a guarantee. The product asks for them explicitly instead, and
accepts UNKNOWN as an answer.

Everything the extractor could not establish is returned in ``not_found`` and
rendered as an empty input with an explanation, rather than quietly defaulted.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import LanguageLevel, SkillEvidence, SkillLevel
from app.domain.profile import (
    Certification,
    Education,
    GeneralInfo,
    Language,
    ProfessionalInfo,
    ProfileDraft,
    Skill,
    normalise_skill_name,
)
from app.llm import prompts
from app.llm.base import LLMError, LLMProvider, Purpose
from app.logging_config import Event, log_event, redact_text
from app.security.guard import InjectionGuard, Provenance
from app.services.skills_graph import enrich, implied_skills

logger = logging.getLogger(__name__)

MAX_CV_CHARS = 30_000


class ExtractedSkill(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(max_length=80)
    level: SkillLevel = SkillLevel.UNKNOWN
    years: float | None = Field(default=None, ge=0, le=70)
    #: CV when the document names it; INFERRED when it is implied by a project
    #: or role description. Never USER_STATED - the user has not said it yet.
    evidence: SkillEvidence = SkillEvidence.CV


class ExtractedLanguage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(max_length=5, description="ISO 639-1, lowercase.")
    level: LanguageLevel = LanguageLevel.UNKNOWN


class ExtractedEducation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    qualification: str = Field(max_length=200)
    institution: str | None = None
    field_of_study: str | None = None
    completed_year: int | None = Field(default=None, ge=1940, le=2100)


class ExtractedCertification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(max_length=200)
    issuer: str | None = None
    issued_year: int | None = Field(default=None, ge=1940, le=2100)


class ExtractedProfile(BaseModel):
    """The closed schema a CV may be read into.

    Note the fields that do *not* exist: employment status, benefits, tax
    registration, date of birth, nationality, marital status, health. They are
    not omitted by instruction - there is nowhere to put them.
    """

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = None
    city: str | None = None
    federal_state: str | None = None
    country: str | None = Field(default=None, max_length=2)

    current_role: str | None = None
    years_experience: float | None = Field(
        default=None, ge=0, le=70,
        description="Only if the CV allows it to be counted. Null if roles are undated.",
    )
    skills: list[ExtractedSkill] = Field(default_factory=list, max_length=40)
    industries: list[str] = Field(default_factory=list, max_length=10)
    education: list[ExtractedEducation] = Field(default_factory=list, max_length=10)
    certifications: list[ExtractedCertification] = Field(default_factory=list, max_length=15)
    languages: list[ExtractedLanguage] = Field(default_factory=list, max_length=10)
    portfolio_url: str | None = None

    not_found: list[str] = Field(
        default_factory=list,
        description="Fields you could not establish from this document.",
    )
    extraction_notes: list[str] = Field(
        default_factory=list,
        description="Ambiguities worth showing the user, e.g. overlapping roles.",
    )


class CvParsingUnavailableError(RuntimeError):
    """No model is available. The caller offers manual entry instead."""


class CvParser:
    def __init__(self, provider: LLMProvider, guard: InjectionGuard) -> None:
        self._provider = provider
        self._guard = guard

    def parse(self, cv_text: str) -> ProfileDraft:
        """Extract a reviewable draft, or raise :class:`CvParsingUnavailableError`.

        Raising rather than returning an empty draft matters: an empty draft
        looks like "your CV had nothing in it", which is a false statement about
        the user's document. The caller shows "we could not analyse this right
        now - you can enter your details manually" instead.
        """
        if not self._provider.available:
            raise CvParsingUnavailableError(
                "CV analysis is unavailable because no language model is configured."
            )

        log_event(logger, Event.CV_EXTRACTION_STARTED, "extracting profile", **redact_text(cv_text))

        # The CV is the user's own document: screened and fenced, never blocked.
        # A CV that trips an injection heuristic is far more likely to be a
        # security engineer's CV than an attack.
        screening = self._guard.assess(cv_text[:MAX_CV_CHARS], Provenance.UPLOADED_FILE)
        notes: list[str] = []
        if screening.suspicious:
            notes.append(
                "This document contains text that looks like instructions to an AI system. "
                "It was treated as ordinary document content and had no effect."
            )

        try:
            extracted = self._provider.structured(
                ExtractedProfile,
                prompts.cv_extraction_messages(screening.text),
                purpose=Purpose.CV_EXTRACTION,
            )
        except LLMError as error:
            raise CvParsingUnavailableError(
                "We could not analyse your CV right now. Your file is safe, and you "
                "can enter your details manually."
            ) from error

        draft = _to_draft(extracted, extra_notes=notes)
        log_event(
            logger,
            Event.CV_EXTRACTION_COMPLETED,
            "profile draft produced",
            skill_count=len(draft.professional.skills),
            not_found=len(draft.not_found),
        )
        return draft


def _to_draft(extracted: ExtractedProfile, *, extra_notes: list[str]) -> ProfileDraft:
    skills = [
        Skill(
            name=item.name.strip(),
            key=normalise_skill_name(item.name),
            level=item.level,
            years=item.years,
            evidence=item.evidence,
            # Nothing arrives confirmed. The review step is where confirmation
            # happens, and it is the user who does it.
            confirmed=False,
        )
        for item in extracted.skills
        if item.name.strip()
    ]
    # Deduplicate on the folded key, keeping the strongest evidence.
    unique: dict[str, Skill] = {}
    for skill in skills:
        existing = unique.get(skill.key)
        if existing is None or (
            existing.evidence is SkillEvidence.INFERRED and skill.evidence is SkillEvidence.CV
        ):
            unique[skill.key] = skill

    confirmed_like = [s for s in unique.values() if s.evidence is SkillEvidence.CV]
    suggestions = [s for s in implied_skills(confirmed_like) if s.key not in unique]

    professional = ProfessionalInfo(
        current_role=extracted.current_role,
        years_experience=extracted.years_experience,
        skills=enrich(list(unique.values()) + suggestions),
        industries=[i.strip() for i in extracted.industries if i.strip()],
        education=[
            Education(
                qualification=item.qualification,
                institution=item.institution,
                field_of_study=item.field_of_study,
                completed_year=item.completed_year,
            )
            for item in extracted.education
        ],
        certifications=[
            Certification(
                name=item.name, issuer=item.issuer, issued_year=item.issued_year
            )
            for item in extracted.certifications
        ],
        languages=[
            Language(code=item.code.lower(), level=item.level)
            for item in extracted.languages
            if len(item.code.strip()) >= 2
        ],
        portfolio_url=_safe_url(extracted.portfolio_url),
    )

    not_found = list(extracted.not_found)
    # Everything the product needs but a CV never contains. Listing these makes
    # the onboarding review honest about what still has to be answered.
    for label, present in (
        ("weekly availability", False),
        ("income goal", False),
        ("work status", False),
    ):
        if not present and label not in not_found:
            not_found.append(label)

    return ProfileDraft(
        general=GeneralInfo(
            display_name=extracted.display_name,
            city=extracted.city,
            federal_state=extracted.federal_state,
            country=(extracted.country or "DE").upper()[:2],
        ),
        professional=professional,
        not_found=not_found,
        extraction_notes=[*extra_notes, *extracted.extraction_notes],
    )


def _safe_url(raw: str | None) -> str | None:
    """Only accept an http(s) URL. A CV can contain anything."""
    if not raw:
        return None
    candidate = raw.strip()
    if not candidate.startswith(("http://", "https://")):
        return None
    return candidate[:500]


def draft_from_text(text: str) -> ProfileDraft:
    """The no-model path: keep the pasted text for the user to work from.

    Deliberately extracts nothing. A regex CV parser produces confident
    nonsense - mistaking a company for a job title, a postcode for a year - and
    the user then has to find and correct each error, which is worse than
    typing the fields themselves.
    """
    return ProfileDraft(
        general=GeneralInfo(),
        professional=ProfessionalInfo(),
        not_found=["everything - automatic extraction is unavailable"],
        extraction_notes=[
            "AI-assisted extraction is unavailable, so nothing was filled in "
            "automatically. Your text is below; please fill in the fields you "
            "want us to use.",
            text[:4000],
        ],
    )
