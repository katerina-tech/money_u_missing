"""Wire types.

Separate from the domain models on purpose. The API is a contract with a
frontend that ships independently, and coupling it directly to internal types
means a refactor becomes a breaking change. It also lets the response types
carry presentation-level honesty - ``trust``, ``unknown``, ``exclusions`` - that
the domain models express structurally but a JSON consumer needs spelled out.

Money crosses the wire as integer minor units with the currency alongside,
never as a formatted string and never as a float.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.domain.enums import (
    ActionabilityBand,
    ApplicationStatus,
    BenefitDisclosure,
    DismissReason,
    FinancialGoalType,
    IncomePreference,
    IncomeStreamCategory,
    LanguageLevel,
    RemoteType,
    SchedulePreference,
    SkillEvidence,
    SkillLevel,
    Tristate,
    TrustLabel,
    WorkStatus,
)


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# =============================================================== identity


class SignupRequest(ApiModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=1024)
    #: Explicit, recorded consent. Required to create an account.
    accept_privacy: bool = Field(description="Must be true. Recorded in consent_records.")


class LoginRequest(ApiModel):
    email: EmailStr
    password: str = Field(max_length=1024)


class RefreshRequest(ApiModel):
    refresh_token: str


class TokenResponse(ApiModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str
    email: str | None = None
    is_demo: bool = False


# ================================================================ profile


class SkillDto(ApiModel):
    name: str
    key: str = ""
    level: SkillLevel = SkillLevel.UNKNOWN
    years: float | None = None
    evidence: SkillEvidence = SkillEvidence.USER_STATED
    related: list[str] = Field(default_factory=list)
    #: Inferred skills arrive False and must be confirmed by the user before
    #: they count at full weight in matching.
    confirmed: bool = False


class LanguageDto(ApiModel):
    code: str
    level: LanguageLevel = LanguageLevel.UNKNOWN


class EducationDto(ApiModel):
    qualification: str
    institution: str | None = None
    field_of_study: str | None = None
    completed_year: int | None = None


class CertificationDto(ApiModel):
    name: str
    issuer: str | None = None
    issued_year: int | None = None


class ProfileDto(ApiModel):
    display_name: str | None = None
    city: str | None = None
    federal_state: str | None = None
    country: str = "DE"

    current_role: str | None = None
    years_experience: float | None = None
    skills: list[SkillDto] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    education: list[EducationDto] = Field(default_factory=list)
    certifications: list[CertificationDto] = Field(default_factory=list)
    languages: list[LanguageDto] = Field(default_factory=list)
    portfolio_url: str | None = None

    current_primary_income_type: str | None = None
    desired_additional_monthly_minor: int | None = None
    minimum_worthwhile_minor: int | None = None
    income_preference: IncomePreference = IncomePreference.NO_PREFERENCE

    hours_per_week: float | None = None
    schedule_preference: SchedulePreference = SchedulePreference.UNKNOWN
    remote_preference: RemoteType = RemoteType.UNKNOWN
    willing_to_travel: Tristate = Tristate.UNKNOWN

    work_status: WorkStatus = WorkStatus.UNKNOWN

    has_gewerbe: Tristate = Tristate.UNKNOWN
    has_freelance_tax_registration: Tristate = Tristate.UNKNOWN
    knows_employer_rules: Tristate = Tristate.UNKNOWN
    receives_employment_benefits: BenefitDisclosure = BenefitDisclosure.UNKNOWN

    confirmed: bool = False
    completeness: float = 0.0
    currency: str = "EUR"


class ProfileDraftResponse(ApiModel):
    """What extraction produced, for the user to review before anything uses it."""

    draft: ProfileDto
    #: Fields the extractor could not establish. Rendered as empty inputs with
    #: an explanation, never silently defaulted.
    not_found: list[str] = Field(default_factory=list)
    extraction_notes: list[str] = Field(default_factory=list)
    inferred_skill_count: int = 0
    source: str = Field(description="upload | paste | manual")


class PasteProfileRequest(ApiModel):
    text: str = Field(min_length=1, max_length=60_000)
    consent_to_process: bool = Field(
        description="Must be true. Processing CV content requires specific consent."
    )


# =========================================================== opportunities


class MoneyDto(ApiModel):
    minor_min: int | None = None
    minor_max: int | None = None
    currency: str = "EUR"
    basis: str = "UNKNOWN"
    period: str = "UNKNOWN"
    tax_treatment: str = "UNKNOWN"
    #: True only when the source page states the figure.
    verified: bool = False
    #: Rendered when nothing is known, so the UI never shows an empty money slot.
    unknown_note: str | None = None


class RequirementDto(ApiModel):
    label: str
    strength: str
    source_text: str | None = None


class ScoreComponentDto(ApiModel):
    name: str
    score: float
    weight: float
    detail: str
    was_unknown: bool = False


class MatchDto(ApiModel):
    total_score: int
    eligible: bool
    components: list[ScoreComponentDto] = Field(default_factory=list)
    hard_failures: list[dict[str, Any]] = Field(default_factory=list)
    uncertainties: list[dict[str, Any]] = Field(default_factory=list)
    explanation_inputs: list[str] = Field(default_factory=list)
    #: Model-written prose, present only when a model was available. The UI
    #: labels it as AI-written; the bullets above are the source of truth.
    explanation: str | None = None
    weights_version: str = "v1"


class ActionabilityDto(ApiModel):
    score: int
    band: ActionabilityBand
    headline_reason: str
    factors: list[dict[str, Any]] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)


class OpportunitySummaryDto(ApiModel):
    id: str
    title: str
    organization: str | None = None
    category: IncomeStreamCategory
    remote_type: RemoteType
    city: str | None = None
    country: str | None = None
    compensation: MoneyDto
    estimated_hours_min: float | None = None
    estimated_hours_max: float | None = None
    deadline: date | None = None
    trust: TrustLabel
    is_demo: bool
    is_sponsored: bool = False
    safety_verdict: str = "ALLOWED"
    safety_reasons: list[str] = Field(default_factory=list)
    source_name: str
    source_url: str | None = None
    last_seen_days_ago: int
    match: MatchDto | None = None
    actionability: ActionabilityDto | None = None
    saved: bool = False
    application_status: ApplicationStatus | None = None


class OpportunityDetailDto(OpportunitySummaryDto):
    description: str | None = None
    summary: str | None = None
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    eligibility_text: str | None = None
    eligibility_structured: list[RequirementDto] = Field(default_factory=list)
    experience_min_years: float | None = None
    experience_max_years: float | None = None
    employment_type: str = "UNKNOWN"
    #: The two panels that carry the product's honesty. Never empty by accident:
    #: an opportunity with nothing unknown is one we verified completely.
    what_we_know: list[str] = Field(default_factory=list)
    what_we_dont_know: list[str] = Field(default_factory=list)
    corroborating_sources: list[dict[str, Any]] = Field(default_factory=list)
    germany_check: GermanyCheckDto | None = None


class GermanyCheckDto(ApiModel):
    considerations: list[str] = Field(default_factory=list)
    questions_to_check: list[str] = Field(default_factory=list)
    employment_notes: list[str] = Field(default_factory=list)
    benefit_notes: list[str] = Field(default_factory=list)
    official_sources: list[dict[str, Any]] = Field(default_factory=list)
    needs_verification: bool = False
    disclaimer: str = (
        "Information and questions to check, not tax or legal advice. This product "
        "does not classify your activity and does not calculate tax."
    )


class MoneySummaryDto(ApiModel):
    currency: str = "EUR"
    recurring_potential_monthly_minor: int = 0
    recurring_potential_count: int = 0
    one_time_potential_minor: int = 0
    one_time_potential_count: int = 0
    secured_monthly_minor: int = 0
    secured_one_time_minor: int = 0
    secured_count: int = 0
    earned_total_minor: int = 0
    earned_count: int = 0
    unknown_value_count: int = 0
    unconvertible_count: int = 0
    #: Rendered next to the totals. What was deliberately left out, and why.
    exclusions: list[str] = Field(default_factory=list)


class BestNextMoveDto(ApiModel):
    opportunity_id: str
    title: str
    organization: str | None = None
    reasons: list[str] = Field(default_factory=list)
    call_to_action: str = "PREPARE APPLICATION"
    caveat: str | None = None


class IncomePathDto(ApiModel):
    category: IncomeStreamCategory
    label: str
    opportunity_count: int
    best_match_score: int | None = None
    #: Only present when at least one opportunity in the path publishes a figure.
    indicative_monthly_minor: int | None = None


class DiscoveryDiagnosticsDto(ApiModel):
    """What the run actually did. Shown in the UI, not hidden in a log.

    A search that returns four results must be able to account for the other
    forty, or the user reasonably concludes the product simply is not very good.
    """

    considered: int = 0
    returned: int = 0
    duplicates_removed: int = 0
    stale_removed: int = 0
    blocked_unsafe: int = 0
    blocked_injection: int = 0
    extraction_failures: int = 0
    sources_queried: int = 0
    sources_failed: list[str] = Field(default_factory=list)
    live_search_used: bool = False
    notices: list[str] = Field(default_factory=list)
    plan_rationale: str = ""
    queries: list[str] = Field(default_factory=list)


class MoneyMapResponse(ApiModel):
    greeting: str
    goal_monthly_minor: int | None = None
    currency: str = "EUR"
    summary: MoneySummaryDto
    goal_progress_ratio: float | None = None
    best_next_move: BestNextMoveDto | None = None
    opportunities: list[OpportunitySummaryDto] = Field(default_factory=list)
    income_paths: list[IncomePathDto] = Field(default_factory=list)
    this_week: list[str] = Field(default_factory=list)
    recent_progress: list[str] = Field(default_factory=list)
    diagnostics: DiscoveryDiagnosticsDto = Field(default_factory=DiscoveryDiagnosticsDto)
    is_demo: bool = False


# ================================================================ actions


class SaveOpportunityRequest(ApiModel):
    opportunity_id: str


class DismissRequest(ApiModel):
    opportunity_id: str
    reason: DismissReason
    note: str | None = Field(default=None, max_length=1000)


class TransitionRequest(ApiModel):
    status: ApplicationStatus
    #: Required when moving to WON. The real figure, not the advertised one.
    outcome: OutcomeRequest | None = None


class OutcomeRequest(ApiModel):
    amount_minor: int = Field(ge=0)
    currency: str = "EUR"
    tax_treatment: str = "UNKNOWN"
    period: str = "ONE_TIME"
    hours_spent: float | None = Field(default=None, ge=0)
    occurred_on: date | None = None
    notes: str | None = Field(default=None, max_length=2000)


class ApplicationDto(ApiModel):
    id: str
    opportunity_id: str
    opportunity_title: str
    organization: str | None = None
    status: ApplicationStatus
    money_state: str
    status_history: list[dict[str, str]] = Field(default_factory=list)
    checklist: list[dict[str, Any]] = Field(default_factory=list)
    documents_needed: list[str] = Field(default_factory=list)
    questions_to_verify: list[str] = Field(default_factory=list)
    notes: str | None = None
    drafts: dict[str, str] = Field(default_factory=dict)
    reminder_at: datetime | None = None
    applied_at: datetime | None = None


class WorkspaceUpdateRequest(ApiModel):
    checklist: list[dict[str, Any]] | None = None
    documents_needed: list[str] | None = None
    questions_to_verify: list[str] | None = None
    notes: str | None = Field(default=None, max_length=10_000)
    reminder_at: datetime | None = None


class DraftRequest(ApiModel):
    kind: str = Field(description="bio | cover_letter | pitch | short_answer | outreach")


class DraftResponse(ApiModel):
    kind: str
    text: str
    #: Always true in P0. Nothing is sent anywhere by this system.
    requires_review: bool = True
    note: str = (
        "Review and edit before you send this. It is written from your profile and may "
        "contain gaps you need to fill in honestly."
    )


# ================================================================ keep


class TaxQuestionRequest(ApiModel):
    question: str = Field(min_length=3, max_length=2000)


class CitationDto(ApiModel):
    source_name: str
    source_url: str | None = None
    title: str
    effective_year: int | None = None
    retrieved_at: datetime | None = None
    excerpt: str


class TaxAnswerResponse(ApiModel):
    question: str
    answered: bool
    answer: str = ""
    refusal: str | None = None
    citations: list[CitationDto] = Field(default_factory=list)
    staleness_warnings: list[str] = Field(default_factory=list)
    questions_to_verify: list[str] = Field(default_factory=list)
    disclaimer: str = (
        "Educational information from the sources cited. Not Steuerberatung and not "
        "Rechtsberatung."
    )


class LegalFactDto(ApiModel):
    id: str
    category: str
    title: str
    summary: str
    structured_value: dict[str, Any] = Field(default_factory=dict)
    effective_from: date | None = None
    effective_to: date | None = None
    source_name: str
    source_url: str | None = None
    last_verified_at: datetime | None = None
    trust: TrustLabel
    status: str


# ================================================================ grow


class GoalRequest(ApiModel):
    goal_type: FinancialGoalType
    name: str = Field(max_length=200)
    target_minor: int = Field(ge=0)
    target_date: date | None = None
    current_minor: int = Field(default=0, ge=0)
    monthly_contribution_minor: int = Field(default=0, ge=0)


class GoalDto(GoalRequest):
    id: str
    currency: str = "EUR"
    progress_ratio: float = 0.0
    months_at_current_contribution: int | None = None


class ProjectionRequest(ApiModel):
    initial_minor: int = Field(default=0, ge=0)
    monthly_contribution_minor: int = Field(default=0, ge=0)
    #: The user supplies this. The product never suggests a rate.
    annual_return: float = Field(ge=-0.20, le=0.20)
    months: int = Field(ge=0, le=720)
    annual_inflation: float | None = Field(default=None, ge=-0.10, le=0.20)


class ProjectionResponse(ApiModel):
    initial_minor: int
    monthly_contribution_minor: int
    annual_return: float
    annual_inflation: float | None = None
    months: int
    currency: str = "EUR"
    total_contributed_minor: int
    final_balance_minor: int
    final_real_balance_minor: int | None = None
    growth_minor: int
    points: list[dict[str, Any]] = Field(default_factory=list)
    disclaimer: str


class ChildGoalRequest(ApiModel):
    child_label: str = Field(max_length=80)
    child_age_years: int = Field(ge=0, le=25)
    target_age_years: int = Field(ge=1, le=30)
    target_minor: int = Field(default=0, ge=0)
    current_minor: int = Field(default=0, ge=0)
    monthly_contribution_minor: int = Field(default=0, ge=0)


class ChildGoalDto(ChildGoalRequest):
    id: str
    currency: str = "EUR"
    years_remaining: int


# ============================================================= validation


class FeedbackRequest(ApiModel):
    question: str = Field(
        description="would_not_have_found | would_pursue",
        max_length=64,
    )
    answer: str = Field(max_length=32)
    reason: DismissReason | None = None
    note: str | None = Field(default=None, max_length=2000)
    opportunity_id: str | None = None


# ================================================================ meta


class CapabilityReport(ApiModel):
    """What this deployment can actually do right now.

    The frontend renders honest states from this rather than discovering a
    missing capability when a button fails. It is also how an accelerator jury
    can see exactly which parts are live and which are degraded.
    """

    llm_available: bool
    llm_provider: str
    live_search_available: bool
    search_provider: str
    retrieval_mode: str
    knowledge_documents: int
    knowledge_chunks: int
    legal_facts_verified: int
    legal_facts_total: int
    stale_fact_rate: float | None = None
    demo_mode_enabled: bool
    payments_enabled: bool
    database: str
    pgvector: bool
    degradations: list[str] = Field(default_factory=list)


class SourceProvenanceDto(ApiModel):
    id: str
    name: str
    type: str
    access_basis: str
    enabled: bool
    note: str | None = None


class HealthResponse(ApiModel):
    status: str = "ok"
    version: str = "0.1.0"
    database: bool = True


class ErrorResponse(ApiModel):
    detail: str
    #: Present when the failure is a degradation the user should understand
    #: rather than a bug, e.g. "the model is unavailable, your data is safe".
    recovery: str | None = None


OpportunityDetailDto.model_rebuild()
TransitionRequest.model_rebuild()
