"""Money arithmetic: what may be added to what, and what may never be."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.domain.enums import (
    CompensationBasis,
    CompensationPeriod,
    IncomeStreamStatus,
    MoneyState,
    TaxTreatment,
)
from app.domain.money import MoneyRange, MoneySummary
from app.domain.opportunity import Opportunity
from app.services.money_map import IncomeRecord, PortfolioStream, portfolio_totals, summarise
from tests.conftest import make_opportunity, make_profile


def monthly(amount_minor: int) -> MoneyRange:
    return MoneyRange(
        minor_min=amount_minor,
        basis=CompensationBasis.PER_MONTH,
        period=CompensationPeriod.RECURRING,
    )


def one_off(amount_minor: int) -> MoneyRange:
    return MoneyRange(
        minor_min=amount_minor,
        basis=CompensationBasis.TOTAL,
        period=CompensationPeriod.ONE_TIME,
    )


# ============================================== the states never mix


def test_potential_is_never_added_to_secured() -> None:
    profile = make_profile()
    opportunities = [make_opportunity(id="a", compensation=monthly(100_000))]
    records = [
        IncomeRecord(
            label="Won project",
            amount_minor=50_000,
            state=MoneyState.SECURED,
            period=CompensationPeriod.ONE_TIME,
        )
    ]
    money = summarise(profile, opportunities, records)
    assert money.summary.recurring_potential_monthly_minor == 100_000
    assert money.summary.secured_one_time_minor == 50_000
    # Nothing anywhere holds their sum.
    assert money.summary.secured_monthly_minor == 0


def test_goal_progress_uses_committed_money_only() -> None:
    """A progress bar filled by un-applied-for opportunities would be a lie."""
    profile = make_profile()
    huge = [make_opportunity(id=f"o{i}", compensation=monthly(500_000)) for i in range(5)]
    money = summarise(profile, huge, [])
    assert money.summary.recurring_potential_monthly_minor == 2_500_000
    assert money.goal_progress_ratio == 0.0


def test_goal_progress_moves_only_on_secured_recurring_income() -> None:
    profile = make_profile()  # goal is 150_000/month
    records = [
        IncomeRecord(
            label="Retainer",
            amount_minor=75_000,
            state=MoneyState.SECURED,
            period=CompensationPeriod.RECURRING,
        )
    ]
    assert summarise(profile, [], records).goal_progress_ratio == 0.5


def test_one_time_amounts_are_not_folded_into_monthly() -> None:
    profile = make_profile()
    money = summarise(
        profile,
        [
            make_opportunity(id="a", compensation=monthly(100_000)),
            make_opportunity(id="b", compensation=one_off(500_000)),
        ],
        [],
    )
    assert money.summary.recurring_potential_monthly_minor == 100_000
    assert money.summary.one_time_potential_minor == 500_000


# ================================================ unknown stays unknown


def test_unpublished_compensation_is_counted_not_estimated() -> None:
    profile = make_profile()
    money = summarise(
        profile, [make_opportunity(id="a", compensation=MoneyRange())], []
    )
    assert money.summary.unknown_value_count == 1
    assert money.summary.recurring_potential_monthly_minor == 0
    assert money.summary.one_time_potential_minor == 0
    assert any("does not publish" in line for line in money.exclusions)


def test_an_hourly_rate_without_availability_is_not_converted() -> None:
    """Guessing the hours would be inventing the number."""
    hourly = MoneyRange(
        minor_min=15_000,
        basis=CompensationBasis.PER_HOUR,
        period=CompensationPeriod.RECURRING,
    )
    assert hourly.monthly_equivalent_minor(None) is None
    assert hourly.monthly_equivalent_minor(10.0) is not None


def test_an_amount_with_no_cadence_is_unconvertible_not_assumed() -> None:
    profile = make_profile()
    irregular = MoneyRange(
        minor_min=20_000,
        basis=CompensationBasis.PER_ENGAGEMENT,
        period=CompensationPeriod.UNKNOWN,
    )
    money = summarise(profile, [make_opportunity(id="a", compensation=irregular)], [])
    assert money.summary.unconvertible_count == 1
    assert money.summary.one_time_potential_minor == 0


def test_exclusions_are_reported_in_readable_singular_and_plural() -> None:
    profile = make_profile()
    one = summarise(profile, [make_opportunity(id="a", compensation=MoneyRange())], [])
    assert "1 opportunity " in one.exclusions[0]
    two = summarise(
        profile,
        [
            make_opportunity(id="a", compensation=MoneyRange()),
            make_opportunity(id="b", compensation=MoneyRange()),
        ],
        [],
    )
    assert "2 opportunities " in two.exclusions[0]


# ======================================================== conservatism


def test_a_published_range_is_summed_at_its_lower_bound() -> None:
    band = MoneyRange(
        minor_min=100_000,
        minor_max=900_000,
        basis=CompensationBasis.PER_MONTH,
        period=CompensationPeriod.RECURRING,
    )
    assert band.conservative_minor == 100_000
    money = summarise(make_profile(), [make_opportunity(id="a", compensation=band)], [])
    assert money.summary.recurring_potential_monthly_minor == 100_000


def test_a_range_is_never_collapsed_to_a_midpoint() -> None:
    band = MoneyRange(minor_min=100_000, minor_max=900_000)
    assert band.minor_min == 100_000
    assert band.minor_max == 900_000


def test_an_inverted_range_is_rejected() -> None:
    with pytest.raises(ValueError, match="minor_min"):
        MoneyRange(minor_min=900_000, minor_max=100_000)


# ======================================================== tax treatment


def test_external_compensation_defaults_to_unknown_tax_treatment() -> None:
    assert MoneyRange(minor_min=1000).tax_treatment is TaxTreatment.UNKNOWN


def test_a_demo_opportunity_cannot_claim_verified_compensation() -> None:
    """Constructing one is a validation error.

    Note that ``model_copy(update=...)`` deliberately bypasses Pydantic
    validators, so this invariant is enforced in three independent places: this
    validator, the ``ck_demo_cannot_be_verified`` CHECK constraint on the
    ``opportunities`` table, and ``DemoOpportunitySource`` forcing the field
    false as it loads. The next two tests cover the other two.
    """
    fields = make_opportunity().model_dump()
    fields["is_demo"] = True
    fields["compensation_verified"] = True
    with pytest.raises(ValueError, match="demo"):
        Opportunity(**fields)


def test_the_demo_source_forces_compensation_unverified() -> None:
    import json

    from app.sources.local import DemoOpportunitySource

    source = DemoOpportunitySource(Path("unused.json"))
    candidate = source._to_candidate(
        {"title": "x", "compensation_verified": True, "is_demo": False}
    )
    record = json.loads(candidate.structured["json"])
    assert record["is_demo"] is True
    assert record["compensation_verified"] is False


def test_the_database_refuses_a_verified_demo_row(session: Session) -> None:
    from sqlalchemy.exc import IntegrityError

    from app.db.models import Opportunity as OpportunityRow

    session.add(
        OpportunityRow(
            fingerprint="fp-demo-verified",
            title="x",
            category="OTHER",
            source_name="s",
            source_type="DEMO",
            is_demo=True,
            compensation_verified=True,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


# =========================================================== portfolio


def test_only_active_streams_count_as_income() -> None:
    streams = [
        PortfolioStream(
            label="Salary",
            category="FULL_TIME_JOB",
            status=IncomeStreamStatus.ACTIVE,
            money_state=MoneyState.EARNED,
            monthly_minor=400_000,
            is_primary=True,
        ),
        PortfolioStream(
            label="Possible consulting",
            category="CONSULTING",
            status=IncomeStreamStatus.POTENTIAL,
            money_state=MoneyState.POTENTIAL,
            monthly_minor=200_000,
        ),
    ]
    totals = portfolio_totals(streams)
    assert totals["active_monthly_minor"] == 400_000
    assert totals["potential_monthly_minor"] == 200_000
    assert streams[1].counts_towards_income is False


def test_money_summary_never_exposes_a_blended_progress_figure() -> None:
    """The domain object refuses to compute one; only the Money Map may."""
    assert MoneySummary().goal_progress_ratio is None


def test_a_won_income_record_with_no_goal_yields_no_progress_ratio() -> None:
    profile = make_profile()
    profile.income.desired_additional_monthly_minor = None
    money = summarise(
        profile,
        [],
        [
            IncomeRecord(
                label="x",
                amount_minor=1000,
                state=MoneyState.EARNED,
                period=CompensationPeriod.ONE_TIME,
                occurred_on=date.today(),
            )
        ],
    )
    assert money.goal_progress_ratio is None
    assert money.summary.earned_total_minor == 1000
