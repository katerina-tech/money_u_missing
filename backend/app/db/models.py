"""The relational schema.

Three properties are designed in rather than added later:

**Deletion is real.** Every table that holds personal data hangs off
``users.id`` with ``ondelete="CASCADE"``. Deleting an account is one DELETE, not
a checklist someone has to remember to update when a table is added - which is
how "we deleted your data" quietly becomes false. ``opportunities`` deliberately
does *not* cascade: an opportunity is public information about the world, not
about the user, and the join tables that connect it to a person do cascade.

**Unknown survives storage.** Nullable columns mean unknown throughout. There
are no sentinel zeroes and no ``NOT NULL DEFAULT 0`` on a money column, because
a zero that means "not published" would be indistinguishable from a zero that
means "unpaid" the moment it left this file.

**Money is integer cents.** No FLOAT columns anywhere near an amount.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JsonDict, StringList, UtcDateTime, Vector
from app.domain.evidence import utcnow


def new_id() -> str:
    return uuid.uuid4().hex


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=utcnow, onupdate=utcnow
    )


# ============================================================ identity


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    #: Argon2id hash. The plaintext never exists outside the request that set it.
    password_hash: Mapped[str | None] = mapped_column(String(255), default=None)
    #: Set when identity is delegated (Supabase Auth); then password_hash is NULL.
    external_auth_id: Mapped[str | None] = mapped_column(String(128), index=True, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    last_login_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)

    profile: Mapped[Profile | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class RefreshToken(Base):
    """Server-side refresh tokens, so logout genuinely revokes.

    Only a hash is stored: a database read must not yield a usable credential.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)


class ConsentRecord(Base):
    """An auditable record of what the user agreed to, and when.

    Required by the CV flow: processing a CV needs a specific, informed consent
    that can be shown back to the user and withdrawn. ``withdrawn_at`` rather
    than a delete, so the audit trail survives the withdrawal.
    """

    __tablename__ = "consent_records"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    purpose: Mapped[str] = mapped_column(String(64), index=True)
    #: The exact wording shown, so consent can be evidenced rather than asserted.
    statement: Mapped[str] = mapped_column(Text)
    version: Mapped[str] = mapped_column(String(16), default="1")
    granted_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    withdrawn_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)

    __table_args__ = (Index("ix_consent_user_purpose", "user_id", "purpose"),)


# ============================================================= profile


