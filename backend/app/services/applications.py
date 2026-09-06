"""Application tracking: the state machine, and the money it is allowed to create.

The transition table is enforced here rather than trusted to the UI, because
the outcome dataset is the product's most valuable asset and a client bug that
records a WON against an application that was never APPLIED would corrupt it
silently. Every rejected transition raises with a message the UI can show.

The money rule this module enforces: **EARNED income exists only because a user
entered it.** Recording a win asks for the actual figure rather than copying
the opportunity's published range - those are different numbers, the second is
frequently wrong, and the difference between them is precisely the data that
makes the product's future recommendations better.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime

from app.domain.enums import (
    ALLOWED_TRANSITIONS,
    STATUS_TO_MONEY_STATE,
    ApplicationStatus,
    CompensationPeriod,
    MoneyState,
    TaxTreatment,
)
from app.domain.evidence import utcnow
from app.logging_config import Event, log_event

logger = logging.getLogger(__name__)


class InvalidTransitionError(ValueError):
    """A transition the state machine does not permit."""

    def __init__(self, current: ApplicationStatus, target: ApplicationStatus) -> None:
        allowed = ", ".join(sorted(s.value for s in ALLOWED_TRANSITIONS[current]))
        super().__init__(
            f"Cannot move from {current.value} to {target.value}. "
            f"Allowed from here: {allowed or 'nothing'}."
        )
        self.current = current
        self.target = target


@dataclass(frozen=True)
class OutcomeRecord:
    """What the user enters when they mark an application WON.

    Every field is what *actually happened*, not what was advertised. Hours
    spent is optional but requested, because compensation divided by real hours
    is the only honest measure of whether an opportunity was worth pursuing -
    and it is the signal that makes ranking better over time.
    """

    amount_minor: int
    currency: str = "EUR"
    tax_treatment: TaxTreatment = TaxTreatment.UNKNOWN
    period: CompensationPeriod = CompensationPeriod.ONE_TIME
    hours_spent: float | None = None
    occurred_on: date | None = None
    notes: str | None = None

    def validate(self) -> None:
        if self.amount_minor < 0:
            raise ValueError("Amount cannot be negative.")
        if self.hours_spent is not None and self.hours_spent < 0:
            raise ValueError("Hours spent cannot be negative.")


def can_transition(current: ApplicationStatus, target: ApplicationStatus) -> bool:
    return target in ALLOWED_TRANSITIONS[current]


def transition(
    current: ApplicationStatus,
    target: ApplicationStatus,
    history: list[dict[str, str]],
    *,
    now: datetime | None = None,
) -> tuple[ApplicationStatus, list[dict[str, str]]]:
    """Validate and apply a transition, appending to the history.

    History is append-only and carries both endpoints of every move. That is
    what lets "how long from saved to applied?" and "which categories do people
    abandon at preparation?" be answered later - questions the product needs to
    answer to know whether it is working.
    """
    if current is target:
        return current, history
    if not can_transition(current, target):
        raise InvalidTransitionError(current, target)

    stamp = (now or utcnow()).isoformat()
    updated = [*history, {"from": current.value, "to": target.value, "at": stamp}]
    log_event(
        logger,
        Event.APPLICATION_TRANSITIONED,
        "application status changed",
        from_status=current.value,
        to_status=target.value,
    )
    return target, updated


def money_state_for(status: ApplicationStatus) -> MoneyState:
    """The money state a status implies. Never upgraded by anything else."""
    return STATUS_TO_MONEY_STATE[status]


def requires_outcome(target: ApplicationStatus) -> bool:
    """Whether reaching this status should prompt for a real figure."""
    return target is ApplicationStatus.WON


def days_between(earlier: datetime | None, later: datetime | None) -> int | None:
    if earlier is None or later is None:
        return None
    return max(0, (later - earlier).days)


DEFAULT_CHECKLIST: tuple[str, ...] = (
    "Read the original listing in full on the source page",
    "Confirm the deadline is still current",
    "Confirm what the work actually pays, and whether that is gross or net",
    "Check the eligibility conditions against your own situation",
    "Check whether your employment contract requires notification",
    "Prepare or update the documents the organisation asks for",
)

#: Documents commonly requested, by opportunity shape. A starting list the user
#: edits - not a claim about what this particular organisation wants, which
#: only their page can tell us.
DOCUMENTS_BY_SHAPE: dict[str, tuple[str, ...]] = {
    "self_employed": (
        "Short professional profile or CV",
        "Rate card or expected day/hourly rate",
        "Tax number or VAT ID, if you already have one",
    ),
    "employment": ("CV", "Cover letter", "Certificates or references"),
    "grant": (
        "Project description",
        "Budget outline",
        "CV of the applicant",
        "Any eligibility evidence the programme asks for",
    ),
}


def starter_checklist(shape: str) -> dict[str, list[str]]:
    """Opening contents of the action workspace. Entirely user-editable."""
    return {
        "checklist": list(DEFAULT_CHECKLIST),
        "documents_needed": list(
            DOCUMENTS_BY_SHAPE.get(shape, DOCUMENTS_BY_SHAPE["self_employed"])
        ),
        "questions_to_verify": [
            "Is the compensation figure confirmed, and is it gross or net?",
            "What is the actual time commitment, including unpaid preparation?",
            "When would the first payment arrive?",
        ],
    }
