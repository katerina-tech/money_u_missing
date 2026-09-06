"""GROW and FAMILY: deterministic projections and neutral comparisons.

No model is consulted anywhere in this module, and that is a correctness
requirement rather than a preference. A compound-growth figure produced by a
language model is a plausible-looking number, not a calculated one, and users
cannot tell the two apart. Every figure here comes from arithmetic that can be
reproduced with a spreadsheet.

The regulatory line (docs/REGULATORY_BOUNDARIES.md): the *user* supplies the
assumed return, the horizon and the contribution. The product computes what
those inputs imply and labels the result illustrative. It does not suggest a
rate, rank instruments, or say what anyone should buy - those would be personal
recommendations concerning financial instruments.
"""

from __future__ import annotations

from datetime import date

from app.domain.enums import AccountOwnership
from app.domain.goals import (
    MAX_ANNUAL_RETURN,
    MAX_HORIZON_YEARS,
    MIN_ANNUAL_RETURN,
    ChildGoal,
    FinancialGoal,
    OwnershipComparison,
    OwnershipConsideration,
    ProjectionPoint,
    ProjectionResult,
)


class CalculatorInputError(ValueError):
    """An assumption outside the range this calculator will render."""


def project(
    *,
    initial_minor: int,
    monthly_contribution_minor: int,
    annual_return: float,
    months: int,
    annual_inflation: float | None = None,
    currency: str = "EUR",
    sample_every: int = 12,
) -> ProjectionResult:
    """Future value of a monthly savings plan under a user-supplied return.

    Contributions are applied at the *end* of each month and growth is
    compounded monthly on the opening balance. That is the conservative
    convention: assuming contributions arrive at the start of the month and earn
    a full month's growth inflates the final figure by roughly one month of
    return, which is exactly the kind of quiet optimism this product avoids.

    Negative returns are permitted, because pretending markets only go up would
    make the tool useless for the one scenario people most need to see.
    """
    if not MIN_ANNUAL_RETURN <= annual_return <= MAX_ANNUAL_RETURN:
        raise CalculatorInputError(
            f"Assumed annual return must be between {MIN_ANNUAL_RETURN:.0%} and "
            f"{MAX_ANNUAL_RETURN:.0%}."
        )
    if months < 0 or months > MAX_HORIZON_YEARS * 12:
        raise CalculatorInputError(f"Horizon must be between 0 and {MAX_HORIZON_YEARS} years.")
    if initial_minor < 0 or monthly_contribution_minor < 0:
        raise CalculatorInputError("Amounts cannot be negative.")
    if annual_inflation is not None and not -0.1 <= annual_inflation <= 0.2:
        raise CalculatorInputError("Assumed inflation must be between -10% and 20%.")

    monthly_rate = (1 + annual_return) ** (1 / 12) - 1
    monthly_inflation = (
        (1 + annual_inflation) ** (1 / 12) - 1 if annual_inflation is not None else None
    )

    balance = float(initial_minor)
    contributed = initial_minor
    points: list[ProjectionPoint] = [
        ProjectionPoint(
            month=0,
            contributed_minor=contributed,
            balance_minor=round(balance),
            real_balance_minor=round(balance) if monthly_inflation is not None else None,
        )
    ]

    for month in range(1, months + 1):
        balance = balance * (1 + monthly_rate) + monthly_contribution_minor
        contributed += monthly_contribution_minor
        if month % sample_every == 0 or month == months:
            real = None
            if monthly_inflation is not None:
                real = round(balance / ((1 + monthly_inflation) ** month))
            points.append(
                ProjectionPoint(
                    month=month,
                    contributed_minor=contributed,
                    balance_minor=round(balance),
                    real_balance_minor=real,
                )
            )

    final = round(balance)
    final_real = points[-1].real_balance_minor if monthly_inflation is not None else None
    return ProjectionResult(
        initial_minor=initial_minor,
        monthly_contribution_minor=monthly_contribution_minor,
        annual_return=annual_return,
        annual_inflation=annual_inflation,
        months=months,
        currency=currency,
        total_contributed_minor=contributed,
        final_balance_minor=final,
        final_real_balance_minor=final_real,
        growth_minor=final - contributed,
        points=points,
    )


def project_goal(goal: FinancialGoal, *, annual_return: float, months: int) -> ProjectionResult:
    return project(
        initial_minor=goal.current_minor,
        monthly_contribution_minor=goal.monthly_contribution_minor,
        annual_return=annual_return,
        months=months,
        currency=goal.currency,
    )