class Profile(Base, TimestampMixin):
    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )

    display_name: Mapped[str | None] = mapped_column(String(120), default=None)
    city: Mapped[str | None] = mapped_column(String(120), default=None)
    federal_state: Mapped[str | None] = mapped_column(String(120), default=None)
    country: Mapped[str] = mapped_column(String(2), default="DE")

    current_role: Mapped[str | None] = mapped_column(String(200), default=None)
    years_experience: Mapped[float | None] = mapped_column(Float, default=None)
    industries: Mapped[list[str]] = mapped_column(StringList, default=list)
    portfolio_url: Mapped[str | None] = mapped_column(String(500), default=None)
    #: Education, certifications and languages: small, always read together with
    #: the profile, never queried across users. A JSON document is the right
    #: shape; three more tables would be schema for its own sake.
    education: Mapped[dict[str, Any]] = mapped_column(JsonDict, default=dict)
    certifications: Mapped[dict[str, Any]] = mapped_column(JsonDict, default=dict)
    languages: Mapped[dict[str, Any]] = mapped_column(JsonDict, default=dict)

    desired_additional_monthly_minor: Mapped[int | None] = mapped_column(Integer, default=None)
    #: The total monthly income the user says they want - point B on the
    #: dashboard band. Stored rather than derived from the field above,
    #: because a target at or below the current income cannot be expressed
    #: as a non-negative "additional", and rewriting the user's own figure to
    #: make the arithmetic work is precisely what this product must not do.
    #: NULL for anyone who has not set one; the band then falls back to
    #: current + additional, which is what it always showed.
    target_monthly_minor: Mapped[int | None] = mapped_column(Integer, default=None)
    minimum_worthwhile_minor: Mapped[int | None] = mapped_column(Integer, default=None)
    current_primary_income_type: Mapped[str | None] = mapped_column(String(80), default=None)
    income_preference: Mapped[str] = mapped_column(String(32), default="NO_PREFERENCE")

    hours_per_week: Mapped[float | None] = mapped_column(Float, default=None)
    schedule_preference: Mapped[str] = mapped_column(String(32), default="UNKNOWN")
    remote_preference: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    willing_to_travel: Mapped[str] = mapped_column(String(16), default="UNKNOWN")

    work_status: Mapped[str] = mapped_column(String(40), default="UNKNOWN")

    # Administrative context. All tri-state, all user-set only.
    has_gewerbe: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    has_freelance_tax_registration: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    knows_employer_rules: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    receives_employment_benefits: Mapped[str] = mapped_column(String(24), default="UNKNOWN")

    # Household context. Explicit disclosure only, never inferred from a CV, a
    # career gap, an age or anything else. It exists to decide which questions
    # are worth raising, never to compute anyone's position.
    has_children: Mapped[str] = mapped_column(String(24), default="UNKNOWN")
    jointly_assessed: Mapped[str] = mapped_column(String(24), default="UNKNOWN")
    #: Ages and parent-chosen labels only. Deliberately no names and no dates of
    #: birth: the questions this product raises do not need them, and a child's
    #: personal data is not collected speculatively.
    children: Mapped[dict[str, Any]] = mapped_column(JsonDict, default=dict)

    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)

    user: Mapped[User] = relationship(back_populates="profile")
    skills: Mapped[list[ProfileSkill]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )


class ProfileSkill(Base):
    """One skills-graph node. Separate table because matching queries it directly."""

    __tablename__ = "profile_skills"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    profile_id: Mapped[str] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    #: Case-folded key. Unique per profile so a skill cannot be listed twice
    #: with different capitalisation and counted twice in a score.
    key: Mapped[str] = mapped_column(String(120), index=True)
    level: Mapped[str] = mapped_column(String(20), default="UNKNOWN")
    years: Mapped[float | None] = mapped_column(Float, default=None)
    evidence: Mapped[str] = mapped_column(String(20), default="USER_STATED")
    related: Mapped[list[str]] = mapped_column(StringList, default=list)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)

    profile: Mapped[Profile] = relationship(back_populates="skills")

    __table_args__ = (UniqueConstraint("profile_id", "key", name="uq_profile_skill"),)


class CvDocument(Base):
    """An uploaded CV. Retention is short and deletion is a first-class action.

    ``extracted_text`` exists so re-extraction does not require the file, and is
    cleared by the same delete that removes the file. See docs/GDPR_DATA_MAP.md.
    """

    __tablename__ = "cv_documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    #: Path on disk, or NULL once the file has been deleted but the extraction
    #: is still in use for the current onboarding session.
    stored_path: Mapped[str | None] = mapped_column(String(500), default=None)
    extracted_text: Mapped[str | None] = mapped_column(Text, default=None)
    uploaded_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)


# ================================================== goals and income


class IncomeGoal(Base, TimestampMixin):
    __tablename__ = "income_goals"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    target_monthly_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class IncomeStream(Base, TimestampMixin):
    """A named source of income in the user's portfolio.

    ``status`` is ACTIVE only when money has actually been secured or earned.
    The portfolio view depends on that distinction and the check constraint
    keeps it true at the storage layer, not just in the service that writes it.
    """

    __tablename__ = "income_streams"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(16), default="POTENTIAL", index=True)
    money_state: Mapped[str] = mapped_column(String(16), default="POTENTIAL", index=True)
    amount_minor: Mapped[int | None] = mapped_column(Integer, default=None)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    period: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    basis: Mapped[str] = mapped_column(String(20), default="UNKNOWN")
    tax_treatment: Mapped[str] = mapped_column(String(10), default="UNKNOWN")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        CheckConstraint(
            "status <> 'ACTIVE' OR money_state IN ('SECURED', 'EARNED')",
            name="ck_active_stream_is_committed",
        ),
    )


