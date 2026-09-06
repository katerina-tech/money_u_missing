"""Authentication, account deletion and data export."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import dto
from app.api.deps import current_user, get_db, rate_limit, settings_dep
from app.config import Settings
from app.db.models import (
    AuditEvent,
    ConsentRecord,
    CvDocument,
    Profile,
    RefreshToken,
    User,
)
from app.logging_config import Event, hash_user_id, log_event
from app.security import auth
from app.security.uploads import delete_stored
from app.services import analytics

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"], dependencies=[Depends(rate_limit)])

#: Columns that are credentials or server internals, not information about the
#: user. Excluded from the export because handing someone their own password
#: hash or an on-disk path serves nobody.
_NEVER_EXPORTED = frozenset({"password_hash", "stored_path", "token_hash"})

PRIVACY_CONSENT = (
    "I have read the privacy notice and agree to Money You're Missing processing the "
    "profile information I provide in order to find and rank income opportunities for "
    "me. I understand I can delete my data at any time."
)
CV_CONSENT = (
    "I agree to Money You're Missing processing the CV or profile text I provide, in "
    "order to extract my skills and experience for opportunity matching. I understand "
    "the extracted result is shown to me for review before it is used, that my CV is "
    "not used to train any model, and that I can delete it at any time."
)


def _audit(session: Session, action: str, user_id: str | None, request: Request) -> None:
    session.add(
        AuditEvent(
            subject_hash=hash_user_id(user_id),
            action=action,
            detail={},
            ip_hash=hash_user_id(request.client.host if request.client else None),
        )
    )


def _issue(session: Session, user: User, settings: Settings) -> dto.TokenResponse:
    principal = auth.Principal(user_id=user.id, email=user.email, is_demo=user.is_demo)
    access, expires_in = auth.issue_access_token(principal, settings)
    plaintext, token_hash = auth.new_refresh_token()
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_ttl_days),
        )
    )
    user.last_login_at = datetime.now(UTC)
    return dto.TokenResponse(
        access_token=access,
        refresh_token=plaintext,
        expires_in=expires_in,
        user_id=user.id,
        email=user.email,
        is_demo=user.is_demo,
    )


@router.post("/signup", response_model=dto.TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(
    payload: dto.SignupRequest,
    request: Request,
    session: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
) -> dto.TokenResponse:
    if not payload.accept_privacy:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="We need your agreement to the privacy notice before creating an account.",
        )
    email = payload.email.lower().strip()
    existing = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing is not None:
        # Deliberately the same shape of response as a weak password, and no
        # confirmation that the address exists: signup must not be an oracle for
        # which email addresses have accounts here.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="We could not create an account with those details.",
        )
    try:
        password_hash = auth.hash_password(
            payload.password, min_length=settings.password_min_length
        )
    except auth.AuthError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

    user = User(email=email, password_hash=password_hash)
    session.add(user)
    session.flush()
    session.add(Profile(user_id=user.id))
    session.add(
        ConsentRecord(user_id=user.id, purpose="privacy_notice", statement=PRIVACY_CONSENT)
    )
    _audit(session, "signup", user.id, request)
    analytics.record(session, "signup_completed", user_id=user.id, is_demo=False)
    log_event(logger, Event.SIGNUP_COMPLETED, "account created", user=hash_user_id(user.id))
    return _issue(session, user, settings)


@router.post("/login", response_model=dto.TokenResponse)
def login(
    payload: dto.LoginRequest,
    request: Request,
    session: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
) -> dto.TokenResponse:
    email = payload.email.lower().strip()
    user = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
    # verify_password performs a full hash comparison even when the user does
    # not exist, so response timing does not reveal which addresses are
    # registered.
    if not auth.verify_password(user.password_hash if user else None, payload.password):
        _audit(session, "login_failed", user.id if user else None, request)
        log_event(logger, Event.LOGIN_FAILED, "login failed", level=logging.INFO)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password."
        )
    assert user is not None
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="This account is no longer active."
        )
    if user.password_hash and auth.needs_rehash(user.password_hash):
        # Transparent upgrade to current hashing parameters.
        user.password_hash = auth.hash_password(
            payload.password, min_length=settings.password_min_length
        )
    _audit(session, "login", user.id, request)
    log_event(logger, Event.LOGIN_SUCCEEDED, "login", user=hash_user_id(user.id))
    return _issue(session, user, settings)


@router.post("/refresh", response_model=dto.TokenResponse)
def refresh(
    payload: dto.RefreshRequest,
    session: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
) -> dto.TokenResponse:
    token_hash = auth.hash_refresh_token(payload.refresh_token)
    row = session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    ).scalar_one_or_none()
    now = datetime.now(UTC)
    if row is None or row.revoked_at is not None or row.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Please sign in again."
        )
    user = session.get(User, row.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Please sign in again."
        )
    # Rotate: the presented token is revoked and a new one issued, so a stolen
    # refresh token is usable at most once and its reuse is detectable.
    row.revoked_at = now
    log_event(logger, Event.TOKEN_REFRESHED, "token refreshed", user=hash_user_id(user.id))
    return _issue(session, user, settings)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(user: User = Depends(current_user), session: Session = Depends(get_db)) -> None:
    """Revoke every refresh token for this account.

    Server-side revocation is why refresh tokens are stored at all. A purely
    stateless scheme cannot log anyone out.
    """
    now = datetime.now(UTC)
    rows = session.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)
        )
    ).scalars()
    for row in rows:
        row.revoked_at = now


@router.get("/me")
def me(user: User = Depends(current_user)) -> dict[str, object]:
    return {
        "user_id": user.id,
        "email": user.email,
        "is_demo": user.is_demo,
        "created_at": user.created_at,
    }


@router.get("/export")
def export_data(
    user: User = Depends(current_user), session: Session = Depends(get_db)
) -> dict[str, object]:
    """Everything held about this account, as JSON.

    A real export rather than a placeholder, because the right of access is
    only meaningful if exercising it produces the data. Deliberately excludes
    the password hash and the stored CV file path - neither is information
    *about* the user that they do not already have, and both are credentials or
    server internals.
    """
    from app.db.models import (
        AnalyticsEvent,
        Application,
        ChildGoalRow,
        FeedbackEvent,
        FinancialGoalRow,
        IncomeEvent,
        IncomeGoal,
        IncomeStream,
        Notification,
        ProfileSkill,
        SavedOpportunity,
    )

    def rows(model: Any, **filters: object) -> list[dict[str, Any]]:
        query = select(model).filter_by(user_id=user.id, **filters)
        return [
            {
                column.name: getattr(row, column.name)
                for column in model.__table__.columns
                if column.name not in _NEVER_EXPORTED
            }
            for row in session.execute(query).scalars()
        ]

    profile = session.execute(
        select(Profile).where(Profile.user_id == user.id)
    ).scalar_one_or_none()
    skills = (
        [
            {c.name: getattr(s, c.name) for c in ProfileSkill.__table__.columns}
            for s in session.execute(
                select(ProfileSkill).where(ProfileSkill.profile_id == profile.id)
            ).scalars()
        ]
        if profile
        else []
    )

    return {
        "exported_at": datetime.now(UTC),
        "account": {"id": user.id, "email": user.email, "created_at": user.created_at},
        "profile": (
            {c.name: getattr(profile, c.name) for c in Profile.__table__.columns}
            if profile
            else None
        ),
        "skills": skills,
        "cv_documents": rows(CvDocument),
        "consents": rows(ConsentRecord),
        "income_goals": rows(IncomeGoal),
        "income_streams": rows(IncomeStream),
        "saved_opportunities": rows(SavedOpportunity),
        "applications": rows(Application),
        "income_events": rows(IncomeEvent),
        "financial_goals": rows(FinancialGoalRow),
        "child_goals": rows(ChildGoalRow),
        "feedback": rows(FeedbackEvent),
        "analytics_events": rows(AnalyticsEvent),
        "notifications": rows(Notification),
    }


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    request: Request,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> None:
    """Delete the account and everything attached to it.

    One DELETE. Every personal table has ``ondelete="CASCADE"`` on
    ``users.id``, which is why this cannot silently miss a table someone added
    last month. Stored CV files are removed from disk first, because a
    filesystem is not covered by a foreign key.

    The audit row deliberately survives: it records that a deletion happened,
    against a hash rather than an id, and is not personal data on its own.
    """
    for document in session.execute(
        select(CvDocument).where(CvDocument.user_id == user.id)
    ).scalars():
        if document.stored_path:
            from pathlib import Path

            delete_stored(Path(document.stored_path))

    _audit(session, "account_deleted", user.id, request)
    log_event(logger, Event.ACCOUNT_DELETED, "deleted", user=hash_user_id(user.id))
    session.delete(user)
