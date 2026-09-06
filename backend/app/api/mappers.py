"""Domain <-> wire and domain <-> row conversion.

Concentrated in one module so a field that must never leave the backend - a
password hash, a stored CV path, the raw text of an uploaded document - has one
place where its absence from the response can be checked.
"""

from __future__ import annotations

import json
from typing import Any

from app.api import dto
from app.db.models import Profile as ProfileRow
from app.db.models import ProfileSkill
from app.domain.enums import (
    BenefitDisclosure,
    CompensationBasis,
    CompensationPeriod,
    Confidence,
    IncomePreference,
    IncomeStreamCategory,
    RemoteType,
    SchedulePreference,
    SkillEvidence,
    SkillLevel,
    TaxTreatment,
    Tristate,
    WorkStatus,
)
from app.domain.legal import GermanyCheck
from app.domain.matching import Actionability, MatchScore
from app.domain.money import MoneyRange
from app.domain.opportunity import Opportunity
from app.domain.profile import (
    AdminContext,
    Certification,
    Education,
    GeneralInfo,
    IncomeInfo,
    Language,
    ProfessionalInfo,
    Skill,
    TimeInfo,
    UserProfile,
    normalise_skill_name,
)

# ============================================================ profile


def profile_row_to_domain(row: ProfileRow, skills: list[ProfileSkill]) -> UserProfile:
    return UserProfile(
        user_id=row.user_id,
        general=GeneralInfo(
            display_name=row.display_name,
            city=row.city,
            federal_state=row.federal_state,
            country=row.country,
        ),
        professional=ProfessionalInfo(
            current_role=row.current_role,
            years_experience=row.years_experience,
            skills=[
                Skill(
                    name=s.name,
                    key=s.key,
                    level=SkillLevel(s.level),
                    years=s.years,
                    evidence=SkillEvidence(s.evidence),
                    related=s.related,
                    confirmed=s.confirmed,
                )
                for s in skills
            ],
            industries=row.industries,
            education=[Education(**item) for item in row.education.get("items", [])],
            certifications=[
                Certification(**item) for item in row.certifications.get("items", [])
            ],
            languages=[Language(**item) for item in row.languages.get("items", [])],
            portfolio_url=row.portfolio_url,
        ),
        income=IncomeInfo(
            current_primary_income_type=row.current_primary_income_type,
            desired_additional_monthly_minor=row.desired_additional_monthly_minor,
            minimum_worthwhile_minor=row.minimum_worthwhile_minor,
            preference=IncomePreference(row.income_preference),
        ),
        time=TimeInfo(
            hours_per_week=row.hours_per_week,
            schedule=SchedulePreference(row.schedule_preference),
            remote_preference=RemoteType(row.remote_preference),
            willing_to_travel=Tristate(row.willing_to_travel),
        ),
        work_status=WorkStatus(row.work_status),
        admin=AdminContext(
            has_gewerbe=Tristate(row.has_gewerbe),
            has_freelance_tax_registration=Tristate(row.has_freelance_tax_registration),
            knows_employer_nebentaetigkeit_rules=Tristate(row.knows_employer_rules),
            receives_employment_benefits=BenefitDisclosure(row.receives_employment_benefits),
        ),
        confirmed=row.confirmed,
        confirmed_at=row.confirmed_at,
        updated_at=row.updated_at,
    )