def project_child_goal(goal: ChildGoal, *, annual_return: float) -> ProjectionResult:
    return project(
        initial_minor=goal.current_minor,
        monthly_contribution_minor=goal.monthly_contribution_minor,
        annual_return=annual_return,
        months=goal.years_remaining * 12,
        currency=goal.currency,
    )


def contribution_needed_minor(
    *, target_minor: int, initial_minor: int, annual_return: float, months: int
) -> int | None:
    """Monthly contribution required to reach a target. ``None`` if unreachable.

    Returns ``None`` rather than a huge number when the target cannot be met -
    for instance a zero-month horizon - because a figure like "€480,000 per
    month" is not an answer, it is a rendering artefact.
    """
    if months <= 0:
        return None
    monthly_rate: float = (1 + annual_return) ** (1 / 12) - 1
    if abs(monthly_rate) < 1e-12:
        shortfall = target_minor - initial_minor
        return max(0, -(-shortfall // months))

    growth: float = (1 + monthly_rate) ** months
    future_of_initial = initial_minor * growth
    remaining: float = target_minor - future_of_initial
    if remaining <= 0:
        return 0
    annuity_factor = (growth - 1) / monthly_rate
    if annuity_factor <= 0:
        return None
    return round(remaining / annuity_factor)


def months_between(start: date, end: date) -> int:
    return max(0, (end.year - start.year) * 12 + (end.month - start.month))


# ----------------------------------------------------------- family module


def ownership_comparison() -> OwnershipComparison:
    """Parent-held versus child-held savings, with no recommended answer.

    Each row genuinely cuts both ways, which is why there is no winner. The
    considerations are framed as what changes, not as what is better, and the
    numeric consequences that depend on current allowances are deliberately
    absent - those are :class:`~app.domain.legal.LegalFact` rows shown with
    their own verification status, not prose here.
    """
    return OwnershipComparison(
        considerations=[
            OwnershipConsideration(
                topic="Legal ownership",
                parent_account="The money remains legally yours.",
                child_account=(
                    "The money legally belongs to the child from the moment it is paid in, "
                    "even though you administer it."
                ),
            ),
            OwnershipConsideration(
                topic="Control at 18",
                parent_account="You decide if and when to hand it over.",
                child_account=(
                    "The child gains full control at 18 and may use it for anything."
                ),
            ),
            OwnershipConsideration(
                topic="Using the money for other purposes",
                parent_account="You may use it for any purpose at any time.",
                child_account=(
                    "Withdrawals must be in the child's interest; using it for household "
                    "costs is generally not permitted."
                ),
            ),
            OwnershipConsideration(
                topic="Tax allowances on investment income",
                parent_account=(
                    "Income counts against your own allowance, alongside your other "
                    "investment income."
                ),
                child_account=(
                    "The child has allowances of their own, which can mean less tax on "
                    "investment income - subject to current thresholds."
                ),
                fact_id="de_sparer_pauschbetrag",
            ),
            OwnershipConsideration(
                topic="Interaction with support and benefits",
                parent_account="No effect on the child's own means-tested entitlements.",
                child_account=(
                    "Assets in the child's name can count towards their own means testing "
                    "later, for example for student support."
                ),
            ),
            OwnershipConsideration(
                topic="Administration",
                parent_account="One account, no additional paperwork.",
                child_account=(
                    "Opening usually needs both parents' consent and the child's "
                    "identification documents."
                ),
            ),
        ],
        questions_to_check=[
            "Which allowances currently apply to investment income in a child's name?",
            "Would assets in my child's name affect their entitlement to student support?",
            "What documentation does my provider require to open an account for a minor?",
            "What happens to the account when my child turns 18?",
        ],
        recommended=None,
    )


#: The FAMILY module returns this alongside every child projection.
OWNERSHIP_CARD_TITLE = "ACCOUNT OWNERSHIP MATTERS"


def ownership_card() -> dict[str, object]:
    comparison = ownership_comparison()
    return {
        "title": OWNERSHIP_CARD_TITLE,
        "note": comparison.note,
        "considerations": [c.model_dump() for c in comparison.considerations],
        "questions_to_check": comparison.questions_to_check,
        "recommended": None,
        "ownership_options": [option.value for option in AccountOwnership],
    }
