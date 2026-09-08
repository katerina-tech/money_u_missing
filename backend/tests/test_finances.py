"""The rules that keep the money picture honest, and the tax boundary intact.

Most of these assert an absence: no gross/net conversion, no tax effect, no
inferred household. An absence is exactly the kind of property that erodes
quietly, so it is worth a test each.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from app.domain.enums import (
    AmountBasis,
    CompensationPeriod,
    ExpenseCategory,
    Tristate,
)
from app.domain.finances import (
    BaselineIncome,
    BaselinePicture,
    Child,
    DeductibleExpense,
    ExpenseSummary,
    HouseholdContext,
    summarise_expenses,
)

WHEN = date(2026, 3, 1)


def expense(**overrides: object) -> DeductibleExpense:
    data: dict[str, object] = {
        "label": "A cost",
        "amount_minor": 10_000,
        "category": ExpenseCategory.OTHER,
        "incurred_on": WHEN,
    }
    data.update(overrides)
    return DeductibleExpense.model_validate(data)


# ------------------------------------------------------------- baseline


def test_gross_and_net_are_totalled_separately() -> None:
    """The central rule: two bases are two numbers, never one."""
    picture = BaselinePicture(
        entries=[
            BaselineIncome(label="Salary", amount_minor=300_000, basis=AmountBasis.NET),
            BaselineIncome(label="Retainer", amount_minor=100_000, basis=AmountBasis.GROSS),
        ]
    )
    assert picture.net_monthly_minor == 300_000
    assert picture.gross_monthly_minor == 100_000
    assert any("not added together" in note for note in picture.notes())


def test_unlabelled_income_is_kept_out_of_both_totals() -> None:
    picture = BaselinePicture(
        entries=[
            BaselineIncome(label="Salary", amount_minor=300_000, basis=AmountBasis.NET),
            BaselineIncome(label="Something", amount_minor=50_000),
        ]
    )
    assert picture.net_monthly_minor == 300_000
    assert picture.gross_monthly_minor == 0
    assert picture.unlabelled_monthly_minor == 50_000
    assert any("not marked as gross or net" in note for note in picture.notes())


def test_a_one_off_payment_has_no_monthly_equivalent() -> None:
    """Spreading a single payment over a year invents a regularity."""
    one_off = BaselineIncome(
        label="Bonus", amount_minor=120_000, period=CompensationPeriod.ONE_TIME
    )
    assert one_off.monthly_minor() is None

    picture = BaselinePicture(entries=[one_off])
    assert picture.net_monthly_minor == 0
    assert picture.gross_monthly_minor == 0
    assert picture.one_off_minor == 120_000


def test_uplift_is_none_without_a_baseline() -> None:
    """"An extra 500" against nothing known is not a percentage."""
    assert BaselinePicture().uplift_ratio(50_000) is None


def test_uplift_uses_the_basis_the_user_actually_gave() -> None:
    picture = BaselinePicture(
        entries=[BaselineIncome(label="Salary", amount_minor=250_000, basis=AmountBasis.NET)]
    )
    assert picture.uplift_ratio(50_000) == 0.2


def test_there_is_no_gross_to_net_conversion_anywhere() -> None:
    """A guard on the boundary, not on a behaviour.

    If someone ever adds a converter, this test tells them to read the module
    docstring first.
    """
    from pathlib import Path

    import app.domain.finances as module

    text = Path(module.__file__ or "").read_text(encoding="utf-8").lower()
    for forbidden in ("def to_net", "def to_gross", "steuerklasse_rate", "tax_rate"):
        assert forbidden not in text


# ------------------------------------------------------------- expenses


def test_an_empty_summary_claims_nothing() -> None:
    summary = summarise_expenses([])
    assert summary.total_minor == 0
    assert summary.by_category == []
    assert summary.questions_to_check == []


def test_totals_are_the_users_own_arithmetic() -> None:
    summary = summarise_expenses(
        [
            expense(amount_minor=5_000, category=ExpenseCategory.TRAVEL),
            expense(amount_minor=7_500, category=ExpenseCategory.TRAVEL),
            expense(amount_minor=100_000, category=ExpenseCategory.EQUIPMENT),
        ]
    )
    assert summary.total_minor == 112_500
    assert summary.count == 3
    # Largest category first, so the biggest number leads.
    assert summary.by_category[0].category is ExpenseCategory.EQUIPMENT
    assert summary.by_category[1].total_minor == 12_500


def test_the_summary_has_no_field_for_a_tax_effect() -> None:
    """The boundary, expressed as a schema rather than as wording."""
    fields = set(ExpenseSummary.model_fields)
    for forbidden in ("tax_saved_minor", "tax_rate", "deductible_minor", "refund_minor"):
        assert forbidden not in fields


def test_missing_receipts_produce_a_specific_question() -> None:
    summary = summarise_expenses(
        [expense(has_receipt=Tristate.YES), expense(), expense(has_receipt=Tristate.NO)]
    )
    assert summary.without_receipt_count == 2
    assert any("no confirmed receipt" in question for question in summary.questions_to_check)


def test_a_declared_private_share_is_asked_about_not_calculated() -> None:
    summary = summarise_expenses(
        [expense(category=ExpenseCategory.WORKSPACE, partly_private=Tristate.YES)]
    )
    asked = " ".join(summary.questions_to_check)
    assert "private share" in asked
    # A percentage would be this product deciding, which it does not do.
    assert "%" not in asked


def test_mixed_use_prone_categories_raise_the_question_unprompted() -> None:
    summary = summarise_expenses([expense(category=ExpenseCategory.COMMUNICATION)])
    assert any("used privately as well" in question for question in summary.questions_to_check)


def test_every_summary_carries_the_disclaimer() -> None:
    assert "not steuerberatung" in summarise_expenses([expense()]).disclaimer.lower()


def test_an_expense_cannot_belong_to_two_things() -> None:
    with pytest.raises(ValidationError):
        expense(income_stream_id="a", application_id="b")


def test_summarising_is_deterministic() -> None:
    items = [
        expense(amount_minor=1_00, category=ExpenseCategory.TRAVEL),
        expense(amount_minor=2_00, category=ExpenseCategory.MATERIALS),
        expense(amount_minor=3_00, category=ExpenseCategory.TRAVEL),
    ]
    assert summarise_expenses(items) == summarise_expenses(list(reversed(items)))


# ------------------------------------------------------------ household


def test_household_starts_unknown_and_says_so() -> None:
    household = HouseholdContext()
    assert household.has_children is Tristate.UNKNOWN
    assert household.disclosed is False


def test_children_and_the_disclosure_must_agree() -> None:
    """A recorded child alongside "no children" is a bug, not a preference."""
    with pytest.raises(ValidationError):
        HouseholdContext(
            has_children=Tristate.NO, children=[Child(label="Eldest", age_years=7)]
        )


def test_a_child_is_recorded_by_age_not_by_birth_date() -> None:
    fields = set(Child.model_fields)
    assert "age_years" in fields
    for forbidden in ("date_of_birth", "birth_date", "name", "first_name"):
        assert forbidden not in fields
