"""Health, capabilities, provenance, feedback, metrics and the demo account.

The capability endpoint is the honesty contract between backend and frontend:
the UI renders what this deployment can actually do, rather than offering a
button that fails. It is also how a reviewer sees, in one request, exactly which
parts of the system are live and which are degraded.
"""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api import dto
from app.api.deps import (
    current_user,
    get_db,
    get_knowledge_store,
    get_legal_facts,
    get_registry,
    rate_limit,
    settings_dep,
)
from app.config import Settings
from app.db.base import get_engine, pgvector_available
from app.db.models import FeedbackEvent, Profile, User
from app.domain.enums import LegalVerificationStatus
from app.logging_config import Event, log_event
from app.rag.store import KnowledgeStore
from app.security.auth import Principal, issue_access_token, new_refresh_token
from app.services import analytics, learning
from app.services.legal_facts import LegalFactRepository
from app.sources.registry import SourceRegistry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health", response_model=dto.HealthResponse)
def health() -> dto.HealthResponse:
    """Liveness for the container platform. Cheap and dependency-light."""
    database_ok = True
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        database_ok = False
    return dto.HealthResponse(status="ok" if database_ok else "degraded", database=database_ok)


@router.get("/capabilities", response_model=dto.CapabilityReport)
def capabilities(
    session: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    store: KnowledgeStore = Depends(get_knowledge_store),
    facts: LegalFactRepository = Depends(get_legal_facts),
) -> dto.CapabilityReport:
    """What works right now, and what is degraded. Named plainly, not hidden."""
    corpus = store.stats(session)
    all_facts = facts.all(session)
    verified = sum(
        1
        for fact in all_facts
        if fact.effective_status(max_age=facts.max_age) is LegalVerificationStatus.VERIFIED
    )
    report = facts.status_report(session)

    degradations: list[str] = []
    if not settings.llm_available:
        degradations.append(
            "No language model is configured. CV extraction, AI-assisted search planning "
            "and written explanations are unavailable; deterministic matching, scoring, "
            "the Money Map, the Germany Check and the calculators all work."
        )
    if not settings.live_search_available:
        degradations.append(
            "No web search provider is configured. Discovery uses the curated and demo "
            "datasets only."
        )
    if corpus["chunks"] == 0:
        degradations.append(
            "The knowledge corpus is empty, so tax questions will be declined rather than "
            "answered. Run `make seed`."
        )
    if not settings.database_url:
        degradations.append(
            "Running on the local SQLite fallback. Suitable for development and the demo; "
            "container filesystems are ephemeral."
        )

    return dto.CapabilityReport(
        llm_available=settings.llm_available,
        llm_provider=settings.llm_provider.value,
        live_search_available=settings.live_search_available,
        search_provider=settings.search_provider.value,
        retrieval_mode=corpus["retrieval_mode"],
        knowledge_documents=corpus["documents"],
        knowledge_chunks=corpus["chunks"],
        legal_facts_verified=verified,
        legal_facts_total=len(all_facts),
        stale_fact_rate=report["stale_fact_rate"],
        demo_mode_enabled=settings.demo_mode_enabled,
        payments_enabled=settings.payments_enabled,
        database="postgres" if settings.uses_postgres else "sqlite",
        pgvector=pgvector_available(),
        degradations=degradations,
    )


@router.get("/provenance", response_model=list[dto.SourceProvenanceDto])
def provenance(registry: SourceRegistry = Depends(get_registry)) -> list[dto.SourceProvenanceDto]:
    """Where opportunities come from, and on what basis we access each source."""
    return [dto.SourceProvenanceDto(**row) for row in registry.describe()]