def profile_to_dto(profile: UserProfile) -> dto.ProfileDto:
    return dto.ProfileDto(
        display_name=profile.general.display_name,
        city=profile.general.city,
        federal_state=profile.general.federal_state,
        country=profile.general.country,
        current_role=profile.professional.current_role,
        years_experience=profile.professional.years_experience,
        skills=[
            dto.SkillDto(
                name=s.name,
                key=s.key,
                level=s.level,
                years=s.years,
                evidence=s.evidence,
                related=s.related,
                confirmed=s.confirmed,
            )
            for s in profile.professional.skills
        ],
        industries=profile.professional.industries,
        education=[dto.EducationDto(**e.model_dump()) for e in profile.professional.education],
        certifications=[
            dto.CertificationDto(
                name=c.name, issuer=c.issuer, issued_year=c.issued_year
            )
            for c in profile.professional.certifications
        ],
        languages=[
            dto.LanguageDto(code=lang.code, level=lang.level)
            for lang in profile.professional.languages
        ],
        portfolio_url=str(profile.professional.portfolio_url)
        if profile.professional.portfolio_url
        else None,
        current_primary_income_type=profile.income.current_primary_income_type,
        desired_additional_monthly_minor=profile.income.desired_additional_monthly_minor,
        minimum_worthwhile_minor=profile.income.minimum_worthwhile_minor,
        income_preference=profile.income.preference,
        hours_per_week=profile.time.hours_per_week,
        schedule_preference=profile.time.schedule,
        remote_preference=profile.time.remote_preference,
        willing_to_travel=profile.time.willing_to_travel,
        work_status=profile.work_status,
        has_gewerbe=profile.admin.has_gewerbe,
        has_freelance_tax_registration=profile.admin.has_freelance_tax_registration,
        knows_employer_rules=profile.admin.knows_employer_nebentaetigkeit_rules,
        receives_employment_benefits=profile.admin.receives_employment_benefits,
        confirmed=profile.confirmed,
        completeness=profile.completeness(),
    )


def apply_profile_dto(row: ProfileRow, payload: dto.ProfileDto) -> None:
    """Write a submitted profile onto its row. Skills are handled separately.

    Every field is taken as given. There is no server-side inference here: if
    the user cleared a value, it is cleared, because the alternative is a
    product that quietly remembers something the user tried to remove.
    """
    row.display_name = payload.display_name
    row.city = payload.city
    row.federal_state = payload.federal_state
    row.country = (payload.country or "DE").upper()[:2]
    row.current_role = payload.current_role
    row.years_experience = payload.years_experience
    row.industries = payload.industries
    row.portfolio_url = payload.portfolio_url
    row.education = {"items": [e.model_dump() for e in payload.education]}
    row.certifications = {"items": [c.model_dump() for c in payload.certifications]}
    row.languages = {
        "items": [
            {"code": lang.code.lower(), "level": lang.level.value}
            for lang in payload.languages
        ]
    }
    row.current_primary_income_type = payload.current_primary_income_type
    row.desired_additional_monthly_minor = payload.desired_additional_monthly_minor
    row.minimum_worthwhile_minor = payload.minimum_worthwhile_minor
    row.income_preference = payload.income_preference.value
    row.hours_per_week = payload.hours_per_week
    row.schedule_preference = payload.schedule_preference.value
    row.remote_preference = payload.remote_preference.value
    row.willing_to_travel = payload.willing_to_travel.value
    row.work_status = payload.work_status.value
    row.has_gewerbe = payload.has_gewerbe.value
    row.has_freelance_tax_registration = payload.has_freelance_tax_registration.value
    row.knows_employer_rules = payload.knows_employer_rules.value
    row.receives_employment_benefits = payload.receives_employment_benefits.value


def skill_dtos_to_rows(profile_id: str, skills: list[dto.SkillDto]) -> list[ProfileSkill]:
    seen: set[str] = set()
    rows: list[ProfileSkill] = []
    for skill in skills:
        key = skill.key or normalise_skill_name(skill.name)
        if not key or key in seen:
            continue
        seen.add(key)
        rows.append(
            ProfileSkill(
                profile_id=profile_id,
                name=skill.name.strip()[:120],
                key=key,
                level=skill.level.value,
                years=skill.years,
                evidence=skill.evidence.value,
                related=skill.related[:8],
                confirmed=skill.confirmed,
            )
        )
    return rows


# ======================================================== opportunities


def money_to_dto(money: MoneyRange, *, verified: bool) -> dto.MoneyDto:
    known = money.known
    return dto.MoneyDto(
        minor_min=money.minor_min,
        minor_max=money.minor_max,
        currency=money.currency,
        basis=money.basis.value,
        period=money.period.value,
        tax_treatment=money.tax_treatment.value,
        verified=verified and known,
        unknown_note=None if known else "The source does not publish what this pays.",
    )


