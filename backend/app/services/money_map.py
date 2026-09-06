"""The Money Map: the arithmetic the whole product's credibility rests on.

There is one rule and it is absolute: **amounts in different states are never
added.** Potential is not secured; secured is not earned; a one-off fee is not
a monthly income; an opportunity with no published compensation contributes to
a *count*, never to a total.

The temptation this module exists to resist is obvious. A dashboard reading
"€4,200 of potential income" is far more compelling than "3 recurring
opportunities worth about €900/month, 4 one-off opportunities, and 6 whose pay
is not published". The second is what we can actually support, so it is what
gets rendered - and the goal progress bar moves only on money the user has
actually secured or earned, because a progress bar that fills up with
un-applied-for opportunities would be the product's biggest lie.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.domain.enums import (
    COMMITTED_STATES,
    CompensationPeriod,
    IncomeStreamStatus,
    MoneyState,
)
from app.domain.money import MoneySummary
from app.domain.opportunity import Opportunity
from app.domain.profile import UserProfile


def _opportunities(count: int) -> str:
    return "opportunity" if count == 1 else "opportunities"


@dataclass(frozen=True)
class IncomeRecord:
    """One recorded amount the user confirmed. Only source of SECURED/EARNED."""

    label: str
    amount_minor: int
    state: MoneyState
    period: CompensationPeriod
    occurred_on: date | None = None
    currency: str = "EUR"


@dataclass
class MoneyMap:
    """Everything the dashboard is allowed to show, and nothing more."""

    goal_monthly_minor: int | None
    currency: str
    summary: MoneySummary
    #: Human-readable statements of what is deliberately excluded from the
    #: totals. Rendered next to them, not hidden in a tooltip.
    exclusions: list[str] = field(default_factory=list)
    opportunity_count: int = 0

    @property
    def goal_progress_ratio(self) -> float | None:
        """Progress towards the monthly goal, from committed money only."""
        if not self.goal_monthly_minor:
            return None
        committed = self.summary.secured_monthly_minor
        return round(min(1.0, committed / self.goal_monthly_minor), 4)

    @property
    def has_any_committed_money(self) -> bool:
        return bool(
            self.summary.secured_monthly_minor
            or self.summary.secured_one_time_minor
            or self.summary.earned_total_minor
        )


def summarise(
    profile: UserProfile,
    opportunities: list[Opportunity],
    income_records: list[IncomeRecord],
) -> MoneyMap:
    """Build the Money Map. Pure arithmetic over typed amounts."""
    goal = profile.income.desired_additional_monthly_minor
    hours = profile.time.hours_per_week
    summary = MoneySummary(currency="EUR")
    exclusions: list[str] = []

    for opportunity in opportunities:
        compensation = opportunity.compensation
        if not compensation.known:
            summary.unknown_value_count += 1
            continue

        amount = compensation.conservative_minor
        assert amount is not None

        if compensation.period is CompensationPeriod.RECURRING:
            monthly = compensation.monthly_equivalent_minor(hours)
            if monthly is None:
                # A recurring hourly rate with no stated availability. We could
                # guess the hours; we do not.
                summary.unconvertible_count += 1
                continue
            summary.recurring_potential_monthly_minor += monthly
            summary.recurring_potential_count += 1
        elif compensation.period is CompensationPeriod.ONE_TIME:
            summary.one_time_potential_minor += amount
            summary.one_time_potential_count += 1
        else:
            # IRREGULAR or UNKNOWN cadence. An amount without a cadence cannot
            # be placed in either bucket without inventing the cadence.
            summary.unconvertible_count += 1

    for record in income_records:
        if record.state not in COMMITTED_STATES:
            continue
        if record.state is MoneyState.EARNED:
            summary.earned_total_minor += record.amount_minor
            summary.earned_count += 1
            continue
        if record.period is CompensationPeriod.RECURRING:
            summary.secured_monthly_minor += record.amount_minor
        else:
            summary.secured_one_time_minor += record.amount_minor
        summary.secured_count += 1

    if summary.unknown_value_count:
        count = summary.unknown_value_count
        exclusions.append(
            f"{count} {_opportunities(count)} excluded from these totals because the "
            f"source does not publish what {'it pays' if count == 1 else 'they pay'}."
        )
    if summary.unconvertible_count:
        count = summary.unconvertible_count
        exclusions.append(
            f"{count} {_opportunities(count)} {'publishes' if count == 1 else 'publish'} an "
            "amount we cannot express as a monthly figure without assuming hours or a "
            "payment cadence we were not told."
        )
    if summary.recurring_potential_count and hours is None:
        exclusions.append(
            "Add your weekly availability to convert hourly rates into a monthly view."
        )

    return MoneyMap(
        goal_monthly_minor=goal,
        currency="EUR",
        summary=summary,
        exclusions=exclusions,
        opportunity_count=len(opportunities),
    )


# ------------------------------------------------------------------ portfolio


@dataclass(frozen=True)
class PortfolioStream:
    """One line in the personal income portfolio."""

    label: str
    category: str
    status: IncomeStreamStatus
    money_state: MoneyState
    monthly_minor: int | None
    is_primary: bool = False

    @property
    def counts_towards_income(self) -> bool:
        """Only ACTIVE streams are income. Everything else is a possibility."""
        return self.status is IncomeStreamStatus.ACTIVE


def portfolio_totals(streams: list[PortfolioStream]) -> dict[str, int]:
    """Totals per status, never one blended figure.

    The vocabulary matters as much as the arithmetic: nothing is called an
    income stream in the UI until the user has secured or earned from it, and
    :class:`~app.domain.enums.IncomeStreamStatus` is what enforces that.
    """
    totals = {"active_monthly_minor": 0, "potential_monthly_minor": 0, "paused_monthly_minor": 0}
    for stream in streams:
        if stream.monthly_minor is None:
            continue
        match stream.status:
            case IncomeStreamStatus.ACTIVE:
                totals["active_monthly_minor"] += stream.monthly_minor
            case IncomeStreamStatus.POTENTIAL:
                totals["potential_monthly_minor"] += stream.monthly_minor
            case IncomeStreamStatus.PAUSED:
                totals["paused_monthly_minor"] += stream.monthly_minor
    return totals