@router.post("/feedback", status_code=status.HTTP_201_CREATED, dependencies=[Depends(rate_limit)])
def submit_feedback(
    payload: dto.FeedbackRequest,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    """The validation instrument. These rows are the startup's actual evidence."""
    row = FeedbackEvent(
        user_id=user.id,
        opportunity_id=payload.opportunity_id,
        question=payload.question[:64],
        answer=payload.answer[:32],
        reason=payload.reason.value if payload.reason else None,
        note=payload.note,
    )
    session.add(row)
    session.flush()
    analytics.record(
        session,
        "feedback_submitted",
        user_id=user.id,
        question=payload.question[:64],
        answer=payload.answer[:32],
        reason=payload.reason.value if payload.reason else "",
    )
    return {"id": row.id}


@router.get("/feedback/summary")
def feedback_summary(session: Session = Depends(get_db)) -> dict[str, object]:
    """Aggregated responses. Deliberately a readable endpoint, not a dashboard.

    At this stage the useful artefact is honest counts a founder reads daily,
    not a visualisation that makes twelve data points look like a trend.
    """
    return {
        "responses": learning.feedback_summary(session),
        "events": analytics.funnel(session),
    }


@router.get("/metrics")
def metrics(
    session: Session = Depends(get_db), facts: LegalFactRepository = Depends(get_legal_facts)
) -> dict[str, object]:
    """The metric definitions in docs/METRICS.md, computed from real rows.

    Rates are ``null`` rather than zero when the denominator is empty: no data
    is not the same as a zero rate, and a metrics table showing 0% for an
    unmeasured step invites exactly the wrong conclusion.
    """
    counts = analytics.funnel(session)
    return {
        "counts": counts,
        "rates": {
            "profile_completion": analytics.rate(
                counts, "profile_completed", "signup_completed"
            ),
            "money_map_activation": analytics.rate(
                counts, "money_map_created", "profile_completed"
            ),
            "save_rate": analytics.rate(counts, "opportunity_saved", "opportunity_opened"),
            "action_rate": analytics.rate(
                counts, "application_prepared", "opportunity_saved"
            ),
            "application_rate": analytics.rate(
                counts, "application_marked_applied", "opportunity_saved"
            ),
            "win_rate": analytics.rate(
                counts, "opportunity_won", "application_marked_applied"
            ),
        },
        "legal_facts": facts.status_report(session),
        "note": (
            "A null rate means the denominator is zero - no data, not a zero result. "
            "Definitions are in docs/METRICS.md."
        ),
    }


@router.get("/preferences")
def preferences(
    user: User = Depends(current_user), session: Session = Depends(get_db)
) -> dict[str, object]:
    """What the ranking has learned from your dismissals, in plain language."""
    return learning.explain_preferences(session, user.id)


@router.delete("/preferences", status_code=status.HTTP_204_NO_CONTENT)
def reset_preferences(
    user: User = Depends(current_user), session: Session = Depends(get_db)
) -> None:
    learning.reset_preferences(session, user.id)


@router.get("/outcomes")
def outcomes(
    user: User = Depends(current_user), session: Session = Depends(get_db)
) -> dict[str, object]:
    return learning.outcome_summary(session, user.id)


# ------------------------------------------------------------------ demo


DEMO_EMAIL_PREFIX = "demo-"


@router.post("/demo/session", response_model=dto.TokenResponse)
def start_demo(
    session: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
) -> dto.TokenResponse:
    """Create a throwaway demo account with a pre-filled fictional profile.

    Exists so an accelerator jury can see the whole product in ninety seconds
    without creating an account. The profile is a generic invented professional -
    never a founder's real details - and every opportunity the demo surfaces is
    badged DEMO.
    """
    if not settings.demo_mode_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Demo mode is disabled."
        )

    token = secrets.token_hex(8)
    user = User(
        email=f"{DEMO_EMAIL_PREFIX}{token}@demo.invalid",
        password_hash=None,
        is_demo=True,
    )
    session.add(user)
    session.flush()
    session.add(_demo_profile(user.id))
    session.flush()

    from app.api.routes.profile import _profile_row
    from app.db.models import ProfileSkill

    profile = _profile_row(session, user)
    for name, level, years in (
        ("Data Engineering", "EXPERT", 7.0),
        ("Python", "ADVANCED", 8.0),
        ("SQL", "ADVANCED", 8.0),
        ("Machine Learning", "INTERMEDIATE", 3.0),
        ("Cloud Architecture", "ADVANCED", 5.0),
        ("Teaching", "INTERMEDIATE", 2.0),
    ):
        session.add(
            ProfileSkill(
                profile_id=profile.id,
                name=name,
                key=name.lower(),
                level=level,
                years=years,
                evidence="USER_STATED",
                confirmed=True,
            )
        )

    analytics.record(session, "signup_completed", user_id=user.id, is_demo=True)
    log_event(logger, Event.SIGNUP_COMPLETED, "demo session started")

    access, expires_in = issue_access_token(
        Principal(user_id=user.id, email=user.email, is_demo=True), settings
    )
    plaintext, token_hash = new_refresh_token()
    from datetime import timedelta

    from app.db.models import RefreshToken

    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
    )
    return dto.TokenResponse(
        access_token=access,
        refresh_token=plaintext,
        expires_in=expires_in,
        user_id=user.id,
        email=user.email,
        is_demo=True,
    )


def _demo_profile(user_id: str) -> Profile:
    """A generic fictional professional. Never anyone's real details."""
    return Profile(
        user_id=user_id,
        display_name="Sam",
        city="Berlin",
        federal_state="Berlin",
        country="DE",
        current_role="Senior Data Engineer",
        years_experience=7.0,
        industries=["Software", "Energy"],
        education={
            "items": [
                {
                    "qualification": "M.Sc. Computer Science",
                    "institution": "A German university",
                    "field_of_study": "Computer Science",
                    "completed_year": 2016,
                }
            ]
        },
        certifications={"items": []},
        languages={
            "items": [{"code": "en", "level": "C1"}, {"code": "de", "level": "B2"}]
        },
        desired_additional_monthly_minor=150_000,
        minimum_worthwhile_minor=15_000,
        current_primary_income_type="Full-time employment",
        income_preference="NO_PREFERENCE",
        hours_per_week=6.0,
        schedule_preference="EVENINGS",
        remote_preference="REMOTE",
        willing_to_travel="UNKNOWN",
        work_status="EMPLOYEE",
        has_gewerbe="NO",
        has_freelance_tax_registration="NO",
        knows_employer_rules="UNKNOWN",
        receives_employment_benefits="NO",
        confirmed=True,
        confirmed_at=datetime.now(UTC),
    )


@router.delete("/demo/session", status_code=status.HTTP_204_NO_CONTENT)
def end_demo(user: User = Depends(current_user), session: Session = Depends(get_db)) -> None:
    """Delete the demo account and everything attached to it."""
    if not user.is_demo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="This is not a demo account."
        )
    session.delete(user)
