"""KEEP and GROW: citation requirement, freshness, calculators, boundaries."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.enums import LegalCategory, LegalVerificationStatus, TrustLabel
from app.domain.legal import CitedAnswer, LegalFact
from app.llm.factory import NullProvider
from app.llm.testing import FailingProvider
from app.rag.chunking import chunk_markdown
from app.rag.embeddings import BM25Index, tokenise
from app.rag.store import KnowledgeStore
from app.security.guard import InjectionGuard
from app.services.calculators import (
    CalculatorInputError,
    contribution_needed_minor,
    ownership_comparison,
    project,
)
from app.services.germany_check import GermanyCheckService
from app.services.legal_facts import LegalFactRepository
from app.services.tax_education import TaxEducationService, classify_topics
from tests.conftest import make_opportunity, make_profile


@pytest.fixture
def knowledge(session: Session) -> KnowledgeStore:
    settings = get_settings()
    LegalFactRepository(settings).load_from_file(session, settings.data_dir / "legal_facts.json")
    store = KnowledgeStore(settings)
    store.ingest_directory(session, settings.knowledge_dir)
    session.flush()
    return store


# ================================================ the citation guarantee


def test_an_answered_response_cannot_exist_without_citations() -> None:
    with pytest.raises(ValueError, match="citation"):
        CitedAnswer(question="q", answered=True, answer="Yes, definitely.")


def test_an_unanswered_response_must_explain_itself() -> None:
    with pytest.raises(ValueError, match="explain"):
        CitedAnswer(question="q", answered=False)


def test_a_question_with_no_supporting_corpus_is_declined(session: Session) -> None:
    """No retrieval, no answer. Never from model memory."""
    settings = get_settings()
    service = TaxEducationService(
        KnowledgeStore(settings),  # empty corpus
        LegalFactRepository(settings),
        NullProvider(),
        InjectionGuard(None),
    )
    answer = service.answer(session, "What is the current Kleinunternehmer threshold?")
    assert answer.answered is False
    assert "verified source material" in (answer.refusal or "")


def test_an_answer_from_the_corpus_carries_its_sources(
    session: Session, knowledge: KnowledgeStore
) -> None:
    service = TaxEducationService(
        knowledge, LegalFactRepository(), NullProvider(), InjectionGuard(None)
    )
    answer = service.answer(session, "Kleinunternehmerregelung Umsatzsteuer threshold")
    assert answer.answered is True
    assert answer.citations
    assert all(c.source_url for c in answer.citations)
    assert all(c.excerpt for c in answer.citations)


def test_the_answer_layer_survives_a_model_outage(
    session: Session, knowledge: KnowledgeStore
) -> None:
    service = TaxEducationService(
        knowledge, LegalFactRepository(), FailingProvider(), InjectionGuard(None)
    )
    answer = service.answer(session, "Do I need a Gewerbeanmeldung?")
    assert answer.answered is True
    assert answer.citations, "it must fall back to the sources, not to memory"


def test_topic_routing_is_keyword_based_and_multi_valued() -> None:
    topics = classify_topics("Do I need a Gewerbe and do I charge Umsatzsteuer?")
    assert LegalCategory.TRADE_REGISTRATION in topics
    assert LegalCategory.VAT in topics


# ============================================================ freshness


def test_a_fact_past_its_review_horizon_is_reported_as_needing_review() -> None:
    old = datetime.now(UTC) - timedelta(days=800)
    fact = LegalFact(
        id="x",
        category=LegalCategory.VAT,
        title="t",
        summary="s",
        source_name="src",
        retrieved_at=old,
        last_verified_at=old,
        verification_status=LegalVerificationStatus.VERIFIED,
    )
    status = fact.effective_status(max_age=timedelta(days=365))
    assert status is LegalVerificationStatus.NEEDS_REVIEW
    assert fact.trust(max_age=timedelta(days=365)) is TrustLabel.NEEDS_REVIEW


def test_a_fact_whose_period_has_ended_is_expired() -> None:
    fact = LegalFact(
        id="x",
        category=LegalCategory.VAT,
        title="t",
        summary="s",
        source_name="src",
        effective_from=date(2020, 1, 1),
        effective_to=date(2021, 12, 31),
        retrieved_at=datetime.now(UTC),
        last_verified_at=datetime.now(UTC),
        verification_status=LegalVerificationStatus.VERIFIED,
    )
    assert fact.effective_status(max_age=timedelta(days=365)) is LegalVerificationStatus.EXPIRED


def test_an_unpopulated_registry_entry_is_never_quoted(
    session: Session, knowledge: KnowledgeStore
) -> None:
    """The Minijob euro figure is the real case: the statute gives a formula."""
    facts = LegalFactRepository()
    minijob = facts.get(session, "de_minijob_threshold")
    assert minijob is not None
    assert minijob.content_available is False
    assert minijob.structured_value["amount_eur"] is None
    quotable = facts.for_topics(session, [LegalCategory.MINIJOB])
    assert all(f.id != "de_minijob_threshold" for f in quotable)


def test_every_shipped_fact_names_a_source(session: Session, knowledge: KnowledgeStore) -> None:
    for fact in LegalFactRepository().all(session):
        assert fact.source_name
        assert fact.source_url, f"{fact.id} has no source URL"


# ======================================================== germany check


def test_the_germany_check_never_makes_a_determination(
    session: Session, knowledge: KnowledgeStore
) -> None:
    check = GermanyCheckService(LegalFactRepository()).check(
        session, make_profile(), make_opportunity()
    )
    joined = " ".join(check.considerations).lower()
    for forbidden in ("you are freiberuflich", "you are gewerblich", "you must register"):
        assert forbidden not in joined
    assert any("depends" in line.lower() for line in check.considerations)
    assert check.questions_to_check


def test_benefit_guidance_appears_only_on_explicit_disclosure(
    session: Session, knowledge: KnowledgeStore
) -> None:
    from app.domain.enums import BenefitDisclosure

    service = GermanyCheckService(LegalFactRepository())
    silent = make_profile()
    assert service.check(session, silent, make_opportunity()).benefit_notes == []

    disclosed = make_profile()
    disclosed.admin.receives_employment_benefits = BenefitDisclosure.YES
    assert service.check(session, disclosed, make_opportunity()).benefit_notes


def test_employer_guidance_appears_only_for_employees(
    session: Session, knowledge: KnowledgeStore
) -> None:
    from app.domain.enums import WorkStatus

    service = GermanyCheckService(LegalFactRepository())
    employee = make_profile(work_status=WorkStatus.EMPLOYEE)
    student = make_profile(work_status=WorkStatus.STUDENT)
    assert service.check(session, employee, make_opportunity()).employment_notes
    assert service.check(session, student, make_opportunity()).employment_notes == []


def test_a_demo_opportunity_says_so_in_its_germany_check(
    session: Session, knowledge: KnowledgeStore
) -> None:
    demo = make_opportunity(is_demo=True, compensation_verified=False)
    check = GermanyCheckService(LegalFactRepository()).check(session, make_profile(), demo)
    assert "demo" in check.considerations[0].lower()


# ============================================================ retrieval


def test_chunks_carry_their_heading_trail() -> None:
    chunks = chunk_markdown("# Tax\n\n## VAT\n\nThe threshold is stated here.\n")
    assert any("VAT" in chunk.heading_path for chunk in chunks)
    assert any("VAT" in chunk.text for chunk in chunks)


def test_bm25_finds_the_rare_german_compound() -> None:
    index = BM25Index()
    index.build(
        [
            ("a", "Die Kleinunternehmerregelung nach Paragraf 19 UStG befreit von der Umsatzsteuer"),
            ("b", "Ein Lehrauftrag an einer Hochschule wird mit einem Honorar verguetet"),
            ("c", "Allgemeine Informationen ueber Steuern in Deutschland"),
        ]
    )
    results = index.search("Kleinunternehmerregelung", top_k=2)
    assert results[0][0] == "a"


def test_stopwords_are_removed_from_both_languages() -> None:
    assert "der" not in tokenise("der Steuersatz")
    assert "the" not in tokenise("the tax rate")
    assert "steuersatz" in tokenise("der Steuersatz")


# ========================================================== calculators


def test_projection_is_deterministic_and_conservative() -> None:
    result = project(
        initial_minor=0, monthly_contribution_minor=10_000, annual_return=0.05, months=12
    )
    assert result.total_contributed_minor == 120_000
    # End-of-month contributions: the final month's payment earns no growth.
    assert 120_000 < result.final_balance_minor < 124_000
    again = project(
        initial_minor=0, monthly_contribution_minor=10_000, annual_return=0.05, months=12
    )
    assert again.final_balance_minor == result.final_balance_minor


def test_a_zero_return_grows_by_exactly_the_contributions() -> None:
    result = project(
        initial_minor=50_000, monthly_contribution_minor=10_000, annual_return=0.0, months=24
    )
    assert result.final_balance_minor == 50_000 + 240_000
    assert result.growth_minor == 0


def test_negative_returns_are_permitted() -> None:
    result = project(
        initial_minor=100_000, monthly_contribution_minor=0, annual_return=-0.10, months=12
    )
    assert result.final_balance_minor < 100_000


def test_absurd_assumptions_are_refused_rather_than_rendered() -> None:
    with pytest.raises(CalculatorInputError):
        project(initial_minor=0, monthly_contribution_minor=1, annual_return=0.9, months=12)
    with pytest.raises(CalculatorInputError):
        project(initial_minor=0, monthly_contribution_minor=1, annual_return=0.05, months=10_000)


def test_every_projection_carries_its_disclaimer() -> None:
    result = project(
        initial_minor=0, monthly_contribution_minor=1000, annual_return=0.05, months=12
    )
    assert "not a forecast" in result.disclaimer


def test_inflation_adjustment_is_absent_unless_asked_for() -> None:
    plain = project(
        initial_minor=0, monthly_contribution_minor=1000, annual_return=0.05, months=12
    )
    assert plain.final_real_balance_minor is None
    adjusted = project(
        initial_minor=0,
        monthly_contribution_minor=1000,
        annual_return=0.05,
        months=12,
        annual_inflation=0.02,
    )
    assert adjusted.final_real_balance_minor is not None
    assert adjusted.final_real_balance_minor < adjusted.final_balance_minor


def test_an_unreachable_target_returns_none_not_a_nonsense_figure() -> None:
    assert (
        contribution_needed_minor(
            target_minor=1_000_000, initial_minor=0, annual_return=0.05, months=0
        )
        is None
    )


def test_an_already_met_target_needs_no_contribution() -> None:
    assert (
        contribution_needed_minor(
            target_minor=100, initial_minor=1_000_000, annual_return=0.05, months=12
        )
        == 0
    )


# =================================================== regulatory boundary


def test_the_family_comparison_has_no_recommended_option() -> None:
    comparison = ownership_comparison()
    assert comparison.recommended is None
    assert comparison.considerations
    assert "no generally correct answer" in comparison.note


def test_no_calculator_consults_a_language_model() -> None:
    import inspect

    from app.services import calculators

    source = inspect.getsource(calculators)
    # Code-level markers only: the word "provider" legitimately appears in the
    # family module's prose, where it means a bank or broker.
    for forbidden in ("LLMProvider", "app.llm", ".structured(", "Purpose."):
        assert forbidden not in source


def test_etf_education_names_no_product_and_recommends_nothing() -> None:
    from app.api.routes.grow import etf_education

    payload = etf_education()
    assert "not investment advice" in payload["disclaimer"].lower()
    text = " ".join(term["explanation"] for term in payload["terms"]).lower()
    for forbidden in ("you should buy", "best for you", "we recommend", "ishares", "vanguard"):
        assert forbidden not in text
