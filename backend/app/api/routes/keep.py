"""KEEP: German tax and administrative education, always cited."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api import dto
from app.api.deps import (
    current_user,
    get_db,
    get_guard,
    get_knowledge_store,
    get_legal_facts,
    get_provider,
    rate_limit,
)
from app.db.models import User
from app.llm.base import LLMProvider
from app.rag.store import KnowledgeStore
from app.security.guard import InjectionGuard
from app.services import analytics
from app.services.legal_facts import LegalFactRepository
from app.services.tax_education import TaxEducationService, classify_topics

router = APIRouter(prefix="/api/tax", tags=["keep"], dependencies=[Depends(rate_limit)])


@router.post("/ask", response_model=dto.TaxAnswerResponse)
def ask(
    payload: dto.TaxQuestionRequest,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
    store: KnowledgeStore = Depends(get_knowledge_store),
    facts: LegalFactRepository = Depends(get_legal_facts),
    provider: LLMProvider = Depends(get_provider),
    guard: InjectionGuard = Depends(get_guard),
) -> dto.TaxAnswerResponse:
    """Answer from retrieved sources, or decline and say what is missing.

    There is no path through this endpoint that produces an answer without a
    citation. When retrieval comes back empty, or every relevant fact is past
    its review horizon, it refuses - which is the correct behaviour for a
    product that would otherwise be confidently quoting last year's threshold.
    """
    service = TaxEducationService(store, facts, provider, guard)
    answer = service.answer(session, payload.question)

    topics = classify_topics(payload.question)
    analytics.record(
        session,
        "tax_check_viewed",
        user_id=user.id,
        topic=topics[0].value if topics else "unknown",
        needs_verification=bool(answer.staleness_warnings),
    )
    return dto.TaxAnswerResponse(
        question=answer.question,
        answered=answer.answered,
        answer=answer.answer,
        refusal=answer.refusal,
        citations=[
            dto.CitationDto(
                source_name=c.source_name,
                source_url=str(c.source_url) if c.source_url else None,
                title=c.title,
                effective_year=c.effective_year,
                retrieved_at=c.retrieved_at,
                excerpt=c.excerpt,
            )
            for c in answer.citations
        ],
        staleness_warnings=answer.staleness_warnings,
        questions_to_verify=answer.questions_to_verify,
    )


@router.get("/facts", response_model=list[dto.LegalFactDto])
def list_facts(
    session: Session = Depends(get_db),
    facts: LegalFactRepository = Depends(get_legal_facts),
) -> list[dto.LegalFactDto]:
    """Every stored fact with its verification state - including the gaps.

    Entries we could not populate from the authority are listed with
    ``content_available`` false and an UNKNOWN status, rather than omitted. A
    visible gap can be filled; an invisible one cannot.
    """
    return [
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
        for fact in facts.all(session)
    ]


@router.get("/topics")
def topics() -> dict[str, list[str]]:
    """The subjects the corpus actually covers, so the UI does not over-promise."""
    from app.services.tax_education import TOPIC_KEYWORDS

    return {"topics": sorted(topic.value for topic in TOPIC_KEYWORDS)}


@router.get("/status")
def knowledge_status(
    session: Session = Depends(get_db),
    store: KnowledgeStore = Depends(get_knowledge_store),
    facts: LegalFactRepository = Depends(get_legal_facts),
) -> dict[str, object]:
    return {"corpus": store.stats(session), "facts": facts.status_report(session)}
