"""Onboarding and profile management: upload, paste, manual, review, confirm."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import dto, mappers
from app.api.deps import current_user, get_db, get_guard, get_provider, rate_limit, settings_dep
from app.api.routes.auth import CV_CONSENT
from app.config import Settings
from app.db.models import ConsentRecord, CvDocument, Profile, ProfileSkill, User
from app.llm.base import LLMProvider
from app.logging_config import Event, hash_user_id, log_event
from app.security.guard import InjectionGuard
from app.security.uploads import (
    UploadRejectedError,
    delete_stored,
    extract_text,
    store,
    validate_upload,
)
from app.services import analytics
from app.services.cv_parsing import CvParser, CvParsingUnavailableError, draft_from_text

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/profile", tags=["profile"], dependencies=[Depends(rate_limit)])


def _profile_row(session: Session, user: User) -> Profile:
    row = session.execute(select(Profile).where(Profile.user_id == user.id)).scalar_one_or_none()
    if row is None:
        row = Profile(user_id=user.id)
        session.add(row)
        session.flush()
    return row


def _skills(session: Session, profile_id: str) -> list[ProfileSkill]:
    return list(
        session.execute(select(ProfileSkill).where(ProfileSkill.profile_id == profile_id)).scalars()
    )


def _record_consent(session: Session, user_id: str) -> None:
    existing = session.execute(
        select(ConsentRecord).where(
            ConsentRecord.user_id == user_id,
            ConsentRecord.purpose == "cv_processing",
            ConsentRecord.withdrawn_at.is_(None),
        )
    ).scalar_one_or_none()
    if existing is None:
        session.add(
            ConsentRecord(user_id=user_id, purpose="cv_processing", statement=CV_CONSENT)
        )


def _draft_response(draft: object, source: str) -> dto.ProfileDraftResponse:
    from app.domain.profile import ProfileDraft, UserProfile

    assert isinstance(draft, ProfileDraft)
    # A draft is rendered through the same DTO as a profile so the review screen
    # and the edit screen are the same component - and so a field that exists in
    # one cannot quietly go missing from the other.
    as_profile = UserProfile(
        user_id="draft", general=draft.general, professional=draft.professional
    )
    payload = mappers.profile_to_dto(as_profile)
    return dto.ProfileDraftResponse(
        draft=payload,
        not_found=draft.not_found,
        extraction_notes=draft.extraction_notes,
        inferred_skill_count=sum(1 for s in draft.professional.skills if s.is_inferred),
        source=source,
    )


@router.get("", response_model=dto.ProfileDto)
def read_profile(
    user: User = Depends(current_user), session: Session = Depends(get_db)
) -> dto.ProfileDto:
    row = _profile_row(session, user)
    return mappers.profile_to_dto(
        mappers.profile_row_to_domain(row, _skills(session, row.id))
    )


@router.put("", response_model=dto.ProfileDto)
def update_profile(
    payload: dto.ProfileDto,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dto.ProfileDto:
    """Save the profile. Every field is editable; nothing is inferred server-side."""
    row = _profile_row(session, user)
    mappers.apply_profile_dto(row, payload)

    session.query(ProfileSkill).filter_by(profile_id=row.id).delete()
    session.flush()
    for skill_row in mappers.skill_dtos_to_rows(row.id, payload.skills):
        session.add(skill_row)
    session.flush()

    domain = mappers.profile_row_to_domain(row, _skills(session, row.id))
    return mappers.profile_to_dto(domain)


@router.post("/confirm", response_model=dto.ProfileDto)
def confirm_profile(
    user: User = Depends(current_user), session: Session = Depends(get_db)
) -> dto.ProfileDto:
    """Mark the profile reviewed. Discovery refuses to run before this.

    The gate is the product's promise in one line: nothing a model extracted
    reaches a recommendation without a human having looked at it.
    """
    row = _profile_row(session, user)
    domain = mappers.profile_row_to_domain(row, _skills(session, row.id))
    ready, missing = domain.model_copy(update={"confirmed": True}).is_ready_for_discovery()
    if not ready:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Before we can search, we still need: " + ", ".join(missing) + ".",
        )
    row.confirmed = True
    row.confirmed_at = datetime.now(UTC)
    session.flush()

    confirmed = mappers.profile_row_to_domain(row, _skills(session, row.id))
    analytics.record(
        session,
        "profile_completed",
        user_id=user.id,
        completeness=confirmed.completeness(),
        skill_count=len(confirmed.professional.skills),
        source="review",
    )
    log_event(
        logger, Event.PROFILE_CONFIRMED, "profile confirmed", user=hash_user_id(user.id)
    )
    return mappers.profile_to_dto(confirmed)


@router.post("/cv/upload", response_model=dto.ProfileDraftResponse)
async def upload_cv(
    file: UploadFile = File(...),
    consent_to_process: bool = Form(...),
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    provider: LLMProvider = Depends(get_provider),
    guard: InjectionGuard = Depends(get_guard),
) -> dto.ProfileDraftResponse:
    """Accept a CV, extract a reviewable draft, and keep the file only as long as needed."""
    if not consent_to_process:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="We need your consent before we can process your CV.",
        )

    # Read with a hard ceiling. Reading the whole stream first and checking
    # afterwards would mean the limit is enforced only once we have already paid
    # the memory cost.
    data = await file.read(settings.max_upload_bytes + 1)
    try:
        upload = validate_upload(
            filename=file.filename or "cv",
            declared_type=file.content_type or "",
            data=data,
            max_bytes=settings.max_upload_bytes,
        )
        text = extract_text(upload)
    except UploadRejectedError as error:
        log_event(
            logger,
            Event.CV_UPLOAD_REJECTED,
            "upload rejected",
            level=logging.INFO,
            reason=error.reason,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

    _record_consent(session, user.id)
    path = store(upload, settings.upload_dir)
    document = CvDocument(
        user_id=user.id,
        filename=upload.original_filename,
        content_type=upload.content_type,
        size_bytes=upload.size_bytes,
        stored_path=str(path),
        extracted_text=text,
    )
    session.add(document)

    try:
        draft = CvParser(provider, guard).parse(text)
    except CvParsingUnavailableError as error:
        # Honest degradation: the file is stored, nothing is faked, and the
        # user is offered the manual path rather than an empty "we found
        # nothing in your CV".
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from error

    return _draft_response(draft, "upload")


@router.post("/cv/paste", response_model=dto.ProfileDraftResponse)
def paste_cv(
    payload: dto.PasteProfileRequest,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
    provider: LLMProvider = Depends(get_provider),
    guard: InjectionGuard = Depends(get_guard),
) -> dto.ProfileDraftResponse:
    if not payload.consent_to_process:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="We need your consent before we can process this text.",
        )
    _record_consent(session, user.id)
    try:
        draft = CvParser(provider, guard).parse(payload.text)
    except CvParsingUnavailableError:
        # Pasted text needs no file, so the fallback can return something
        # useful: the text itself, with every field left for the user to fill.
        return _draft_response(draft_from_text(payload.text), "paste")
    return _draft_response(draft, "paste")


@router.delete("/cv", status_code=status.HTTP_204_NO_CONTENT)
def delete_cv(user: User = Depends(current_user), session: Session = Depends(get_db)) -> None:
    """Delete every stored CV file and its extracted text.

    Separate from account deletion on purpose: a user may be happy to keep
    their profile and want the underlying document gone. Both the file and the
    extracted text go - keeping the text would make the deletion cosmetic.
    """
    now = datetime.now(UTC)
    for document in session.execute(
        select(CvDocument).where(CvDocument.user_id == user.id, CvDocument.deleted_at.is_(None))
    ).scalars():
        if document.stored_path:
            delete_stored(Path(document.stored_path))
        document.stored_path = None
        document.extracted_text = None
        document.deleted_at = now
    log_event(logger, Event.CV_DELETED, "cv deleted", user=hash_user_id(user.id))


@router.get("/cv")
def list_cv(
    user: User = Depends(current_user), session: Session = Depends(get_db)
) -> list[dict[str, object]]:
    """What we hold, so the delete button is not a leap of faith."""
    return [
        {
            "id": document.id,
            "filename": document.filename,
            "size_bytes": document.size_bytes,
            "uploaded_at": document.uploaded_at,
            "deleted_at": document.deleted_at,
            "file_present": bool(document.stored_path),
            "extracted_text_present": bool(document.extracted_text),
        }
        for document in session.execute(
            select(CvDocument).where(CvDocument.user_id == user.id)
        ).scalars()
    ]


@router.get("/consents")
def list_consents(
    user: User = Depends(current_user), session: Session = Depends(get_db)
) -> list[dict[str, object]]:
    return [
        {
            "purpose": record.purpose,
            "statement": record.statement,
            "granted_at": record.granted_at,
            "withdrawn_at": record.withdrawn_at,
        }
        for record in session.execute(
            select(ConsentRecord).where(ConsentRecord.user_id == user.id)
        ).scalars()
    ]
