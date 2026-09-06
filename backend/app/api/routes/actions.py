"""Save, dismiss, the action workspace, tracking and recorded income."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import dto, mappers
from app.api.deps import current_user, get_db, get_provider, rate_limit
from app.db.models import (
    Application,
    IncomeEvent,
    IncomeStream,
    Profile,
    ProfileSkill,
    SavedOpportunity,
    User,
)
from app.db.models import Opportunity as OpportunityRow
from app.domain.enums import (
    ApplicationStatus,
    CompensationPeriod,
    IncomeStreamStatus,
    TaxTreatment,
)
from app.llm import prompts
from app.llm.base import LLMError, LLMProvider, Purpose
from app.logging_config import Event, log_event
from app.services import analytics, applications
from app.services.applications import InvalidTransitionError, OutcomeRecord
from app.services.explanation import render_opportunity
from app.services.germany_check import GermanyCheckService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["actions"], dependencies=[Depends(rate_limit)])

VALID_DRAFT_KINDS = frozenset({"bio", "cover_letter", "pitch", "short_answer", "outreach"})


def _opportunity(session: Session, opportunity_id: str) -> OpportunityRow:
    row = session.get(OpportunityRow, opportunity_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    return row


def _application(session: Session, user_id: str, application_id: str) -> Application:
    row = session.get(Application, application_id)
    # Ownership is checked here, not by trusting an id from the client.
    if row is None or row.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    return row


def _to_dto(session: Session, row: Application) -> dto.ApplicationDto:
    opportunity = session.get(OpportunityRow, row.opportunity_id)
    return dto.ApplicationDto(
        id=row.id,
        opportunity_id=row.opportunity_id,
        opportunity_title=opportunity.title if opportunity else "(removed)",
        organization=opportunity.organization if opportunity else None,
        status=ApplicationStatus(row.status),
        money_state=applications.money_state_for(ApplicationStatus(row.status)).value,
        status_history=row.status_history.get("items", []),
        checklist=row.checklist.get("items", []),
        documents_needed=row.documents_needed,
        questions_to_verify=row.questions_to_verify,
        notes=row.notes,
        drafts={k: str(v) for k, v in row.drafts.items()},
        reminder_at=row.reminder_at,
        applied_at=row.applied_at,
    )


# ---------------------------------------------------------------- save


@router.post("/opportunities/{opportunity_id}/save", response_model=dto.ApplicationDto)
def save_opportunity(
    opportunity_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dto.ApplicationDto:
    """Save an opportunity and open its action workspace."""
    opportunity = _opportunity(session, opportunity_id)

    saved = session.execute(
        select(SavedOpportunity).where(
            SavedOpportunity.user_id == user.id,
            SavedOpportunity.opportunity_id == opportunity_id,
        )
    ).scalar_one_or_none()
    if saved is None:
        session.add(SavedOpportunity(user_id=user.id, opportunity_id=opportunity_id))
    else:
        # Un-dismiss: the user changed their mind.
        saved.dismissed_at = None
        saved.dismiss_reason = None

    application = session.execute(
        select(Application).where(
            Application.user_id == user.id, Application.opportunity_id == opportunity_id
        )
    ).scalar_one_or_none()
    if application is None:
        shape = GermanyCheckService._shape(mappers.row_to_opportunity(opportunity))
        starter = applications.starter_checklist(shape)
        application = Application(
            user_id=user.id,
            opportunity_id=opportunity_id,
            status=ApplicationStatus.SAVED.value,
            status_history={
                "items": [
                    {
                        "from": ApplicationStatus.DISCOVERED.value,
                        "to": ApplicationStatus.SAVED.value,
                        "at": datetime.now(UTC).isoformat(),
                    }
                ]
            },
            checklist={"items": [{"label": item, "done": False} for item in starter["checklist"]]},
            documents_needed=starter["documents_needed"],
            questions_to_verify=starter["questions_to_verify"],
        )
        session.add(application)
    session.flush()

    analytics.record(
        session,
        "opportunity_saved",
        user_id=user.id,
        category=opportunity.category,
        match_score=0,
        actionability="",
    )
    log_event(logger, Event.OPPORTUNITY_SAVED, "opportunity saved")
    return _to_dto(session, application)


@router.post("/opportunities/{opportunity_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
def dismiss_opportunity(
    opportunity_id: str,
    payload: dto.DismissRequest,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> None:
    """Dismiss with a reason. The reason is the learning signal.

    A dismissal with no reason teaches nothing. The reason maps to one named
    weight adjustment in :mod:`app.services.learning`, which the user can read
    and reset.
    """
    opportunity = _opportunity(session, opportunity_id)
    row = session.execute(
        select(SavedOpportunity).where(
            SavedOpportunity.user_id == user.id,
            SavedOpportunity.opportunity_id == opportunity_id,
        )
    ).scalar_one_or_none()
    if row is None:
        row = SavedOpportunity(user_id=user.id, opportunity_id=opportunity_id)
        session.add(row)
    row.dismissed_at = datetime.now(UTC)
    row.dismiss_reason = payload.reason.value
    row.dismiss_note = payload.note

    analytics.record(
        session,
        "opportunity_dismissed",
        user_id=user.id,
        category=opportunity.category,
        match_score=0,
        reason=payload.reason.value,
    )
    log_event(logger, Event.OPPORTUNITY_DISMISSED, "dismissed", reason=payload.reason.value)


# ------------------------------------------------------------ workspace


@router.get("/applications", response_model=list[dto.ApplicationDto])
def list_applications(
    user: User = Depends(current_user), session: Session = Depends(get_db)
) -> list[dto.ApplicationDto]:
    rows = session.execute(
        select(Application)
        .where(Application.user_id == user.id)
        .order_by(Application.updated_at.desc())
    ).scalars()
    return [_to_dto(session, row) for row in rows]


@router.get("/applications/{application_id}", response_model=dto.ApplicationDto)
def read_application(
    application_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dto.ApplicationDto:
    return _to_dto(session, _application(session, user.id, application_id))


@router.patch("/applications/{application_id}", response_model=dto.ApplicationDto)
def update_workspace(
    application_id: str,
    payload: dto.WorkspaceUpdateRequest,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dto.ApplicationDto:
    row = _application(session, user.id, application_id)
    if payload.checklist is not None:
        row.checklist = {"items": payload.checklist}
    if payload.documents_needed is not None:
        row.documents_needed = payload.documents_needed
    if payload.questions_to_verify is not None:
        row.questions_to_verify = payload.questions_to_verify
    if payload.notes is not None:
        row.notes = payload.notes
    if payload.reminder_at is not None:
        row.reminder_at = payload.reminder_at
    return _to_dto(session, row)


@router.post("/applications/{application_id}/status", response_model=dto.ApplicationDto)
def transition_status(
    application_id: str,
    payload: dto.TransitionRequest,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dto.ApplicationDto:
    """Move through the tracking state machine. Invalid moves are refused.

    Reaching WON requires a real figure. That is not bureaucracy: the whole
    point of tracking is that EARNED money is money the user says they actually
    received, and copying the listing's advertised range would destroy exactly
    the data that makes this product's outcome dataset worth anything.
    """
    row = _application(session, user.id, application_id)
    current = ApplicationStatus(row.status)
    target = payload.status

    # Validate the move before asking for anything about it. Telling someone
    # "we need the amount you were paid" for a transition that is not legal in
    # the first place sends them looking for the wrong problem.
    try:
        new_status, history = applications.transition(
            current, target, row.status_history.get("items", [])
        )
    except InvalidTransitionError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    if applications.requires_outcome(target) and payload.outcome is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "To record this as won, tell us what it actually paid. We do not copy the "
                "advertised amount - the difference between the two is the useful part."
            ),
        )

    row.status = new_status.value
    row.status_history = {"items": history}
    if new_status is ApplicationStatus.APPLIED and row.applied_at is None:
        row.applied_at = datetime.now(UTC)
        analytics.record(
            session,
            "application_marked_applied",
            user_id=user.id,
            category=_opportunity(session, row.opportunity_id).category,
            days_from_save=applications.days_between(row.created_at, row.applied_at) or 0,
        )
    if new_status in {ApplicationStatus.WON, ApplicationStatus.LOST}:
        row.closed_at = datetime.now(UTC)

    if payload.outcome is not None and new_status is ApplicationStatus.WON:
        _record_outcome(session, user, row, payload.outcome)

    if new_status is ApplicationStatus.OFFERED:
        analytics.record(
            session,
            "opportunity_offered",
            user_id=user.id,
            category=_opportunity(session, row.opportunity_id).category,
        )
    if new_status is ApplicationStatus.LOST:
        analytics.record(
            session,
            "opportunity_lost",
            user_id=user.id,
            category=_opportunity(session, row.opportunity_id).category,
        )
    return _to_dto(session, row)


def _record_outcome(
    session: Session, user: User, application: Application, payload: dto.OutcomeRequest
) -> None:
    record = OutcomeRecord(
        amount_minor=payload.amount_minor,
        currency=payload.currency,
        tax_treatment=TaxTreatment(payload.tax_treatment),
        period=CompensationPeriod(payload.period),
        hours_spent=payload.hours_spent,
        occurred_on=payload.occurred_on,
        notes=payload.notes,
    )
    try:
        record.validate()
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

    opportunity = _opportunity(session, application.opportunity_id)
    stream = IncomeStream(
        user_id=user.id,
        label=opportunity.title[:160],
        category=opportunity.category,
        # ACTIVE only because the money is now SECURED. The check constraint on
        # income_streams enforces that pairing at the storage layer.
        status=IncomeStreamStatus.ACTIVE.value,
        money_state="SECURED",
        amount_minor=record.amount_minor,
        currency=record.currency,
        period=record.period.value,
        tax_treatment=record.tax_treatment.value,
    )
    session.add(stream)
    session.flush()

    session.add(
        IncomeEvent(
            user_id=user.id,
            application_id=application.id,
            income_stream_id=stream.id,
            label=opportunity.title[:200],
            amount_minor=record.amount_minor,
            currency=record.currency,
            tax_treatment=record.tax_treatment.value,
            period=record.period.value,
            money_state="SECURED",
            hours_spent=record.hours_spent,
            occurred_on=record.occurred_on or date.today(),
            notes=record.notes,
        )
    )
    analytics.record(
        session,
        "opportunity_won",
        user_id=user.id,
        category=opportunity.category,
        days_from_applied=applications.days_between(application.applied_at, datetime.now(UTC))
        or 0,
    )
    analytics.record(
        session,
        "income_recorded",
        user_id=user.id,
        category=opportunity.category,
        amount_bucket=analytics.amount_bucket(record.amount_minor),
        period=record.period.value,
    )
    log_event(logger, Event.INCOME_RECORDED, "income recorded")


@router.post("/income", status_code=status.HTTP_201_CREATED)
def record_income(
    payload: dto.OutcomeRequest,
    label: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    """Record income not tied to a tracked application.

    Someone's existing side income belongs on the Money Map too; the product is
    about their whole income picture, not only what it found them.
    """
    event = IncomeEvent(
        user_id=user.id,
        label=label[:200],
        amount_minor=payload.amount_minor,
        currency=payload.currency,
        tax_treatment=payload.tax_treatment,
        period=payload.period,
        money_state="EARNED",
        hours_spent=payload.hours_spent,
        occurred_on=payload.occurred_on or date.today(),
        notes=payload.notes,
    )
    session.add(event)
    session.flush()
    analytics.record(
        session,
        "income_recorded",
        user_id=user.id,
        category="OTHER",
        amount_bucket=analytics.amount_bucket(payload.amount_minor),
        period=payload.period,
    )
    return {"id": event.id}


@router.get("/income")
def list_income(
    user: User = Depends(current_user), session: Session = Depends(get_db)
) -> list[dict[str, object]]:
    return [
        {
            "id": row.id,
            "label": row.label,
            "amount_minor": row.amount_minor,
            "currency": row.currency,
            "period": row.period,
            "tax_treatment": row.tax_treatment,
            "money_state": row.money_state,
            "hours_spent": row.hours_spent,
            "occurred_on": row.occurred_on,
        }
        for row in session.execute(
            select(IncomeEvent)
            .where(IncomeEvent.user_id == user.id)
            .order_by(IncomeEvent.occurred_on.desc())
        ).scalars()
    ]


# ---------------------------------------------------------------- drafts


@router.post("/applications/{application_id}/draft", response_model=dto.DraftResponse)
def write_draft(
    application_id: str,
    payload: dto.DraftRequest,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
    provider: LLMProvider = Depends(get_provider),
) -> dto.DraftResponse:
    """Draft application text. The user reviews and sends it themselves.

    Nothing is submitted anywhere by this system, in P0 or otherwise without an
    explicit product decision - see docs/ROADMAP.md.
    """
    if payload.kind not in VALID_DRAFT_KINDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown draft kind. Choose one of: {', '.join(sorted(VALID_DRAFT_KINDS))}.",
        )
    if not provider.available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Draft writing is unavailable right now. Your saved opportunity and "
                "notes are safe, and the requirements checklist still works."
            ),
        )

    row = _application(session, user.id, application_id)
    opportunity = mappers.row_to_opportunity(_opportunity(session, row.opportunity_id))
    profile_row = session.execute(
        select(Profile).where(Profile.user_id == user.id)
    ).scalar_one_or_none()
    if profile_row is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No profile yet.")
    skills = list(
        session.execute(
            select(ProfileSkill).where(ProfileSkill.profile_id == profile_row.id)
        ).scalars()
    )
    profile = mappers.profile_row_to_domain(profile_row, skills)

    from pydantic import BaseModel, ConfigDict, Field

    class Draft(BaseModel):
        model_config = ConfigDict(extra="forbid")

        text: str = Field(max_length=4000)
        placeholders: list[str] = Field(
            default_factory=list,
            description="Anything the profile did not evidence, left for the user to complete.",
        )

    profile_summary = "\n".join(
        [
            f"Role: {profile.professional.current_role or 'not stated'}",
            f"Years: {profile.professional.years_experience or 'not stated'}",
            "Skills: " + ", ".join(s.name for s in profile.professional.skills),
            "Education: "
            + "; ".join(e.qualification for e in profile.professional.education),
        ]
    )
    try:
        draft = provider.structured(
            Draft,
            prompts.application_draft_messages(
                render_opportunity(opportunity), profile_summary, payload.kind
            ),
            purpose=Purpose.APPLICATION_DRAFT,
        )
    except LLMError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="We could not write a draft right now. Your saved data is safe.",
        ) from error

    row.drafts = {**row.drafts, payload.kind: draft.text}
    analytics.record(
        session,
        "application_prepared",
        user_id=user.id,
        category=_opportunity(session, row.opportunity_id).category,
        draft_kind=payload.kind,
    )
    return dto.DraftResponse(kind=payload.kind, text=draft.text)
