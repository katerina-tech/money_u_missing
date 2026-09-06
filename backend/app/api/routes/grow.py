"""GROW and FAMILY: goals, deterministic projections, neutral comparisons.

Every number returned by these endpoints is arithmetic over inputs the *user*
supplied. No model is consulted, no return rate is suggested, no instrument is
named or ranked. See docs/REGULATORY_BOUNDARIES.md for why that line is drawn
where it is.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import dto
from app.api.deps import current_user, get_db, rate_limit
from app.db.models import ChildGoalRow, FinancialGoalRow, User
from app.domain.enums import FinancialGoalType
from app.domain.goals import ChildGoal, FinancialGoal
from app.services import analytics
from app.services.calculators import (
    CalculatorInputError,
    contribution_needed_minor,
    ownership_card,
    project,
)

router = APIRouter(prefix="/api", tags=["grow"], dependencies=[Depends(rate_limit)])


def _goal_dto(row: FinancialGoalRow) -> dto.GoalDto:
    goal = FinancialGoal(
        id=row.id,
        user_id=row.user_id,
        goal_type=FinancialGoalType(row.goal_type),
        name=row.name,
        target_minor=row.target_minor,
        target_date=row.target_date,
        current_minor=row.current_minor,
        monthly_contribution_minor=row.monthly_contribution_minor,
        currency=row.currency,
    )
    return dto.GoalDto(
        id=goal.id,
        goal_type=goal.goal_type,
        name=goal.name,
        target_minor=goal.target_minor,
        target_date=goal.target_date,
        current_minor=goal.current_minor,
        monthly_contribution_minor=goal.monthly_contribution_minor,
        currency=goal.currency,
        progress_ratio=goal.progress_ratio,
        months_at_current_contribution=goal.months_at_current_contribution(),
    )


@router.get("/goals", response_model=list[dto.GoalDto])
def list_goals(
    user: User = Depends(current_user), session: Session = Depends(get_db)
) -> list[dto.GoalDto]:
    return [
        _goal_dto(row)
        for row in session.execute(
            select(FinancialGoalRow).where(FinancialGoalRow.user_id == user.id)
        ).scalars()
    ]


@router.post("/goals", response_model=dto.GoalDto, status_code=status.HTTP_201_CREATED)
def create_goal(
    payload: dto.GoalRequest,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dto.GoalDto:
    row = FinancialGoalRow(
        user_id=user.id,
        goal_type=payload.goal_type.value,
        name=payload.name,
        target_minor=payload.target_minor,
        target_date=payload.target_date,
        current_minor=payload.current_minor,
        monthly_contribution_minor=payload.monthly_contribution_minor,
    )
    session.add(row)
    session.flush()
    analytics.record(
        session,
        "goal_created",
        user_id=user.id,
        goal_type=payload.goal_type.value,
        has_target_date=payload.target_date is not None,
    )
    return _goal_dto(row)


@router.put("/goals/{goal_id}", response_model=dto.GoalDto)
def update_goal(
    goal_id: str,
    payload: dto.GoalRequest,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dto.GoalDto:
    row = session.get(FinancialGoalRow, goal_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    row.goal_type = payload.goal_type.value
    row.name = payload.name
    row.target_minor = payload.target_minor
    row.target_date = payload.target_date
    row.current_minor = payload.current_minor
    row.monthly_contribution_minor = payload.monthly_contribution_minor
    return _goal_dto(row)


@router.delete("/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(
    goal_id: str, user: User = Depends(current_user), session: Session = Depends(get_db)
) -> None:
    row = session.get(FinancialGoalRow, goal_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    session.delete(row)


@router.post("/grow/project", response_model=dto.ProjectionResponse)
def projection(payload: dto.ProjectionRequest) -> dto.ProjectionResponse:
    """Future value under the user's own assumptions. Illustrative, and labelled so.

    Requires no authentication because it holds no data and reads none: it is a
    calculator over numbers in the request body.
    """
    try:
        result = project(
            initial_minor=payload.initial_minor,
            monthly_contribution_minor=payload.monthly_contribution_minor,
            annual_return=payload.annual_return,
            months=payload.months,
            annual_inflation=payload.annual_inflation,
        )
    except CalculatorInputError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

    return dto.ProjectionResponse(
        initial_minor=result.initial_minor,
        monthly_contribution_minor=result.monthly_contribution_minor,
        annual_return=result.annual_return,
        annual_inflation=result.annual_inflation,
        months=result.months,
        currency=result.currency,
        total_contributed_minor=result.total_contributed_minor,
        final_balance_minor=result.final_balance_minor,
        final_real_balance_minor=result.final_real_balance_minor,
        growth_minor=result.growth_minor,
        points=[point.model_dump() for point in result.points],
        disclaimer=result.disclaimer,
    )


@router.get("/grow/contribution-needed")
def contribution_needed(
    target_minor: int, initial_minor: int, annual_return: float, months: int
) -> dict[str, object]:
    """Monthly contribution required to hit a target, or an honest ``null``."""
    value = contribution_needed_minor(
        target_minor=target_minor,
        initial_minor=initial_minor,
        annual_return=annual_return,
        months=months,
    )
    return {
        "monthly_contribution_minor": value,
        "reachable": value is not None,
        "note": (
            "Illustrative assumption - not a forecast."
            if value is not None
            else "This target cannot be reached within the horizon you gave."
        ),
    }


@router.get("/grow/etf-education")
def etf_education() -> dict[str, object]:
    """Objective explanations of ETF terminology. No product is named or ranked.

    The absence of any "recommended" field is deliberate and structural: there
    is nowhere in this response for a recommendation to go.
    """
    return {
        "disclaimer": (
            "Educational information about how these instruments work. Not investment "
            "advice, and no recommendation of any product."
        ),
        "terms": [
            {
                "term": "ETF",
                "explanation": (
                    "An exchange-traded fund is a fund whose shares trade on an exchange. "
                    "Buying one share gives you a proportional interest in everything the "
                    "fund holds."
                ),
            },
            {
                "term": "Index",
                "explanation": (
                    "A published rule for selecting and weighting a set of securities. An "
                    "index fund follows that rule rather than a manager's judgement."
                ),
            },
            {
                "term": "UCITS",
                "explanation": (
                    "An EU regulatory framework for funds sold to retail investors. It "
                    "imposes diversification and disclosure requirements. It is a legal "
                    "form, not a quality rating."
                ),
            },
            {
                "term": "Diversification",
                "explanation": (
                    "Holding many different assets so that the failure of any one has a "
                    "limited effect. It reduces the risk specific to individual holdings; "
                    "it does not remove the risk of the market as a whole falling."
                ),
            },
            {
                "term": "TER (total expense ratio)",
                "explanation": (
                    "The annual running cost of the fund, expressed as a percentage of "
                    "assets. It is deducted from the fund, not billed separately, so it "
                    "reduces returns whether the fund rises or falls."
                ),
            },
            {
                "term": "Replication",
                "explanation": (
                    "How the fund tracks its index. Physical replication holds the actual "
                    "securities, in whole or as a representative sample. Synthetic "
                    "replication uses a swap with a counterparty, which introduces "
                    "counterparty risk."
                ),
            },
            {
                "term": "Accumulating vs distributing",
                "explanation": (
                    "An accumulating fund reinvests income inside the fund; a distributing "
                    "fund pays it out. This affects when and how income is taxed, which in "
                    "Germany depends on your circumstances."
                ),
            },
            {
                "term": "Fund domicile",
                "explanation": (
                    "The country where the fund is legally established. It affects the tax "
                    "treatment of the fund's own income and the reporting you receive."
                ),
            },
            {
                "term": "Fund size",
                "explanation": (
                    "Total assets under management. Very small funds are more likely to be "
                    "closed or merged, which can force a disposal at a time not of your "
                    "choosing."
                ),
            },
            {
                "term": "Market risk",
                "explanation": (
                    "The risk that the whole market falls. Diversification within an asset "
                    "class does not protect against it."
                ),
            },
            {
                "term": "Volatility",
                "explanation": (
                    "How much a price moves over time. High volatility means larger swings "
                    "in both directions, not a higher expected return."
                ),
            },
            {
                "term": "Time horizon",
                "explanation": (
                    "How long before you need the money. A short horizon leaves less time "
                    "to recover from a fall, which is why horizon and volatility are "
                    "considered together."
                ),
            },
        ],
    }


# ---------------------------------------------------------------- family


def _child_dto(row: ChildGoalRow) -> dto.ChildGoalDto:
    goal = ChildGoal(
        id=row.id,
        user_id=row.user_id,
        child_label=row.child_label,
        child_age_years=row.child_age_years,
        target_age_years=row.target_age_years,
        target_minor=row.target_minor,
        current_minor=row.current_minor,
        monthly_contribution_minor=row.monthly_contribution_minor,
        currency=row.currency,
    )
    return dto.ChildGoalDto(
        id=goal.id,
        child_label=goal.child_label,
        child_age_years=goal.child_age_years,
        target_age_years=goal.target_age_years,
        target_minor=goal.target_minor,
        current_minor=goal.current_minor,
        monthly_contribution_minor=goal.monthly_contribution_minor,
        currency=goal.currency,
        years_remaining=goal.years_remaining,
    )


@router.get("/family/goals", response_model=list[dto.ChildGoalDto])
def list_child_goals(
    user: User = Depends(current_user), session: Session = Depends(get_db)
) -> list[dto.ChildGoalDto]:
    return [
        _child_dto(row)
        for row in session.execute(
            select(ChildGoalRow).where(ChildGoalRow.user_id == user.id)
        ).scalars()
    ]


@router.post(
    "/family/goals", response_model=dto.ChildGoalDto, status_code=status.HTTP_201_CREATED
)
def create_child_goal(
    payload: dto.ChildGoalRequest,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dto.ChildGoalDto:
    if payload.target_age_years <= payload.child_age_years:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The target age must be later than the current age.",
        )
    row = ChildGoalRow(
        user_id=user.id,
        child_label=payload.child_label,
        child_age_years=payload.child_age_years,
        target_age_years=payload.target_age_years,
        target_minor=payload.target_minor,
        current_minor=payload.current_minor,
        monthly_contribution_minor=payload.monthly_contribution_minor,
    )
    session.add(row)
    session.flush()
    analytics.record(
        session,
        "child_goal_created",
        user_id=user.id,
        years_remaining=payload.target_age_years - payload.child_age_years,
    )
    return _child_dto(row)


@router.delete("/family/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_child_goal(
    goal_id: str, user: User = Depends(current_user), session: Session = Depends(get_db)
) -> None:
    row = session.get(ChildGoalRow, goal_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    session.delete(row)


@router.get("/family/ownership")
def ownership() -> dict[str, object]:
    """Parent-held versus child-held savings. ``recommended`` is always null."""
    return ownership_card()
