"""The Money Map and opportunity endpoints - the core product surface."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import dto, mappers
from app.api.deps import (
    current_user,
    discovery_rate_limit,
    get_db,
    get_guard,
    get_legal_facts,
    get_provider,
    get_registry,
    rate_limit,
)
from app.db.models import Application, IncomeEvent, OpportunityMatch, Profile, ProfileSkill, User
from app.db.models import Opportunity as OpportunityRow
from app.domain.enums import (
    ApplicationStatus,
    CompensationPeriod,
    IncomeStreamCategory,
    MoneyState,
)
from app.domain.matching import Actionability, MatchScore
from app.domain.profile import UserProfile
from app.graph.state import Deps, DiscoveryState
from app.llm.base import LLMProvider
from app.security.guard import InjectionGuard
from app.services import analytics, discovery
from app.services.explanation import explain_match
from app.services.germany_check import GermanyCheckService
from app.services.legal_facts import LegalFactRepository
from app.services.money_map import IncomeRecord, summarise
from app.sources.registry import SourceRegistry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["opportunities"], dependencies=[Depends(rate_limit)])


# ------------------------------------------------------------------ helpers


def _load_profile(session: Session, user: User) -> UserProfile:
    row = session.execute(select(Profile).where(Profile.user_id == user.id)).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Build your profile first so we know what to look for.",
        )
    skills = list(
        session.execute(select(ProfileSkill).where(ProfileSkill.profile_id == row.id)).scalars()
    )
    return mappers.profile_row_to_domain(row, skills)


def _require_confirmed(profile: UserProfile) -> None:
    ready, missing = profile.is_ready_for_discovery()
    if ready:
        return
    if not profile.confirmed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Review and confirm your profile before we search. Nothing we extracted "
                "is used until you have checked it."
            ),
        )
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Before we can search, we still need: " + ", ".join(missing) + ".",
    )


def _income_records(session: Session, user_id: str) -> list[IncomeRecord]:
    records: list[IncomeRecord] = []
    for row in session.execute(
        select(IncomeEvent).where(IncomeEvent.user_id == user_id)
    ).scalars():
        records.append(
            IncomeRecord(
                label=row.label,
                amount_minor=row.amount_minor,
                state=MoneyState(row.money_state),
                period=CompensationPeriod(row.period),
                occurred_on=row.occurred_on,
                currency=row.currency,
            )
        )
    return records


def _application_statuses(session: Session, user_id: str) -> dict[str, ApplicationStatus]:
    return {
        row.opportunity_id: ApplicationStatus(row.status)
        for row in session.execute(
            select(Application).where(Application.user_id == user_id)
        ).scalars()
    }


def _greeting(profile: UserProfile, now: datetime | None = None) -> str:
    hour = (now or datetime.now(UTC)).hour
    part = "morning" if hour < 12 else ("afternoon" if hour < 18 else "evening")
    name = profile.general.display_name
    return f"Good {part}, {name}" if name else f"Good {part}"


def _income_paths(
    opportunities: list, ranked: list
) -> list[dto.IncomePathDto]:
    """Group results by category, so the map shows routes rather than a list."""
    by_id = {o.id: o for o in opportunities}
    scores: dict[IncomeStreamCategory, list[int]] = {}
    counts: dict[IncomeStreamCategory, int] = {}
    monthly: dict[IncomeStreamCategory, list[int]] = {}

    for entry in ranked:
        opportunity = by_id.get(entry.opportunity_id)
        if opportunity is None:
            continue
        category = opportunity.category
        counts[category] = counts.get(category, 0) + 1
        scores.setdefault(category, []).append(entry.match.total_score)
        value = opportunity.compensation.monthly_equivalent_minor(None)
        if value is not None:
            monthly.setdefault(category, []).append(value)

    return sorted(
        (
            dto.IncomePathDto(
                category=category,
                label=category.value.replace("_", " ").title(),
                opportunity_count=count,
                best_match_score=max(scores.get(category, [0])) or None,
                # Only shown when at least one opportunity in the path published
                # a convertible figure. Otherwise the path has a count and no
                # number, which is the honest rendering.
                indicative_monthly_minor=max(monthly[category]) if monthly.get(category) else None,
            )
            for category, count in counts.items()
        ),
        key=lambda path: (path.best_match_score or 0, path.opportunity_count),
        reverse=True,
    )


def _this_week(opportunities: list, ranked: list) -> list[str]:
    by_id = {o.id: o for o in opportunities}
    today = datetime.now(UTC).date()
    lines: list[str] = []
    for entry in ranked:
        opportunity = by_id.get(entry.opportunity_id)
        if opportunity is None or opportunity.deadline is None:
            continue
        days = (opportunity.deadline - today).days
        if 0 <= days <= 7:
            lines.append(
                f"{opportunity.title} closes in {days} day{'s' if days != 1 else ''}."
            )
    return lines[:5]


# -------------------------------------------------------------- money map


@router.post("/money-map/refresh", response_model=dto.MoneyMapResponse)
def refresh_money_map(
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
    provider: LLMProvider = Depends(get_provider),
    guard: InjectionGuard = Depends(get_guard),
    registry: SourceRegistry = Depends(get_registry),
    facts: LegalFactRepository = Depends(get_legal_facts),
    _limited: None = Depends(discovery_rate_limit),
) -> dto.MoneyMapResponse:
    """Run discovery and rebuild the Money Map.

    The expensive endpoint: it queries every source, may fetch and extract web
    pages, and rewrites the stored scores. Its own rate-limit bucket exists for
    that reason.
    """
    profile = _load_profile(session, user)
    _require_confirmed(profile)

    deps = Deps(
        session=session,
        provider=provider,
        guard=guard,
        registry=registry,
        facts=facts,
        user_id=user.id,
    )
    plan_queries: list[str] = []
    state = discovery.discover(profile, deps)
    plan = state.get("plan")
    if plan is not None:
        plan_queries = [query.text for query in plan.queries]

    analytics.record(
        session,
        "opportunity_search_started",
        user_id=user.id,
        query_count=len(plan_queries),
        planner="model" if provider.available else "deterministic",
        live_search=state.get("live_search_used", False),
    )
    return _build_money_map(session, user, profile, state, plan_queries)


@router.get("/money-map", response_model=dto.MoneyMapResponse)
def read_money_map(
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dto.MoneyMapResponse:
    """The stored Money Map. Cheap: reads persisted scores, runs no search."""
    profile = _load_profile(session, user)
    ranked, opportunities = _load_stored(session, user.id)
    state: DiscoveryState = {
        "opportunities": opportunities,
        "ranked": ranked,
        "best_next_move": None,
        "notices": []
        if ranked
        else ["No opportunities yet. Build your Money Map to run the first search."],
    }
    from app.graph.nodes import pick_best_next_move

    state.update(pick_best_next_move(state, None))  # type: ignore[arg-type]
    return _build_money_map(session, user, profile, state, [])


def _load_stored(session: Session, user_id: str) -> tuple[list, list]:
    from app.domain.enums import ActionabilityBand
    from app.domain.matching import (
        ActionabilityFactor,
        HardFailure,
        RankedOpportunity,
        ScoreComponent,
        Uncertainty,
    )

    dismissed = discovery.dismissed_ids(session, user_id)
    rows = session.execute(
        select(OpportunityMatch, OpportunityRow)
        .join(OpportunityRow, OpportunityMatch.opportunity_id == OpportunityRow.id)
        .where(OpportunityMatch.user_id == user_id, OpportunityRow.is_active.is_(True))
        .order_by(OpportunityMatch.total_score.desc())
    ).all()

    ranked: list = []
    opportunities: list = []
    for match_row, opportunity_row in rows:
        if opportunity_row.id in dismissed:
            continue
        match = MatchScore(
            opportunity_id=opportunity_row.id,
            total_score=match_row.total_score,
            components=[
                ScoreComponent(**item) for item in match_row.components.get("items", [])
            ],
            hard_failures=[
                HardFailure(**item) for item in match_row.hard_failures.get("items", [])
            ],
            uncertainties=[
                Uncertainty(**item) for item in match_row.uncertainties.get("items", [])
            ],
            explanation_inputs=match_row.explanation_inputs,
            weights_version=match_row.weights_version,
        )
        action = Actionability(
            opportunity_id=opportunity_row.id,
            score=match_row.actionability_score,
            band=ActionabilityBand(match_row.actionability_band),
            factors=[
                ActionabilityFactor(**item)
                for item in match_row.actionability_factors.get("items", [])
            ],
            headline_reason="",
            blockers=[],
        )
        ranked.append(
            RankedOpportunity(
                opportunity_id=opportunity_row.id,
                match=match,
                actionability=action,
                rank_score=match.total_score * 0.7 + action.score * 0.3,
            )
        )
        opportunities.append(mappers.row_to_opportunity(opportunity_row))

    ranked.sort(key=lambda r: (r.match.eligible, r.rank_score), reverse=True)
    return ranked, opportunities


def _build_money_map(
    session: Session,
    user: User,
    profile: UserProfile,
    state: DiscoveryState,
    plan_queries: list[str],
) -> dto.MoneyMapResponse:
    opportunities = state.get("opportunities", [])
    ranked = state.get("ranked", [])
    by_id = {o.id: o for o in opportunities}

    money = summarise(profile, opportunities, _income_records(session, user.id))
    saved = discovery.saved_ids(session, user.id)
    statuses = _application_statuses(session, user.id)

    summaries = [
        mappers.opportunity_to_summary(
            by_id[entry.opportunity_id],
            match=entry.match,
            actionability=entry.actionability,
            saved=entry.opportunity_id in saved,
            application_status=statuses.get(entry.opportunity_id),
        )
        for entry in ranked
        if entry.opportunity_id in by_id
    ]

    best = state.get("best_next_move")
    analytics.record(
        session,
        "money_map_created",
        user_id=user.id,
        opportunity_count=len(summaries),
        high_match_count=sum(1 for s in summaries if s.match and s.match.total_score >= 70),
        has_goal=profile.income.desired_additional_monthly_minor is not None,
    )

    return dto.MoneyMapResponse(
        greeting=_greeting(profile),
        goal_monthly_minor=money.goal_monthly_minor,
        summary=dto.MoneySummaryDto(
            **money.summary.model_dump(), exclusions=money.exclusions
        ),
        goal_progress_ratio=money.goal_progress_ratio,
        best_next_move=dto.BestNextMoveDto(**best.model_dump()) if best else None,
        opportunities=summaries,
        income_paths=_income_paths(opportunities, ranked),
        this_week=_this_week(opportunities, ranked),
        recent_progress=_recent_progress(session, user.id),
        diagnostics=dto.DiscoveryDiagnosticsDto(
            considered=state.get("considered", 0),
            returned=len(summaries),
            duplicates_removed=state.get("duplicates_removed", 0),
            stale_removed=state.get("stale_removed", 0),
            blocked_unsafe=state.get("blocked_unsafe", 0),
            blocked_injection=state.get("blocked_injection", 0),
            extraction_failures=state.get("extraction_failures", 0),
            sources_queried=state.get("sources_queried", 0),
            sources_failed=state.get("sources_failed", []),
            live_search_used=state.get("live_search_used", False),
            notices=state.get("notices", []),
            plan_rationale=getattr(state.get("plan"), "rationale", ""),
            queries=plan_queries,
        ),
        is_demo=user.is_demo,
    )


def _recent_progress(session: Session, user_id: str) -> list[str]:
    lines: list[str] = []
    for row in session.execute(
        select(Application)
        .where(Application.user_id == user_id)
        .order_by(Application.updated_at.desc())
        .limit(5)
    ).scalars():
        opportunity = session.get(OpportunityRow, row.opportunity_id)
        title = opportunity.title if opportunity else "an opportunity"
        lines.append(f"{title}: {row.status.replace('_', ' ').lower()}")
    return lines


# ----------------------------------------------------------- opportunities


@router.get("/opportunities", response_model=list[dto.OpportunitySummaryDto])
def list_opportunities(
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
    saved_only: bool = False,
    min_score: int = 0,
) -> list[dto.OpportunitySummaryDto]:
    ranked, opportunities = _load_stored(session, user.id)
    by_id = {o.id: o for o in opportunities}
    saved = discovery.saved_ids(session, user.id)
    statuses = _application_statuses(session, user.id)
    return [
        mappers.opportunity_to_summary(
            by_id[entry.opportunity_id],
            match=entry.match,
            actionability=entry.actionability,
            saved=entry.opportunity_id in saved,
            application_status=statuses.get(entry.opportunity_id),
        )
        for entry in ranked
        if entry.opportunity_id in by_id
        and entry.match.total_score >= min_score
        and (not saved_only or entry.opportunity_id in saved)
    ]


@router.get("/opportunities/{opportunity_id}", response_model=dto.OpportunityDetailDto)
def read_opportunity(
    opportunity_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
    provider: LLMProvider = Depends(get_provider),
    facts: LegalFactRepository = Depends(get_legal_facts),
) -> dto.OpportunityDetailDto:
    row = session.get(OpportunityRow, opportunity_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    opportunity = mappers.row_to_opportunity(row)
    profile = _load_profile(session, user)

    match_row = session.execute(
        select(OpportunityMatch).where(
            OpportunityMatch.user_id == user.id,
            OpportunityMatch.opportunity_id == opportunity_id,
        )
    ).scalar_one_or_none()

    match: MatchScore | None = None
    action: Actionability | None = None
    if match_row is not None:
        ranked, _ = _load_stored(session, user.id)
        for entry in ranked:
            if entry.opportunity_id == opportunity_id:
                match, action = entry.match, entry.actionability
                break
    if match is None:
        # Not scored yet - score it now rather than showing a card with no
        # assessment. Deterministic, so this costs nothing.
        from app.services import actionability as actionability_service
        from app.services import matching as matching_service

        match = matching_service.score(profile, opportunity)
        action = actionability_service.assess(profile, opportunity, match)

    check = GermanyCheckService(facts).check(session, profile, opportunity)
    explanation = explain_match(provider, match, opportunity)

    analytics.record(
        session,
        "opportunity_opened",
        user_id=user.id,
        category=opportunity.category.value,
        match_score=match.total_score,
        is_demo=opportunity.is_demo,
    )
    return mappers.opportunity_to_detail(
        opportunity,
        match=match,
        actionability=action,
        explanation=explanation,
        germany_check=check,
        saved=opportunity_id in discovery.saved_ids(session, user.id),
        application_status=_application_statuses(session, user.id).get(opportunity_id),
    )


@router.get("/opportunities/{opportunity_id}/germany-check", response_model=dto.GermanyCheckDto)
def germany_check(
    opportunity_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
    facts: LegalFactRepository = Depends(get_legal_facts),
) -> dto.GermanyCheckDto:
    row = session.get(OpportunityRow, opportunity_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    profile = _load_profile(session, user)
    check = GermanyCheckService(facts).check(session, profile, mappers.row_to_opportunity(row))
    analytics.record(
        session,
        "tax_check_viewed",
        user_id=user.id,
        topic=row.category,
        needs_verification=check.needs_verification,
    )
    return mappers.germany_check_to_dto(check)
