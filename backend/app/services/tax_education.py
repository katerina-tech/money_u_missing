"""KEEP: source-backed German tax and administrative education.

The behavioural rule, enforced structurally rather than by disclaimer: **this
module cannot produce an answer it has no source for.**

Three gates, in order:

1. **Retrieval.** Nothing retrieved means nothing to answer from. The refusal
   text says what is missing rather than apologising vaguely.
2. **Freshness.** Every legal fact the question touches is checked against its
   review horizon. A fact whose source has not been re-verified within a year
   is reported as NEEDS_REVIEW - because a German tax threshold that moved in
   January is worse than no answer at all, and a model has no way to know which
   year's number it learned.
3. **Citation.** :class:`~app.domain.legal.CitedAnswer` refuses to validate an
   answered response with no citations. Even if the prompt were subverted, an
   uncited answer cannot be constructed.

What it will not do, ever: state a tax amount owed, classify the user's
activity as freiberuflich or gewerblich, or tell anyone which legal form to
choose. Those turn on facts this product cannot see and are contested between
tax offices. Instead it produces the specific questions to put to a
Steuerberater or Finanzamt - which is the actually useful output.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.domain.enums import LegalCategory, LegalVerificationStatus
from app.domain.legal import Citation, CitedAnswer, KnowledgeChunk, LegalFact
from app.llm import prompts
from app.llm.base import LLMError, LLMProvider, Purpose
from app.logging_config import Event, log_event, redact_text
from app.rag.embeddings import tokenise
from app.rag.store import KnowledgeStore
from app.security.guard import InjectionGuard, Provenance
from app.services.legal_facts import LegalFactRepository

logger = logging.getLogger(__name__)

MAX_EXCERPT_CHARS = 600

#: Question keywords to the topics that answer them. Deliberately explicit: a
#: model deciding which topic a benefits question belongs to could route it to
#: general VAT guidance and answer confidently from the wrong corpus.
TOPIC_KEYWORDS: dict[LegalCategory, tuple[str, ...]] = {
    LegalCategory.VAT: ("umsatzsteuer", "vat", "mehrwertsteuer", "kleinunternehmer", "19%", "ust"),
    LegalCategory.TRADE_REGISTRATION: ("gewerbe", "gewerbeanmeldung", "trade licence", "freiberuf"),
    LegalCategory.SELF_EMPLOYMENT: (
        "selbststaendig",
        "selbstaendig",
        "nebenberuflich",
        "freelance",
        "self-employed",
    ),
    LegalCategory.INCOME_TAX: (
        "einkommensteuer",
        "income tax",
        "steuererklaerung",
        "grundfreibetrag",
        "steuer",
    ),
    LegalCategory.INVOICING: ("rechnung", "invoice", "pflichtangaben"),
    LegalCategory.ACCOUNTING: (
        "euer",
        "buchhaltung",
        "bookkeeping",
        "betriebsausgaben",
        "expenses",
    ),
    LegalCategory.EMPLOYMENT: ("arbeitgeber", "employer", "nebentaetigkeit", "arbeitsvertrag"),
    LegalCategory.SOCIAL_INSURANCE: (
        "sozialversicherung",
        "krankenversicherung",
        "rentenversicherung",
        "social insurance",
    ),
    LegalCategory.BENEFITS: (
        "arbeitslosengeld",
        "buergergeld",
        "jobcenter",
        "benefit",
        "alg",
        "unemployment",
    ),
    LegalCategory.MINIJOB: ("minijob", "geringfuegig", "538", "556"),
    LegalCategory.CAPITAL_INCOME: (
        "kapitalertrag",
        "sparer-pauschbetrag",
        "abgeltungsteuer",
        "capital gains",
        "etf",
    ),
    LegalCategory.FAMILY: ("kind", "child", "junior depot", "kindergeld"),
}


class DraftedAnswer(BaseModel):
    """What the model may return. Every claim must name its passage."""

    model_config = ConfigDict(extra="forbid")

    answered: bool
    answer: str = Field(default="", max_length=3000)
    #: 1-based indices into the passages provided. The composer maps these back
    #: to real citations and drops any index the model invented.
    passage_numbers: list[int] = Field(default_factory=list)
    what_depends_on_circumstances: list[str] = Field(default_factory=list)
    questions_to_verify: list[str] = Field(default_factory=list)
    missing_information: str | None = None


def classify_topics(question: str) -> list[LegalCategory]:
    """Keyword routing. Returns every plausible topic, never guesses one."""
    lowered = question.lower()
    matched = [
        topic
        for topic, keywords in TOPIC_KEYWORDS.items()
        if any(keyword in lowered for keyword in keywords)
    ]
    return matched


#: Jurisdictions this corpus does not cover. Named explicitly because a question
#: about Portuguese capital gains retrieves German passages about capital income
#: with a *higher* BM25 score than a good German question does - the shared
#: vocabulary is the problem, and no relevance threshold can separate them.
#: Saying "we only cover Germany" is both the accurate answer and the useful one.
_OTHER_JURISDICTIONS: dict[str, str] = {
    "austria": "Austria",
    "oesterreich": "Austria",
    "switzerland": "Switzerland",
    "schweiz": "Switzerland",
    "portugal": "Portugal",
    "spain": "Spain",
    "spanien": "Spain",
    "france": "France",
    "frankreich": "France",
    "italy": "Italy",
    "italien": "Italy",
    "ireland": "Ireland",
    "irland": "Ireland",
    "netherlands": "the Netherlands",
    "niederlande": "the Netherlands",
    "poland": "Poland",
    "polen": "Poland",
    "uk": "the UK",
    "united kingdom": "the UK",
    "england": "the UK",
    "usa": "the USA",
    "united states": "the USA",
    "estonia": "Estonia",
    "dubai": "the UAE",
    "uae": "the UAE",
    "cyprus": "Cyprus",
}

#: A question term must be at least this long to count as distinctive. Shorter
#: words are overwhelmingly function words that survive the stopword list.
DISTINCTIVE_TERM_LENGTH = 5


def named_other_jurisdiction(question: str) -> str | None:
    """The non-German jurisdiction a question names, if any."""
    lowered = f" {question.lower()} "
    for needle, label in _OTHER_JURISDICTIONS.items():
        if any(f" {needle}{tail}" in lowered for tail in (" ", "?", ".", ",", "'s ")):
            return label
    return None


def covered_terms(question: str, passages: list[KnowledgeChunk]) -> set[str]:
    """The question's distinctive terms that the passages actually contain.

    Matching allows German compounding in both directions: a question about
    "Nebentaetigkeit" is covered by a passage that says
    "Nebentaetigkeitsklausel", and vice versa. Requiring exact token equality
    made the retriever look like it had missed a document it had in fact found
    exactly - German compounds are the normal case in this corpus, not an edge
    one.
    """
    terms = {t for t in tokenise(question) if len(t) >= DISTINCTIVE_TERM_LENGTH}
    if not terms:
        return set()
    haystack = set(tokenise(" ".join(chunk.text for chunk in passages)))
    return {
        term
        for term in terms
        if term in haystack or any(term in word or word in term for word in haystack)
    }


def covers_question(question: str, passages: list[KnowledgeChunk]) -> bool:
    """Whether the corpus plausibly covers this question at all.

    The gate that catches a question the corpus simply does not hold. A
    relevance score cannot do this job: BM25 returns a best match for "how do I
    bake sourdough bread" too, because something is always the closest thing
    available, and it scores that match *higher* than some genuine questions.

    One distinctive shared term is enough. Demanding a fraction of the query
    punished long, well-specified questions - which are exactly the ones worth
    answering.
    """
    distinctive = {t for t in tokenise(question) if len(t) >= DISTINCTIVE_TERM_LENGTH}
    if not distinctive:
        # Nothing distinctive was asked. Retrieval cannot be shown to be
        # relevant, so we do not build an answer on it.
        return False
    return bool(covered_terms(question, passages))


class TaxEducationService:
    def __init__(
        self,
        store: KnowledgeStore,
        facts: LegalFactRepository,
        provider: LLMProvider,
        guard: InjectionGuard,
        settings: Settings | None = None,
    ) -> None:
        self._store = store
        self._facts = facts
        self._provider = provider
        self._guard = guard
        self._settings = settings or get_settings()

    def answer(self, session: Session, question: str) -> CitedAnswer:
        """Answer from retrieved sources, or decline and say why."""
        clean = self._guard.screen(question, Provenance.USER_TEXT)
        log_event(logger, Event.TAX_QUESTION_ASKED, "tax question received", **redact_text(clean))

        # Scope gate. Our corpus is German law only, and a question about
        # another country retrieves German passages that share its vocabulary.
        # Answering from those would be worse than useless.
        elsewhere = named_other_jurisdiction(clean)
        if elsewhere is not None:
            return self._refuse(
                clean,
                f"We only hold verified source material for Germany, so we cannot answer "
                f"a question about {elsewhere}. Everything in this section comes from "
                "German federal legislation and authorities.",
            )

        topics = classify_topics(clean)
        passages = self._store.retrieve(session, clean, topics=topics or None)
        if not passages and topics:
            # The topic filter may be wrong; retry unfiltered before giving up.
            passages = self._store.retrieve(session, clean)

        if not passages or not covers_question(clean, passages):
            return self._refuse(
                clean,
                "We do not have verified source material covering this question, so we "
                "will not answer it from memory. Rules and thresholds change, and an "
                "answer we cannot point at a source for is not worth having.",
            )

        facts, warnings = self._relevant_facts(session, topics)

        if not self._provider.available:
            # No model: return the passages themselves. Less polished, entirely
            # honest, and still the actual source material.
            return self._passages_only(clean, passages, warnings)

        try:
            drafted = self._provider.structured(
                DraftedAnswer,
                prompts.tax_answer_messages(clean, _render_passages(passages)),
                purpose=Purpose.TAX_ANSWER,
            )
        except LLMError:
            return self._passages_only(clean, passages, warnings)

        if not drafted.answered:
            return self._refuse(
                clean,
                drafted.missing_information
                or "The sources we hold do not cover this question closely enough to answer it.",
            )

        citations = _citations_for(drafted.passage_numbers, passages)
        if not citations:
            # The model answered but cited nothing traceable. That is exactly
            # the failure mode this module exists to prevent, so it becomes a
            # refusal rather than an uncited answer.
            log_event(
                logger,
                Event.TAX_ANSWER_REFUSED,
                "model answered without usable citations",
                level=logging.WARNING,
            )
            return self._refuse(
                clean,
                "We could not tie an answer to a specific source passage, so we are not "
                "showing one. The sources we hold on this topic are listed below.",
            )

        return CitedAnswer(
            question=clean,
            answered=True,
            answer=drafted.answer.strip(),
            citations=citations,
            facts_used=[fact.id for fact in facts],
            staleness_warnings=warnings,
            questions_to_verify=drafted.questions_to_verify
            or _default_questions(drafted.what_depends_on_circumstances),
        )

    # ------------------------------------------------------------- helpers
    def _relevant_facts(
        self, session: Session, topics: list[LegalCategory]
    ) -> tuple[list[LegalFact], list[str]]:
        """Facts for the topic, plus a warning for each past its review horizon."""
        max_age = timedelta(days=self._settings.legal_fact_max_age_days)
        facts = self._facts.for_topics(session, topics) if topics else []
        warnings: list[str] = []
        for fact in facts:
            status = fact.effective_status(max_age=max_age)
            if status in {
                LegalVerificationStatus.NEEDS_REVIEW,
                LegalVerificationStatus.EXPIRED,
                LegalVerificationStatus.UNKNOWN,
            }:
                warnings.append(
                    f"'{fact.title}' has not been re-verified against {fact.source_name} "
                    f"recently ({status.value}). Check the current figure at the source "
                    "before relying on it."
                )
                log_event(
                    logger,
                    Event.LEGAL_FACT_STALE,
                    "legal fact past its review horizon",
                    level=logging.WARNING,
                    fact_id=fact.id,
                    status=status.value,
                )
        return facts, warnings

    def _passages_only(
        self, question: str, passages: list[KnowledgeChunk], warnings: list[str]
    ) -> CitedAnswer:
        return CitedAnswer(
            question=question,
            answered=True,
            answer=(
                "We are showing the relevant source passages directly, because "
                "AI-assisted summarising is unavailable right now. These are the "
                "sources we would have summarised."
            ),
            citations=[_to_citation(p) for p in passages],
            staleness_warnings=warnings,
            questions_to_verify=_default_questions([]),
        )

    def _refuse(self, question: str, reason: str) -> CitedAnswer:
        log_event(logger, Event.TAX_ANSWER_REFUSED, "declined to answer", reason=reason[:120])
        return CitedAnswer.refuse(question, reason)


def _render_passages(passages: list[KnowledgeChunk]) -> str:
    return "\n\n".join(
        f"[{index}] {chunk.title} ({chunk.source_name}"
        + (f", {chunk.effective_year}" if chunk.effective_year else "")
        + f")\n{chunk.text}"
        for index, chunk in enumerate(passages, start=1)
    )


def _citations_for(numbers: list[int], passages: list[KnowledgeChunk]) -> list[Citation]:
    """Map the model's passage numbers to real citations, dropping invented ones."""
    seen: set[str] = set()
    citations: list[Citation] = []
    for number in numbers:
        if not 1 <= number <= len(passages):
            continue
        chunk = passages[number - 1]
        if chunk.id in seen:
            continue
        seen.add(chunk.id)
        citations.append(_to_citation(chunk))
    return citations


def _to_citation(chunk: KnowledgeChunk) -> Citation:
    return Citation(
        source_name=chunk.source_name,
        source_url=chunk.source_url,
        title=chunk.title,
        chunk_id=chunk.id,
        effective_year=chunk.effective_year,
        retrieved_at=chunk.retrieved_at,
        excerpt=chunk.text[:MAX_EXCERPT_CHARS],
    )


def _default_questions(depends_on: list[str]) -> list[str]:
    """Concrete questions, never "consult a professional".

    A generic instruction to seek advice is what someone does instead of
    helping. A list of the actual questions is what makes the appointment
    useful and short.
    """
    base = [
        "Does my planned activity count as freiberuflich or gewerblich in my case, "
        "and what specifically determines that?",
        "Do I need to submit a Fragebogen zur steuerlichen Erfassung, and by when?",
        "Given my expected turnover, does the Kleinunternehmerregelung apply to me, "
        "and what happens if I exceed the threshold mid-year?",
        "What must appear on my invoices for this kind of work?",
    ]
    return [*depends_on, *base][:6]