def opportunity_to_summary(
    opportunity: Opportunity,
    *,
    match: MatchScore | None = None,
    actionability: Actionability | None = None,
    explanation: str | None = None,
    saved: bool = False,
    application_status: Any | None = None,
) -> dto.OpportunitySummaryDto:
    return dto.OpportunitySummaryDto(
        id=opportunity.id,
        title=opportunity.title,
        organization=opportunity.organization,
        category=opportunity.category,
        remote_type=opportunity.remote_type,
        city=opportunity.city,
        country=opportunity.country,
        compensation=money_to_dto(
            opportunity.compensation, verified=opportunity.compensation_verified
        ),
        estimated_hours_min=opportunity.estimated_hours_min,
        estimated_hours_max=opportunity.estimated_hours_max,
        deadline=opportunity.deadline,
        trust=opportunity.trust,
        is_demo=opportunity.is_demo,
        is_sponsored=opportunity.is_sponsored,
        safety_verdict=opportunity.safety.verdict.value,
        safety_reasons=opportunity.safety.reasons,
        source_name=opportunity.source.name,
        source_url=str(opportunity.source.url) if opportunity.source.url else None,
        last_seen_days_ago=opportunity.source.age_days(),
        match=match_to_dto(match, explanation) if match else None,
        actionability=actionability_to_dto(actionability) if actionability else None,
        saved=saved,
        application_status=application_status,
    )


def opportunity_to_detail(
    opportunity: Opportunity,
    *,
    match: MatchScore | None = None,
    actionability: Actionability | None = None,
    explanation: str | None = None,
    germany_check: GermanyCheck | None = None,
    saved: bool = False,
    application_status: Any | None = None,
) -> dto.OpportunityDetailDto:
    summary = opportunity_to_summary(
        opportunity,
        match=match,
        actionability=actionability,
        explanation=explanation,
        saved=saved,
        application_status=application_status,
    )
    return dto.OpportunityDetailDto(
        **summary.model_dump(),
        description=opportunity.description,
        summary=opportunity.summary,
        required_skills=opportunity.required_skills,
        preferred_skills=opportunity.preferred_skills,
        eligibility_text=opportunity.eligibility_text,
        eligibility_structured=[
            dto.RequirementDto(
                label=r.label, strength=r.strength.value, source_text=r.source_text
            )
            for r in opportunity.eligibility_structured
        ],
        experience_min_years=opportunity.experience_min_years,
        experience_max_years=opportunity.experience_max_years,
        employment_type=opportunity.employment_type.value,
        what_we_know=opportunity.known_facts(),
        what_we_dont_know=opportunity.unknown_facts(),
        corroborating_sources=[
            {
                "name": source.name,
                "url": str(source.url) if source.url else None,
                "type": source.source_type.value,
            }
            for source in opportunity.corroborating_sources
        ],
        germany_check=germany_check_to_dto(germany_check) if germany_check else None,
    )


def match_to_dto(match: MatchScore, explanation: str | None = None) -> dto.MatchDto:
    return dto.MatchDto(
        total_score=match.total_score,
        eligible=match.eligible,
        components=[
            dto.ScoreComponentDto(
                name=c.name,
                score=c.score,
                weight=c.weight,
                detail=c.detail,
                was_unknown=c.was_unknown,
            )
            for c in match.components
        ],
        hard_failures=[f.model_dump() for f in match.hard_failures],
        uncertainties=[u.model_dump() for u in match.uncertainties],
        explanation_inputs=match.explanation_inputs,
        explanation=explanation,
        weights_version=match.weights_version,
    )


def actionability_to_dto(actionability: Actionability) -> dto.ActionabilityDto:
    return dto.ActionabilityDto(
        score=actionability.score,
        band=actionability.band,
        headline_reason=actionability.headline_reason,
        factors=[f.model_dump() for f in actionability.factors],
        blockers=actionability.blockers,
    )


def germany_check_to_dto(check: GermanyCheck) -> dto.GermanyCheckDto:
    return dto.GermanyCheckDto(
        considerations=check.considerations,
        questions_to_check=check.questions_to_check,
        employment_notes=check.employment_notes,
        benefit_notes=check.benefit_notes,
        official_sources=[
            {
                "source_name": c.source_name,
                "source_url": str(c.source_url) if c.source_url else None,
                "title": c.title,
                "excerpt": c.excerpt,
            }
            for c in check.official_sources
        ],
        needs_verification=check.needs_verification,
    )


# ============================================ opportunity row round-trip