# ========================================================= opportunities


class OpportunitySource(Base, TimestampMixin):
    """A registered source and its operational state.

    ``last_health_check_ok`` is what lets the UI say "live search is
    unavailable, these are cached results" instead of showing a short list and
    letting the user assume that is all there is.
    """

    __tablename__ = "opportunity_sources"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    source_type: Mapped[str] = mapped_column(String(32), index=True)
    base_url: Mapped[str | None] = mapped_column(String(500), default=None)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    #: Terms/robots position recorded at the time the source was added.
    access_basis: Mapped[str | None] = mapped_column(Text, default=None)
    last_health_check_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, default=None
    )
    last_health_check_ok: Mapped[bool | None] = mapped_column(Boolean, default=None)
    last_error: Mapped[str | None] = mapped_column(Text, default=None)


class Opportunity(Base, TimestampMixin):
    __tablename__ = "opportunities"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    #: Deterministic identity from canonical URL, or org+title+deadline. Unique,
    #: so de-duplication is enforced by the database and not only by the service
    #: that happens to run before the insert.
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    title: Mapped[str] = mapped_column(String(400))
    organization: Mapped[str | None] = mapped_column(String(300), default=None, index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    subcategory: Mapped[str | None] = mapped_column(String(120), default=None)

    description: Mapped[str | None] = mapped_column(Text, default=None)
    summary: Mapped[str | None] = mapped_column(Text, default=None)

    country: Mapped[str | None] = mapped_column(String(2), default=None, index=True)
    region: Mapped[str | None] = mapped_column(String(120), default=None)
    city: Mapped[str | None] = mapped_column(String(120), default=None)
    remote_type: Mapped[str] = mapped_column(String(16), default="UNKNOWN", index=True)

    required_skills: Mapped[list[str]] = mapped_column(StringList, default=list)
    preferred_skills: Mapped[list[str]] = mapped_column(StringList, default=list)
    required_languages: Mapped[dict[str, Any]] = mapped_column(JsonDict, default=dict)
    experience_min_years: Mapped[float | None] = mapped_column(Float, default=None)
    experience_max_years: Mapped[float | None] = mapped_column(Float, default=None)

    eligibility_text: Mapped[str | None] = mapped_column(Text, default=None)
    eligibility_structured: Mapped[dict[str, Any]] = mapped_column(JsonDict, default=dict)

    employment_type: Mapped[str] = mapped_column(String(24), default="UNKNOWN")

    # Money: nullable integers. NULL is "not published", and there is no
    # default that could be mistaken for a published zero.
    compensation_min_minor: Mapped[int | None] = mapped_column(Integer, default=None)
    compensation_max_minor: Mapped[int | None] = mapped_column(Integer, default=None)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    compensation_basis: Mapped[str] = mapped_column(String(20), default="UNKNOWN")
    compensation_period: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    tax_treatment: Mapped[str] = mapped_column(String(10), default="UNKNOWN")
    compensation_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    estimated_hours_min: Mapped[float | None] = mapped_column(Float, default=None)
    estimated_hours_max: Mapped[float | None] = mapped_column(Float, default=None)

    deadline: Mapped[date | None] = mapped_column(Date, default=None, index=True)
    start_date: Mapped[date | None] = mapped_column(Date, default=None)

    source_id: Mapped[str | None] = mapped_column(
        ForeignKey("opportunity_sources.id", ondelete="SET NULL"), default=None, index=True
    )
    source_name: Mapped[str] = mapped_column(String(160))
    source_url: Mapped[str | None] = mapped_column(String(1000), default=None)
    source_type: Mapped[str] = mapped_column(String(32), index=True)
    retrieved_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    last_verified_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, default=None
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_sponsored: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence_confidence: Mapped[str] = mapped_column(String(20), default="UNKNOWN")
    safety_verdict: Mapped[str] = mapped_column(String(16), default="ALLOWED", index=True)
    safety_reasons: Mapped[list[str]] = mapped_column(StringList, default=list)

    evidence: Mapped[list[OpportunityEvidence]] = relationship(
        back_populates="opportunity", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # The ranking query filters on all three together.
        Index("ix_opportunity_live", "is_active", "is_demo", "category"),
        Index("ix_opportunity_deadline_active", "deadline", "is_active"),
        CheckConstraint(
            "compensation_min_minor IS NULL OR compensation_max_minor IS NULL "
            "OR compensation_min_minor <= compensation_max_minor",
            name="ck_compensation_range_ordered",
        ),
        CheckConstraint(
            "NOT (is_demo AND compensation_verified)",
            name="ck_demo_cannot_be_verified",
        ),
    )


class OpportunityEvidence(Base):
    """Per-field provenance. One row per claim we are prepared to stand behind."""

    __tablename__ = "opportunity_evidence"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    opportunity_id: Mapped[str] = mapped_column(
        ForeignKey("opportunities.id", ondelete="CASCADE"), index=True
    )
    field_name: Mapped[str] = mapped_column(String(60), index=True)
    value_text: Mapped[str | None] = mapped_column(Text, default=None)
    confidence: Mapped[str] = mapped_column(String(20), default="UNKNOWN")
    source_name: Mapped[str] = mapped_column(String(160))
    source_url: Mapped[str | None] = mapped_column(String(1000), default=None)
    retrieved_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    #: Verbatim supporting text from the source, so a claim can be checked.
    excerpt: Mapped[str | None] = mapped_column(Text, default=None)

    opportunity: Mapped[Opportunity] = relationship(back_populates="evidence")

    __table_args__ = (Index("ix_evidence_opp_field", "opportunity_id", "field_name"),)


class OpportunityMatch(Base, TimestampMixin):
    """A stored score. Persisted with its weights version so it stays readable.

    Storing the component breakdown rather than only the total is what allows
    "why did this drop from 91 to 74 last week?" to be answered at all.
    """

    __tablename__ = "opportunity_matches"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    opportunity_id: Mapped[str] = mapped_column(
        ForeignKey("opportunities.id", ondelete="CASCADE"), index=True
    )
    total_score: Mapped[int] = mapped_column(Integer, index=True)
    components: Mapped[dict[str, Any]] = mapped_column(JsonDict, default=dict)
    hard_failures: Mapped[dict[str, Any]] = mapped_column(JsonDict, default=dict)
    uncertainties: Mapped[dict[str, Any]] = mapped_column(JsonDict, default=dict)
    explanation_inputs: Mapped[list[str]] = mapped_column(StringList, default=list)
    actionability_score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    actionability_band: Mapped[str] = mapped_column(String(24), default="LOW_PRIORITY")
    actionability_factors: Mapped[dict[str, Any]] = mapped_column(JsonDict, default=dict)
    weights_version: Mapped[str] = mapped_column(String(16), default="v1")

    __table_args__ = (
        UniqueConstraint("user_id", "opportunity_id", name="uq_match_user_opportunity"),
        Index("ix_match_ranking", "user_id", "total_score", "actionability_score"),
    )


class SavedOpportunity(Base):
    __tablename__ = "saved_opportunities"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    opportunity_id: Mapped[str] = mapped_column(
        ForeignKey("opportunities.id", ondelete="CASCADE"), index=True
    )
    saved_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    dismissed_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)
    dismiss_reason: Mapped[str | None] = mapped_column(String(32), default=None, index=True)
    dismiss_note: Mapped[str | None] = mapped_column(Text, default=None)

    __table_args__ = (UniqueConstraint("user_id", "opportunity_id", name="uq_saved_user_opp"),)


