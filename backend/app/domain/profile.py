"""The user profile and the skills graph.

Two rules shape this module and are enforced by types rather than by convention:

1. **Nothing sensitive is inferred.** Work status, benefit receipt and tax
   registration are :class:`~app.domain.enums.Tristate` /
   :class:`~app.domain.enums.BenefitDisclosure` with an explicit UNKNOWN, and
   the extractor is forbidden from populating them. A product that guesses "you
   are probably on unemployment benefit" from a CV gap would be both wrong and
   an insult.
2. **Inferred skills stay labelled inferred.** :class:`Skill` records its
   :class:`~app.domain.enums.SkillEvidence`, and matching treats a skill the
   user has never confirmed as weaker evidence than one they have - see
   :func:`app.services.matching.score_skill_fit`.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.domain.enums import (
    BenefitDisclosure,
    IncomePreference,
    LanguageLevel,
    RemoteType,
    SchedulePreference,
    SkillEvidence,
    SkillLevel,
    Tristate,
    WorkStatus,
)
from app.domain.evidence import utcnow


def normalise_skill_name(raw: str) -> str:
    """Canonical key for a skill.

    Case-folded and whitespace-collapsed so "Python ", "python" and "PYTHON"
    are one node in the graph. Punctuation is kept: "C++" and "C" are not the
    same skill, and stripping symbols would merge them.
    """
    return " ".join(raw.strip().lower().split())


class Skill(BaseModel):
    """One node in the user's skills graph."""

    model_config = ConfigDict(extra="forbid")

    name: str
    #: Case-folded key used for matching and de-duplication.
    key: str = ""
    level: SkillLevel = SkillLevel.UNKNOWN
    years: float | None = Field(default=None, ge=0, le=70)
    evidence: SkillEvidence = SkillEvidence.USER_STATED
    #: Skills this one implies. Populated from a curated map, never by a model,
    #: so "Python" cannot silently become "machine learning".
    related: list[str] = Field(default_factory=list)
    #: True once the user has seen and kept it in the review step. Inferred
    #: skills start False and are visibly marked in the UI until confirmed.
    confirmed: bool = False

    def model_post_init(self, _context: object) -> None:
        if not self.key:
            object.__setattr__(self, "key", normalise_skill_name(self.name))

    @property
    def is_inferred(self) -> bool:
        return self.evidence is SkillEvidence.INFERRED


class Language(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=2, max_length=5, description="ISO 639-1, e.g. 'de', 'en'.")
    level: LanguageLevel = LanguageLevel.UNKNOWN

    @field_validator("code")
    @classmethod
    def _lower(cls, value: str) -> str:
        return value.strip().lower()


class Education(BaseModel):
    model_config = ConfigDict(extra="forbid")

    qualification: str
    institution: str | None = None
    field_of_study: str | None = None
    completed_year: int | None = Field(default=None, ge=1940, le=2100)


class Certification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    issuer: str | None = None
    issued_year: int | None = Field(default=None, ge=1940, le=2100)
    expires: date | None = None


class GeneralInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = None
    city: str | None = None
    #: German Bundesland. Free text rather than an enum so the model is not the
    #: reason an expansion market fails to onboard.
    federal_state: str | None = None
    country: str = "DE"


class ProfessionalInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_role: str | None = None
    years_experience: float | None = Field(default=None, ge=0, le=70)
    skills: list[Skill] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    portfolio_url: HttpUrl | None = None

    def skill_keys(self) -> set[str]:
        return {s.key for s in self.skills}

    def confirmed_skill_keys(self) -> set[str]:
        return {s.key for s in self.skills if s.confirmed or not s.is_inferred}

    def language_level(self, code: str) -> LanguageLevel:
        for language in self.languages:
            if language.code == code.lower():
                return language.level
        return LanguageLevel.UNKNOWN


class IncomeInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_primary_income_type: str | None = None
    #: The headline goal, in cents per month. The Money Map measures against it.
    desired_additional_monthly_minor: int | None = Field(default=None, ge=0)
    #: Below this, an opportunity is not worth the user's time. Used as a SOFT
    #: signal, never a hard filter: an unpublished amount must not be discarded
    #: for failing a threshold it was never measured against.
    minimum_worthwhile_minor: int | None = Field(default=None, ge=0)
    preference: IncomePreference = IncomePreference.NO_PREFERENCE


class TimeInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hours_per_week: float | None = Field(default=None, ge=0, le=80)
    schedule: SchedulePreference = SchedulePreference.UNKNOWN
    remote_preference: RemoteType = RemoteType.UNKNOWN
    willing_to_travel: Tristate = Tristate.UNKNOWN


class AdminContext(BaseModel):
    """Optional German administrative context.

    Every field defaults to UNKNOWN and is only ever set by the user. The
    Germany Check reads these to decide which questions to raise; it never
    infers them, and an UNKNOWN produces a question rather than an assumption.
    """

    model_config = ConfigDict(extra="forbid")

    has_gewerbe: Tristate = Tristate.UNKNOWN
    has_freelance_tax_registration: Tristate = Tristate.UNKNOWN
    knows_employer_nebentaetigkeit_rules: Tristate = Tristate.UNKNOWN
    #: Explicit disclosure only. Never derived from work status or CV gaps.
    receives_employment_benefits: BenefitDisclosure = BenefitDisclosure.UNKNOWN


class UserProfile(BaseModel):
    """The confirmed profile. Discovery runs against this, never against a draft."""

    model_config = ConfigDict(extra="forbid")

    user_id: str
    general: GeneralInfo = Field(default_factory=GeneralInfo)
    professional: ProfessionalInfo = Field(default_factory=ProfessionalInfo)
    income: IncomeInfo = Field(default_factory=IncomeInfo)
    time: TimeInfo = Field(default_factory=TimeInfo)
    work_status: WorkStatus = WorkStatus.UNKNOWN
    admin: AdminContext = Field(default_factory=AdminContext)

    #: False until the user has reviewed extracted data. Discovery refuses to
    #: run on an unconfirmed profile, so nothing a model guessed can reach a
    #: recommendation without a human having looked at it.
    confirmed: bool = False
    confirmed_at: datetime | None = None
    updated_at: datetime = Field(default_factory=utcnow)

    def completeness(self) -> float:
        """Fraction of the fields that drive matching which are populated.

        Weighted by what actually changes a score: skills and availability move
        the ranking far more than a portfolio URL, so the metric reflects that
        rather than counting fields evenly.
        """
        checks: list[tuple[float, bool]] = [
            (3.0, bool(self.professional.skills)),
            (2.0, self.professional.years_experience is not None),
            (2.0, self.time.hours_per_week is not None),
            (2.0, self.income.desired_additional_monthly_minor is not None),
            (1.5, bool(self.professional.languages)),
            (1.5, bool(self.general.city or self.general.federal_state)),
            (1.0, self.work_status is not WorkStatus.UNKNOWN),
            (1.0, bool(self.professional.current_role)),
            (1.0, self.time.remote_preference is not RemoteType.UNKNOWN),
            (0.5, bool(self.professional.industries)),
            (0.5, bool(self.professional.education)),
        ]
        total = sum(weight for weight, _ in checks)
        got = sum(weight for weight, present in checks if present)
        return round(got / total, 3)

    def is_ready_for_discovery(self) -> tuple[bool, list[str]]:
        """Whether a useful search can be planned, and what is missing if not."""
        missing: list[str] = []
        if not self.professional.skills:
            missing.append("at least one skill")
        if self.time.hours_per_week is None:
            missing.append("hours available per week")
        if self.income.desired_additional_monthly_minor is None:
            missing.append("a monthly income goal")
        return (not missing and self.confirmed), missing


class ProfileDraft(BaseModel):
    """Model-extracted profile awaiting human review.

    Structurally identical to a profile minus the identity, and deliberately a
    separate type: it is impossible to pass a draft where the matching engine
    expects a confirmed profile, which is the whole point.
    """

    model_config = ConfigDict(extra="forbid")

    general: GeneralInfo = Field(default_factory=GeneralInfo)
    professional: ProfessionalInfo = Field(default_factory=ProfessionalInfo)
    #: Fields the extractor could not establish. Surfaced in the review UI as
    #: empty inputs with an explanation, never quietly defaulted.
    not_found: list[str] = Field(default_factory=list)
    #: Free-text notes from extraction, e.g. "two roles overlap in 2021".
    extraction_notes: list[str] = Field(default_factory=list)
