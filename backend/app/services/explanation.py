"""Turning a computed score into prose - and only that.

The model is handed a finished :class:`~app.domain.matching.MatchScore` rendered
as text and asked to phrase it. It does not see the profile, the weights, or any
code path that could change a number. If it is unavailable, the UI falls back to
the bullet list, which is what the explanation is derived from anyway - so the
degraded state loses polish, not information.

The output is validated against a schema that forbids new claims, and the caller
labels it in the UI as AI-written. The computed bullets remain the source of
truth and are always displayed alongside.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, ConfigDict, Field

from app.domain.matching import MatchScore
from app.domain.opportunity import Opportunity
from app.llm import prompts
from app.llm.base import LLMError, LLMProvider, Purpose

logger = logging.getLogger(__name__)


class Explanation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Two or three sentences. Length-capped so a model cannot pad a weak match
    #: into something that reads convincing.
    text: str = Field(max_length=700)
    #: Restated uncertainties. Required non-empty when the score has any, which
    #: is checked below - an explanation that quietly drops the caveats is worse
    #: than no explanation.
    uncertainties_restated: list[str] = Field(default_factory=list)


def render_breakdown(match: MatchScore) -> str:
    lines = [f"Total match score: {match.total_score}%", ""]
    lines.extend(match.explanation_inputs)
    if match.hard_failures:
        lines.append("")
        lines.append("This opportunity is blocked by a stated requirement:")
        lines.extend(f"- {failure.explanation}" for failure in match.hard_failures)
    return "\n".join(lines)


def render_opportunity(opportunity: Opportunity) -> str:
    parts = [
        f"Title: {opportunity.title}",
        f"Organisation: {opportunity.organization or 'not stated'}",
        f"Category: {opportunity.category.value}",
        f"Arrangement: {opportunity.remote_type.value}",
    ]
    if opportunity.compensation.known:
        parts.append(
            "Compensation as published: "
            f"{(opportunity.compensation.conservative_minor or 0) / 100:,.0f} "
            f"{opportunity.compensation.currency} "
            f"({opportunity.compensation.basis.value}, {opportunity.compensation.period.value})"
        )
    else:
        parts.append("Compensation: not published by the source")
    return "\n".join(parts)


def explain_match(
    provider: LLMProvider, match: MatchScore, opportunity: Opportunity
) -> str | None:
    """Prose explanation, or ``None`` when a model is unavailable or misbehaves."""
    if not provider.available:
        return None
    try:
        explanation = provider.structured(
            Explanation,
            prompts.match_explanation_messages(
                render_breakdown(match), render_opportunity(opportunity)
            ),
            purpose=Purpose.MATCH_EXPLANATION,
        )
    except LLMError:
        return None

    # The explanation must not lose the caveats. If the model dropped them, the
    # bullets stand alone rather than the prose replacing them - a confident
    # paragraph with the uncertainties removed is the exact failure this whole
    # architecture is arranged to prevent.
    if match.uncertainties and not explanation.uncertainties_restated:
        logger.info("explanation dropped the uncertainties; falling back to the bullet list")
        return None
    return explanation.text.strip() or None