class Application(Base, TimestampMixin):
    """The action workspace and tracking state for one pursued opportunity."""

    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    opportunity_id: Mapped[str] = mapped_column(
        ForeignKey("opportunities.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="SAVED", index=True)
    #: Append-only list of {from, to, at}. The history is the outcome dataset.
    status_history: Mapped[dict[str, Any]] = mapped_column(JsonDict, default=dict)

    checklist: Mapped[dict[str, Any]] = mapped_column(JsonDict, default=dict)
    documents_needed: Mapped[list[str]] = mapped_column(StringList, default=list)
    questions_to_verify: Mapped[list[str]] = mapped_column(StringList, default=list)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    #: Model-assisted drafts. Never sent anywhere by this system.
    drafts: Mapped[dict[str, Any]] = mapped_column(JsonDict, default=dict)
    reminder_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)

    applied_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)
    closed_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)

    __table_args__ = (
        UniqueConstraint("user_id", "opportunity_id", name="uq_application_user_opp"),
        Index("ix_application_user_status", "user_id", "status"),
    )


class IncomeEvent(Base):
    """Money the user says actually happened. The only source of EARNED figures.

    Never written by discovery, never inferred from an opportunity's published
    range - a user has to enter it.
    """

    __tablename__ = "income_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    application_id: Mapped[str | None] = mapped_column(
        ForeignKey("applications.id", ondelete="SET NULL"), default=None, index=True
    )
    income_stream_id: Mapped[str | None] = mapped_column(
        ForeignKey("income_streams.id", ondelete="SET NULL"), default=None
    )
    label: Mapped[str] = mapped_column(String(200))
    amount_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    tax_treatment: Mapped[str] = mapped_column(String(10), default="UNKNOWN")
    period: Mapped[str] = mapped_column(String(16), default="ONE_TIME")
    money_state: Mapped[str] = mapped_column(String(16), default="EARNED", index=True)
    hours_spent: Mapped[float | None] = mapped_column(Float, default=None)
    occurred_on: Mapped[date] = mapped_column(Date, index=True)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)

    __table_args__ = (
        CheckConstraint("money_state IN ('SECURED','EARNED')", name="ck_income_is_committed"),
        Index("ix_income_user_date", "user_id", "occurred_on"),
    )


