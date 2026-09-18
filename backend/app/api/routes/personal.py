"""The personal page: what you already earn, what it costs, who is at home.

This is the one part of the product where a user types money figures about
their own life rather than about an opportunity, so two rules are enforced at
this boundary and not left to the client:

1. **A figure keeps the basis it was given.** ``basis`` travels with every
   amount, in and out. No endpoint here accepts a net figure and returns a
   gross one, because nothing behind it can do that conversion honestly - it
   needs the Steuerklasse, insurance and federal state, and performing it for
   an individual is Steuerberatung.

2. **Recording is not deciding.** Expenses are the user's own records, added
   up. No response carries a deductible amount, a tax rate or a tax saved, and
   ``ExpenseSummaryDto`` has no field for one.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import dto, mappers
from app.api.deps import current_user, get_db, get_legal_facts, rate_limit, settings_dep
from app.config import Settings
from app.db.models import (
    BaselineIncomeRow,
    ExpenseRow,
    IncomeEvent,
    Opportunity,
    Profile,
    ProfileSkill,
    SavedOpportunity,
    User,
)
from app.domain.enums import AmountBasis, CompensationPeriod, IncomeStreamCategory, Tristate
from app.domain.finances import (
    BaselineIncome,
    Child,
    DeductibleExpense,
    HouseholdContext,
)
from app.services import finances, statements
from app.services import leaks as leaks_service
from app.services.legal_facts import LegalFactRepository

router = APIRouter(prefix="/api/personal", tags=["personal"], dependencies=[Depends(rate_limit)])


def _profile(session: Session, user_id: str) -> Profile | None:
    return session.scalars(select(Profile).where(Profile.user_id == user_id)).first()


def _baseline_dto(row: BaselineIncomeRow) -> dto.BaselineIncomeDto:
    entry = BaselineIncome(
        label=row.label,
        amount_minor=row.amount_minor,
        currency=row.currency,
        basis=row.basis,
        period=row.period,
        is_primary=row.is_primary,
        started_on=row.started_on,
    )
    return dto.BaselineIncomeDto(
        id=row.id,
        label=entry.label,
        amount_minor=entry.amount_minor,
        currency=entry.currency,
        basis=entry.basis,
        period=entry.period,
        is_primary=entry.is_primary,
        started_on=entry.started_on,
        monthly_minor=entry.monthly_minor(),
    )


def _expense_dto(row: ExpenseRow) -> dto.ExpenseDto:
    return dto.ExpenseDto(
        id=row.id,
        label=row.label,
        amount_minor=row.amount_minor,
        currency=row.currency,
        category=row.category,
        incurred_on=row.incurred_on,
        has_receipt=row.has_receipt,
        partly_private=row.partly_private,
        income_stream_id=row.income_stream_id,
        application_id=row.application_id,
        notes=row.notes,
    )


# ------------------------------------------------------------- overview


@router.get("/overview", response_model=dto.PersonalOverviewDto)
def overview(
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
    facts: LegalFactRepository = Depends(get_legal_facts),
) -> dto.PersonalOverviewDto:
    """Everything the personal page shows, in one call."""
    profile = _profile(session, user.id)
    picture = finances.load_baseline(session, user.id)
    summary = finances.expense_summary(session, user.id)
    household = finances.load_household(profile)

    goal = profile.desired_additional_monthly_minor if profile else None
    usable_facts, questions = finances.deduction_context(facts.all(session), household)

    rows = session.scalars(
        select(BaselineIncomeRow)
        .where(BaselineIncomeRow.user_id == user.id)
        .order_by(BaselineIncomeRow.is_primary.desc(), BaselineIncomeRow.label)
    ).all()

    return dto.PersonalOverviewDto(
        baseline=dto.BaselinePictureDto(
            entries=[_baseline_dto(row) for row in rows],
            currency=picture.currency,
            net_monthly_minor=picture.net_monthly_minor,
            gross_monthly_minor=picture.gross_monthly_minor,
            unlabelled_monthly_minor=picture.unlabelled_monthly_minor,
            one_off_minor=picture.one_off_minor,
            notes=picture.notes(),
        ),
        expenses=dto.ExpenseSummaryDto(
            currency=summary.currency,
            total_minor=summary.total_minor,
            count=summary.count,
            by_category=[
                dto.CategoryTotalDto(
                    category=row.category,
                    total_minor=row.total_minor,
                    count=row.count,
                    without_receipt=row.without_receipt,
                    partly_private=row.partly_private,
                )
                for row in summary.by_category
            ],
            without_receipt_count=summary.without_receipt_count,
            questions_to_check=summary.questions_to_check,
            disclaimer=summary.disclaimer,
        ),
        household=dto.HouseholdDto(
            has_children=household.has_children,
            jointly_assessed=household.jointly_assessed,
            children=[
                dto.ChildDto(
                    label=child.label,
                    age_years=child.age_years,
                    in_education_or_training=child.in_education_or_training,
                )
                for child in household.children
            ],
            disclosed=household.disclosed,
        ),
        goal_monthly_minor=goal,
        uplift_ratio=picture.uplift_ratio(goal),
        facts=[
            dto.LegalFactDto(
                id=fact.id,
                category=fact.category.value,
                title=fact.title,
                summary=fact.summary,
                structured_value=fact.structured_value,
                effective_from=fact.effective_from,
                effective_to=fact.effective_to,
                source_name=fact.source_name,
                source_url=str(fact.source_url) if fact.source_url else None,
                last_verified_at=fact.last_verified_at,
                trust=facts.trust(fact),
                status=fact.effective_status(max_age=facts.max_age).value,
            )
            for fact in usable_facts
        ],
        questions_to_check=questions,
    )


# ------------------------------------------------------- baseline income


@router.get("/income", response_model=list[dto.BaselineIncomeDto])
def list_income(
    user: User = Depends(current_user), session: Session = Depends(get_db)
) -> list[dto.BaselineIncomeDto]:
    rows = session.scalars(
        select(BaselineIncomeRow)
        .where(BaselineIncomeRow.user_id == user.id)
        .order_by(BaselineIncomeRow.is_primary.desc(), BaselineIncomeRow.label)
    ).all()
    return [_baseline_dto(row) for row in rows]


@router.post("/income", response_model=dto.BaselineIncomeDto, status_code=status.HTTP_201_CREATED)
def add_income(
    payload: dto.BaselineIncomeRequest,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dto.BaselineIncomeDto:
    row = BaselineIncomeRow(
        user_id=user.id,
        label=payload.label,
        amount_minor=payload.amount_minor,
        basis=payload.basis.value,
        period=payload.period.value,
        is_primary=payload.is_primary,
        started_on=payload.started_on,
    )
    session.add(row)
    session.flush()
    if payload.is_primary:
        finances.demote_other_primaries(session, user.id, row.id)
    session.commit()
    return _baseline_dto(row)


@router.delete("/income/{income_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_income(
    income_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> None:
    row = session.get(BaselineIncomeRow, income_id)
    if row is None or row.user_id != user.id:
        # Same response either way: whether an id exists is not something an
        # unrelated account should be able to learn.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    session.delete(row)
    session.commit()


# ------------------------------------------------------------- expenses


@router.get("/expenses", response_model=list[dto.ExpenseDto])
def list_expenses(
    user: User = Depends(current_user), session: Session = Depends(get_db)
) -> list[dto.ExpenseDto]:
    rows = session.scalars(
        select(ExpenseRow)
        .where(ExpenseRow.user_id == user.id)
        .order_by(ExpenseRow.incurred_on.desc())
    ).all()
    return [_expense_dto(row) for row in rows]


@router.post("/expenses", response_model=dto.ExpenseDto, status_code=status.HTTP_201_CREATED)
def add_expense(
    payload: dto.ExpenseRequest,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dto.ExpenseDto:
    # Validate through the domain type first, so the "one parent only" rule is
    # enforced by the same code the rest of the product uses rather than by a
    # second copy of it here.
    try:
        DeductibleExpense(
            label=payload.label,
            amount_minor=payload.amount_minor,
            category=payload.category,
            incurred_on=payload.incurred_on,
            has_receipt=payload.has_receipt,
            partly_private=payload.partly_private,
            income_stream_id=payload.income_stream_id,
            application_id=payload.application_id,
            notes=payload.notes,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from error

    row = ExpenseRow(
        user_id=user.id,
        label=payload.label,
        amount_minor=payload.amount_minor,
        category=payload.category.value,
        incurred_on=payload.incurred_on,
        has_receipt=payload.has_receipt.value,
        partly_private=payload.partly_private.value,
        income_stream_id=payload.income_stream_id,
        application_id=payload.application_id,
        notes=payload.notes,
    )
    session.add(row)
    session.commit()
    return _expense_dto(row)


@router.delete("/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(
    expense_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> None:
    row = session.get(ExpenseRow, expense_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    session.delete(row)
    session.commit()


# ------------------------------------------------------------ household


@router.put("/household", response_model=dto.HouseholdDto)
def set_household(
    payload: dto.HouseholdRequest,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dto.HouseholdDto:
    """Record what the user has explicitly told us. Nothing is inferred."""
    profile = _profile(session, user.id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Create your profile before adding household details.",
        )

    try:
        household = HouseholdContext(
            has_children=payload.has_children,
            jointly_assessed=payload.jointly_assessed,
            children=[
                Child(
                    label=child.label,
                    age_years=child.age_years,
                    in_education_or_training=child.in_education_or_training,
                )
                for child in payload.children
            ],
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from error

    finances.store_household(profile, household)
    session.commit()

    return dto.HouseholdDto(
        has_children=household.has_children,
        jointly_assessed=household.jointly_assessed,
        children=payload.children,
        disclosed=household.disclosed,
    )


# --------------------------------------------------- money you may be losing


def _engaged_categories(session: Session, user_id: str) -> frozenset[IncomeStreamCategory]:
    """Categories the user has actually engaged with, not ones merely shown.

    A finding raised because an opportunity happened to appear in a search is
    noise; one raised because the user saved it is about them.
    """
    rows = session.scalars(
        select(Opportunity.category)
        .join(SavedOpportunity, SavedOpportunity.opportunity_id == Opportunity.id)
        .where(SavedOpportunity.user_id == user_id)
    ).all()
    out: set[IncomeStreamCategory] = set()
    for value in rows:
        try:
            out.add(IncomeStreamCategory(value))
        except ValueError:
            continue
    return frozenset(out)


@router.get("/leaks", response_model=dto.LeaksResponse)
def money_you_may_be_losing(
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
    facts: LegalFactRepository = Depends(get_legal_facts),
) -> dto.LeaksResponse:
    """The second direction: money already passing you by.

    Every finding is triggered by something in the user's own data and cites a
    stored legal fact, or carries no figure at all. See `services/leaks.py`.
    """
    profile_row = _profile(session, user.id)
    profile = None
    if profile_row is not None:
        skills = session.scalars(
            select(ProfileSkill).where(ProfileSkill.profile_id == profile_row.id)
        ).all()
        profile = mappers.profile_row_to_domain(profile_row, list(skills))

    earned = sum(
        row.amount_minor
        for row in session.scalars(
            select(IncomeEvent).where(IncomeEvent.user_id == user.id)
        ).all()
    )

    found = leaks_service.detect_leaks(
        profile=profile,
        baseline=finances.load_baseline(session, user.id),
        expenses=finances.expense_summary(session, user.id),
        household=finances.load_household(profile_row),
        engaged_categories=_engaged_categories(session, user.id),
        earned_total_minor=earned,
        facts=facts.all(session),
    )
    counts = leaks_service.summarise_leaks(found)

    return dto.LeaksResponse(
        leaks=[
            dto.LeakDto(
                id=leak.id,
                title=leak.title,
                why_this_applies=leak.why_this_applies,
                what_to_check=leak.what_to_check,
                fact_ids=leak.fact_ids,
                stated_amount_minor=leak.stated_amount_minor,
                amount_note=leak.amount_note,
            )
            for leak in found
        ],
        total=counts["total"],
        with_sources=counts["with_sources"],
    )


# ------------------------------------------------------- the two numbers

#: The label given to the baseline entry the A-to-B band creates. Recognisable
#: on the personal page, so a figure typed on the dashboard does not appear
#: there as a mystery row.
BAND_INCOME_LABEL = "Current income"


def _targets(session: Session, user_id: str, profile: Profile | None) -> dto.TargetsDto:
    picture = finances.load_baseline(session, user_id)
    current = picture.net_monthly_minor or picture.gross_monthly_minor
    additional = (profile.desired_additional_monthly_minor if profile else None) or 0

    # The stored target is the user's own figure and is returned unchanged.
    # Falling back to current + additional covers everyone who set a goal
    # before this column existed, and matches what the band used to show.
    stored = profile.target_monthly_minor if profile else None
    target = stored if stored is not None else current + additional

    return dto.TargetsDto(
        current_monthly_minor=current,
        target_monthly_minor=target,
        additional_needed_minor=max(0, target - current),
        target_reached=target <= current,
        currency=picture.currency,
    )


@router.get("/targets", response_model=dto.TargetsDto)
def read_targets(
    user: User = Depends(current_user), session: Session = Depends(get_db)
) -> dto.TargetsDto:
    return _targets(session, user.id, _profile(session, user.id))


@router.put("/targets", response_model=dto.TargetsDto)
def set_targets(
    payload: dto.TargetsRequest,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dto.TargetsDto:
    """Set where you are and where you want to be, in one call.

    The profile stores the *additional* income being aimed for, so the target
    is converted here. A target below the current income means the gap is zero
    rather than negative - the product does not ask anyone to earn less.
    """
    profile = _profile(session, user.id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Create your profile before setting these.",
        )

    # A single recurring entry stands for "what I earn now". If the user has
    # several, the band edits the primary one and leaves the rest alone -
    # overwriting a carefully entered list from a one-box edit would be rude.
    primary = session.scalars(
        select(BaselineIncomeRow)
        .where(BaselineIncomeRow.user_id == user.id)
        .order_by(BaselineIncomeRow.is_primary.desc(), BaselineIncomeRow.label)
    ).first()

    if primary is None:
        primary = BaselineIncomeRow(
            user_id=user.id,
            label=BAND_INCOME_LABEL,
            amount_minor=payload.current_monthly_minor,
            basis=AmountBasis.NET.value,
            period=CompensationPeriod.RECURRING.value,
            is_primary=True,
        )
        session.add(primary)
        session.flush()
        finances.demote_other_primaries(session, user.id, primary.id)
    else:
        primary.amount_minor = payload.current_monthly_minor
        # The basis is left exactly as the user set it. Guessing "net" over an
        # entry they marked gross would quietly restate their own figure.

    # Both are stored: the target because it is what the user said, and the
    # additional because that is what the matcher scores against. Deriving the
    # target back from the additional would lose any target at or below the
    # current income, which is the case this pair exists to keep honest.
    profile.target_monthly_minor = payload.target_monthly_minor
    profile.desired_additional_monthly_minor = max(
        0, payload.target_monthly_minor - payload.current_monthly_minor
    )
    session.commit()
    return _targets(session, user.id, profile)


# -------------------------------------------------- bank statement import

#: The formats a Sparkasse account actually produces. PDF is included because
#: it is what the bank sends by default, and the parser proves what it read by
#: reconciling against the statement's own opening and closing balance.
STATEMENT_SUFFIXES = (".csv", ".xml", ".txt", ".camt", ".pdf")


@router.post("/statements/preview", response_model=dto.StatementPreviewDto)
async def preview_statement(
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    settings: Settings = Depends(settings_dep),
) -> dto.StatementPreviewDto:
    """Read an exported statement and propose what could be recorded.

    Nothing is written. This endpoint exists so the user can see the file's
    contents, and our suggestions, before anything touches their records - and
    so that no banking credential is ever involved: they export the file
    themselves from their own online banking.
    """
    del user  # authentication only; the file is not stored against the account

    name = (file.filename or "statement").lower()
    if not name.endswith(STATEMENT_SUFFIXES):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Upload the statement your bank produced: the PDF it sends, or a "
                "CSV-CAMT or CAMT.053 export. Screenshots and spreadsheets you "
                "have edited cannot be checked against a balance."
            ),
        )

    # Read with a ceiling, like the CV upload: checking the size after reading
    # the whole stream would mean paying the memory cost before enforcing it.
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="That file is larger than we accept. Export a shorter period.",
        )

    try:
        result = statements.preview(data, name)
    except statements.StatementRowError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)
        ) from error

    return dto.StatementPreviewDto(
        rows=[
            dto.SuggestedExpenseDto(
                row=dto.StatementRowDto(
                    booked_on=item.row.booked_on,
                    amount_minor=item.row.amount_minor,
                    currency=item.row.currency,
                    counterparty=item.row.counterparty,
                    reference=item.row.reference,
                ),
                suggested=item.suggested,
                category=item.category,
                reason=item.reason,
            )
            for item in result.rows
        ],
        total_rows=result.total_rows,
        outgoing_rows=result.outgoing_rows,
        suggested_rows=result.suggested_rows,
        currency=result.currency,
        note=result.note,
    )


@router.post("/statements/import", response_model=dto.StatementImportResult)
def import_statement(
    payload: dto.StatementImportRequest,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dto.StatementImportResult:
    """Record the lines the user picked, with the categories the user chose.

    The server does not re-read the file and does not decide anything: it takes
    the list the user confirmed. Amounts arrive positive because an expense is
    a cost, and the statement's minus sign has already served its purpose in
    telling the user which lines were money leaving.
    """
    for item in payload.items:
        session.add(
            ExpenseRow(
                user_id=user.id,
                label=item.label,
                amount_minor=item.amount_minor,
                category=item.category.value,
                incurred_on=item.incurred_on,
                # Imported rather than typed, so the receipt question is open
                # rather than answered. A bank line is evidence of payment, not
                # the invoice a Finanzamt would ask for.
                has_receipt=Tristate.UNKNOWN.value,
                notes=item.notes,
            )
        )
    session.commit()
    return dto.StatementImportResult(imported=len(payload.items))