def opportunity_to_row_values(opportunity: Opportunity) -> dict[str, Any]:
    return {
        "fingerprint": opportunity.fingerprint(),
        "title": opportunity.title,
        "organization": opportunity.organization,
        "category": opportunity.category.value,
        "subcategory": opportunity.subcategory,
        "description": opportunity.description,
        "summary": opportunity.summary,
        "country": opportunity.country,
        "region": opportunity.region,
        "city": opportunity.city,
        "remote_type": opportunity.remote_type.value,
        "required_skills": opportunity.required_skills,
        "preferred_skills": opportunity.preferred_skills,
        "required_languages": {
            "items": [lang.model_dump(mode="json") for lang in opportunity.required_languages]
        },
        "experience_min_years": opportunity.experience_min_years,
        "experience_max_years": opportunity.experience_max_years,
        "eligibility_text": opportunity.eligibility_text,
        "eligibility_structured": {
            "items": [r.model_dump(mode="json") for r in opportunity.eligibility_structured]
        },
        "employment_type": opportunity.employment_type.value,
        "compensation_min_minor": opportunity.compensation.minor_min,
        "compensation_max_minor": opportunity.compensation.minor_max,
        "currency": opportunity.compensation.currency,
        "compensation_basis": opportunity.compensation.basis.value,
        "compensation_period": opportunity.compensation.period.value,
        "tax_treatment": opportunity.compensation.tax_treatment.value,
        "compensation_verified": opportunity.compensation_verified,
        "estimated_hours_min": opportunity.estimated_hours_min,
        "estimated_hours_max": opportunity.estimated_hours_max,
        "deadline": opportunity.deadline,
        "start_date": opportunity.start_date,
        "source_name": opportunity.source.name,
        "source_url": str(opportunity.source.url) if opportunity.source.url else None,
        "source_type": opportunity.source.source_type.value,
        "retrieved_at": opportunity.source.retrieved_at,
        "last_verified_at": opportunity.source.last_verified_at,
        "is_active": opportunity.is_active,
        "is_demo": opportunity.is_demo,
        "is_sponsored": opportunity.is_sponsored,
        "evidence_confidence": opportunity.evidence_confidence.value,
        "safety_verdict": opportunity.safety.verdict.value,
        "safety_reasons": opportunity.safety.reasons,
    }


def row_to_opportunity(row: Any) -> Opportunity:
    from app.domain.enums import EmploymentType, SafetyVerdict, SourceType
    from app.domain.evidence import SourceRef
    from app.domain.opportunity import LanguageRequirement, Requirement, SafetyAssessment

    return Opportunity(
        id=row.id,
        title=row.title,
        organization=row.organization,
        category=IncomeStreamCategory(row.category),
        subcategory=row.subcategory,
        description=row.description,
        summary=row.summary,
        country=row.country,
        region=row.region,
        city=row.city,
        remote_type=RemoteType(row.remote_type),
        required_skills=row.required_skills,
        preferred_skills=row.preferred_skills,
        required_languages=[
            LanguageRequirement(**item) for item in row.required_languages.get("items", [])
        ],
        experience_min_years=row.experience_min_years,
        experience_max_years=row.experience_max_years,
        eligibility_text=row.eligibility_text,
        eligibility_structured=[
            Requirement(**item) for item in row.eligibility_structured.get("items", [])
        ],
        employment_type=EmploymentType(row.employment_type),
        compensation=MoneyRange(
            minor_min=row.compensation_min_minor,
            minor_max=row.compensation_max_minor,
            currency=row.currency,
            basis=CompensationBasis(row.compensation_basis),
            period=CompensationPeriod(row.compensation_period),
            tax_treatment=TaxTreatment(row.tax_treatment),
        ),
        compensation_verified=row.compensation_verified,
        estimated_hours_min=row.estimated_hours_min,
        estimated_hours_max=row.estimated_hours_max,
        deadline=row.deadline,
        start_date=row.start_date,
        source=SourceRef(
            name=row.source_name,
            url=row.source_url,
            source_type=SourceType(row.source_type),
            retrieved_at=row.retrieved_at,
            last_verified_at=row.last_verified_at,
        ),
        is_active=row.is_active,
        is_demo=row.is_demo,
        is_sponsored=row.is_sponsored,
        evidence_confidence=Confidence(row.evidence_confidence),
        safety=SafetyAssessment(
            verdict=SafetyVerdict(row.safety_verdict), reasons=row.safety_reasons
        ),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def json_or_empty(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        return dict(json.loads(raw))
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}