class BaselineIncomeRow(Base, TimestampMixin):
    """Income the user already had before this product existed.

    Kept apart from ``income_events``, which is money this product helped find.
    Mixing them would let a salary inflate the "earned" figure on the Money Map
    and make the product look like it had produced income it had nothing to do
    with - the single most flattering lie available to it.

    ``basis`` records whether the amount is gross or net. There is no column for
    "the other one" because nothing in this system converts between them.
    """

    __tablename__ = "baseline_incomes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(160))
    amount_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    basis: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    period: Mapped[str] = mapped_column(String(16), default="RECURRING")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    started_on: Mapped[date | None] = mapped_column(Date, default=None)

    __table_args__ = (
        CheckConstraint("basis IN ('GROSS','NET','UNKNOWN')", name="ck_baseline_basis"),
        CheckConstraint("amount_minor >= 0", name="ck_baseline_amount_non_negative"),
    )


class ExpenseRow(Base, TimestampMixin):
    """A cost the user recorded against an income they are pursuing.

    Note what this table does *not* have: no deductible flag, no tax rate, no
    saved-tax column. Whether a cost reduces someone's tax is a question for
    their Finanzamt, and a column here would be this product answering it.
    The rows are the user's own records; the product adds them up and produces
    questions.
    """

    __tablename__ = "expenses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    #: What the cost was for. At most one of these is set - an expense belongs
    #: to a stream or to an application, never to both.
    income_stream_id: Mapped[str | None] = mapped_column(
        ForeignKey("income_streams.id", ondelete="SET NULL"), default=None
    )
    application_id: Mapped[str | None] = mapped_column(
        ForeignKey("applications.id", ondelete="SET NULL"), default=None, index=True
    )
    label: Mapped[str] = mapped_column(String(200))
    amount_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    category: Mapped[str] = mapped_column(String(40), default="OTHER", index=True)
    incurred_on: Mapped[date] = mapped_column(Date, index=True)
    has_receipt: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    #: The user's own statement that the cost was partly private. Stored as
    #: given and never turned into a percentage by this product.
    partly_private: Mapped[str] = mapped_column(String(16), default="UNKNOWN")
    notes: Mapped[str | None] = mapped_column(Text, default=None)

    __table_args__ = (
        CheckConstraint("amount_minor >= 0", name="ck_expense_amount_non_negative"),
        CheckConstraint(
            "income_stream_id IS NULL OR application_id IS NULL",
            name="ck_expense_has_one_parent",
        ),
        Index("ix_expense_user_date", "user_id", "incurred_on"),
    )


