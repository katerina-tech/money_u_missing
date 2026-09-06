"""Shared fixtures.

Every test runs against a temporary SQLite database and the deterministic
providers in :mod:`app.llm.testing`. No test in this suite makes a paid model
call or a network request, which is what makes it reasonable to run the whole
thing on every commit.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.domain.enums import (
    CompensationBasis,
    CompensationPeriod,
    Confidence,
    IncomePreference,
    IncomeStreamCategory,
    LanguageLevel,
    RemoteType,
    RequirementStrength,
    SkillLevel,
    SourceType,
    WorkStatus,
)
from app.domain.evidence import SourceRef
from app.domain.money import MoneyRange
from app.domain.opportunity import LanguageRequirement, Opportunity, Requirement
from app.domain.profile import (
    GeneralInfo,
    IncomeInfo,
    Language,
    ProfessionalInfo,
    Skill,
    TimeInfo,
    UserProfile,
)


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Point every test at its own database and data directory."""
    monkeypatch.setenv("MYM_ENVIRONMENT", "test")
    monkeypatch.setenv("MYM_JWT_SECRET", "test-secret-not-used-anywhere-real")
    monkeypatch.setenv("MYM_LLM_PROVIDER", "none")
    monkeypatch.setenv("MYM_SEARCH_PROVIDER", "none")
    monkeypatch.setenv("MYM_LOG_FORMAT", "console")
    monkeypatch.setenv("MYM_SQLITE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("MYM_UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.delenv("MYM_DATABASE_URL", raising=False)

    from app.api import deps
    from app.config import get_settings
    from app.db import base as db_base

    get_settings.cache_clear()
    db_base.reset_engine()
    deps.reset_singletons()
    yield
    db_base.reset_engine()
    get_settings.cache_clear()
    deps.reset_singletons()


@pytest.fixture
def session() -> Iterator[Session]:
    from app.db.base import Base, create_app_engine, get_session_factory

    Base.metadata.create_all(create_app_engine())
    factory = get_session_factory()
    db = factory()
    try:
        yield db
        db.commit()
    finally:
        db.close()


@pytest.fixture
def client() -> Iterator[object]:
    from fastapi.testclient import TestClient

    from app.db.base import Base, create_app_engine
    from app.main import create_app

    Base.metadata.create_all(create_app_engine())
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def seeded_client(client: object) -> object:
    """A client whose database has the knowledge corpus and legal facts loaded."""
    from app.config import get_settings
    from app.db.base import session_scope
    from app.rag.store import KnowledgeStore
    from app.services.legal_facts import LegalFactRepository

    settings = get_settings()
    with session_scope() as db:
        LegalFactRepository(settings).load_from_file(db, settings.data_dir / "legal_facts.json")
        KnowledgeStore(settings).ingest_directory(db, settings.knowledge_dir)
    return client


# ------------------------------------------------------------------ builders


def make_profile(**overrides: object) -> UserProfile:
    """A confirmed profile with everything matching needs. Override per test."""
    base = UserProfile(
        user_id="test-user",
        confirmed=True,
        confirmed_at=datetime.now(UTC),
        general=GeneralInfo(
            display_name="Test", city="Berlin", federal_state="Berlin", country="DE"
        ),
        professional=ProfessionalInfo(
            current_role="Senior Data Engineer",
            years_experience=7.0,
            skills=[
                Skill(name="Python", level=SkillLevel.ADVANCED, years=8),
                Skill(name="Data Engineering", level=SkillLevel.EXPERT, years=7),
                Skill(name="SQL", level=SkillLevel.ADVANCED, years=8),
            ],
            languages=[
                Language(code="en", level=LanguageLevel.C1),
                Language(code="de", level=LanguageLevel.B2),
            ],
        ),
        income=IncomeInfo(
            desired_additional_monthly_minor=150_000,
            minimum_worthwhile_minor=10_000,
            preference=IncomePreference.NO_PREFERENCE,
        ),
        time=TimeInfo(hours_per_week=6.0, remote_preference=RemoteType.REMOTE),
        work_status=WorkStatus.EMPLOYEE,
    )
    return base.model_copy(update=overrides)


def make_opportunity(**overrides: object) -> Opportunity:
    """A well-specified opportunity. Override to create the interesting cases."""
    base = Opportunity(
        id="opp-1",
        title="Freelance data engineering project",
        organization="Example Org",
        category=IncomeStreamCategory.FREELANCE_PROJECT,
        country="DE",
        city="Berlin",
        remote_type=RemoteType.REMOTE,
        required_skills=["Python", "SQL"],
        preferred_skills=["Data Engineering"],
        required_languages=[
            LanguageRequirement(
                code="en", minimum=LanguageLevel.B2, strength=RequirementStrength.HARD
            )
        ],
        experience_min_years=3,
        eligibility_structured=[
            Requirement(label="Based in Germany", strength=RequirementStrength.HARD)
        ],
        compensation=MoneyRange(
            minor_min=80_000,
            minor_max=120_000,
            basis=CompensationBasis.PER_MONTH,
            period=CompensationPeriod.RECURRING,
        ),
        compensation_verified=True,
        estimated_hours_min=5,
        estimated_hours_max=6,
        deadline=date.today() + timedelta(days=30),
        source=SourceRef(
            name="Example source",
            url="https://example.org/jobs/1",
            source_type=SourceType.CURATED,
            retrieved_at=datetime.now(UTC),
        ),
        evidence_confidence=Confidence.SOURCE_BACKED,
    )
    return base.model_copy(update=overrides)


def bare_opportunity(**overrides: object) -> Opportunity:
    """An opportunity that publishes almost nothing. The important edge case.

    Most real listings look more like this than like ``make_opportunity``, which
    is precisely why the "unknown is not false" rules matter.
    """
    base = Opportunity(
        id="opp-bare",
        title="Expert network - practitioners wanted",
        organization=None,
        category=IncomeStreamCategory.EXPERT_CALL,
        source=SourceRef(
            name="Example source",
            source_type=SourceType.SEARCH_API,
            retrieved_at=datetime.now(UTC),
        ),
        evidence_confidence=Confidence.EXTRACTED,
    )
    return base.model_copy(update=overrides)


__all__ = ["bare_opportunity", "make_opportunity", "make_profile"]