# ============================================================ knowledge


class LegalFactRow(Base, TimestampMixin):
    __tablename__ = "legal_facts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    jurisdiction: Mapped[str] = mapped_column(String(8), default="DE", index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(300))
    summary: Mapped[str] = mapped_column(Text)
    structured_value: Mapped[dict[str, Any]] = mapped_column(JsonDict, default=dict)
    effective_from: Mapped[date | None] = mapped_column(Date, default=None, index=True)
    effective_to: Mapped[date | None] = mapped_column(Date, default=None)
    source_name: Mapped[str] = mapped_column(String(200))
    source_url: Mapped[str | None] = mapped_column(String(1000), default=None)
    retrieved_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)
    last_verified_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, default=None, index=True
    )
    verification_status: Mapped[str] = mapped_column(String(20), default="UNKNOWN", index=True)
    #: False for registry placeholders that no one has populated from the
    #: authority yet. Such rows are listed but never quoted.
    content_available: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (Index("ix_legal_lookup", "jurisdiction", "category", "verification_status"),)


class KnowledgeDocumentRow(Base, TimestampMixin):
    __tablename__ = "knowledge_documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    source_name: Mapped[str] = mapped_column(String(200))
    source_url: Mapped[str | None] = mapped_column(String(1000), default=None)
    jurisdiction: Mapped[str] = mapped_column(String(8), default="DE")
    topic: Mapped[str] = mapped_column(String(40), index=True)
    effective_year: Mapped[int | None] = mapped_column(Integer, default=None, index=True)
    retrieved_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)
    content_available: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    checksum: Mapped[str | None] = mapped_column(String(64), default=None)


class KnowledgeChunkRow(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    #: Metadata denormalised onto the chunk so a citation needs no join and
    #: cannot go missing if the parent document row is later reorganised.
    source_name: Mapped[str] = mapped_column(String(200))
    source_url: Mapped[str | None] = mapped_column(String(1000), default=None)
    title: Mapped[str] = mapped_column(String(300))
    jurisdiction: Mapped[str] = mapped_column(String(8), default="DE")
    topic: Mapped[str] = mapped_column(String(40), index=True)
    effective_year: Mapped[int | None] = mapped_column(Integer, default=None)
    retrieved_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)
    #: NULL when only lexical retrieval is configured, which is the default.
    embedding: Mapped[list[float] | None] = mapped_column(Vector, default=None)
    token_estimate: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("document_id", "ordinal", name="uq_chunk_position"),
        Index("ix_chunk_topic_year", "topic", "effective_year"),
    )


# =============================================== grow, family, feedback


class FinancialGoalRow(Base, TimestampMixin):
    __tablename__ = "financial_goals"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    goal_type: Mapped[str] = mapped_column(String(24), index=True)
    name: Mapped[str] = mapped_column(String(200))
    target_minor: Mapped[int] = mapped_column(Integer)
    target_date: Mapped[date | None] = mapped_column(Date, default=None)
    current_minor: Mapped[int] = mapped_column(Integer, default=0)
    monthly_contribution_minor: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")


class ChildGoalRow(Base, TimestampMixin):
    __tablename__ = "child_goals"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    #: A label the parent chooses. The product never needs a child's real name.
    child_label: Mapped[str] = mapped_column(String(80))
    child_age_years: Mapped[int] = mapped_column(Integer)
    target_age_years: Mapped[int] = mapped_column(Integer)
    target_minor: Mapped[int] = mapped_column(Integer, default=0)
    current_minor: Mapped[int] = mapped_column(Integer, default=0)
    monthly_contribution_minor: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")

    __table_args__ = (
        CheckConstraint("target_age_years > child_age_years", name="ck_child_ages_ordered"),
    )


class FeedbackEvent(Base):
    """The validation instrument. These rows are the startup's actual evidence."""

    __tablename__ = "feedback_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    opportunity_id: Mapped[str | None] = mapped_column(
        ForeignKey("opportunities.id", ondelete="SET NULL"), default=None, index=True
    )
    question: Mapped[str] = mapped_column(String(64), index=True)
    answer: Mapped[str] = mapped_column(String(32), index=True)
    reason: Mapped[str | None] = mapped_column(String(32), default=None, index=True)
    note: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=utcnow, index=True
    )


class AnalyticsEvent(Base):
    """First-party analytics. Properties are a closed allowlist per event name.

    ``user_id`` is a foreign key so analytics is deleted with the account. The
    allowlist in :mod:`app.services.analytics` is what keeps CV text and profile
    contents out of here - the schema alone could not.
    """

    __tablename__ = "analytics_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), default=None, index=True
    )
    name: Mapped[str] = mapped_column(String(64), index=True)
    properties: Mapped[dict[str, Any]] = mapped_column(JsonDict, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=utcnow, index=True
    )

    __table_args__ = (Index("ix_analytics_name_time", "name", "occurred_at"),)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(500), default=None)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=utcnow, index=True
    )
    read_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)

    __table_args__ = (Index("ix_notification_unread", "user_id", "read_at"),)


class LlmUsage(Base):
    """Per-call model usage. The basis for unit economics.

    Records what was spent and on which product purpose - never the prompt or
    the completion, which would put CV and tax-question content into a table
    nobody thinks of as personal data.
    """

    __tablename__ = "llm_usage"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), index=True)
    model: Mapped[str] = mapped_column(String(80), index=True)
    purpose: Mapped[str] = mapped_column(String(48), index=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, default=None)
    output_tokens: Mapped[int | None] = mapped_column(Integer, default=None)
    total_tokens: Mapped[int | None] = mapped_column(Integer, default=None)
    latency_ms: Mapped[int | None] = mapped_column(Integer, default=None)
    #: Only populated when a deterministic price list exists for the model.
    #: NULL rather than a guess, so cost dashboards cannot quietly invent spend.
    estimated_cost_micros: Mapped[int | None] = mapped_column(Integer, default=None)
    success: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    error_kind: Mapped[str | None] = mapped_column(String(48), default=None)
    occurred_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=utcnow, index=True
    )

    __table_args__ = (Index("ix_llm_usage_purpose_time", "purpose", "occurred_at"),)


class AuditEvent(Base):
    """Security- and privacy-relevant actions.

    Deliberately NOT cascaded from ``users``: the record that an account was
    deleted must outlive the account. It carries a hashed subject id rather than
    a foreign key, so it is not personal data on its own.
    """

    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    subject_hash: Mapped[str | None] = mapped_column(String(64), default=None, index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    detail: Mapped[dict[str, Any]] = mapped_column(JsonDict, default=dict)
    ip_hash: Mapped[str | None] = mapped_column(String(64), default=None)
    occurred_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=utcnow, index=True
    )
