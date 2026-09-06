"""Running discovery and persisting what it found.

Sits between the graph (which computes) and the API (which serves). Two jobs:

* **Upsert by fingerprint**, so the same opportunity discovered on Tuesday and
  again on Friday is one row with an updated ``retrieved_at``, not two. The
  fingerprint is a unique constraint, so this holds even under a race.
* **Store the score with its component breakdown and weights version**, so
  "why did this drop from 91 to 74?" is answerable later. A stored total alone
  would make that question permanently unanswerable.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import mappers
from app.db.models import Opportunity as OpportunityRow
from app.db.models import OpportunityMatch, SavedOpportunity
from app.domain.matching import RankedOpportunity
from app.domain.opportunity import Opportunity
from app.domain.profile import UserProfile
from app.graph.state import Deps, DiscoveryState
from app.graph.workflow import run_pipeline
from app.logging_config import Event, log_event
from app.services import analytics

logger = logging.getLogger(__name__)


def discover(profile: UserProfile, deps: Deps) -> DiscoveryState:
    """Run the pipeline and persist the results. Returns the full state."""
    state = run_pipeline(profile, deps)
    session = deps.session

    stored: dict[str, str] = {}
    for opportunity in state.get("opportunities", []):
        stored[opportunity.id] = _upsert(session, opportunity)
    session.flush()

    # Re-key the ranked list onto the persisted row ids so every later request
    # - opening a card, saving it, tracking it - addresses the same identifier.
    reranked: list[RankedOpportunity] = []
    for ranked in state.get("ranked", []):
        row_id = stored.get(ranked.opportunity_id)
        if row_id is None:
            continue
        reranked.append(
            ranked.model_copy(
                update={
                    "opportunity_id": row_id,
                    "match": ranked.match.model_copy(update={"opportunity_id": row_id}),
                    "actionability": ranked.actionability.model_copy(
                        update={"opportunity_id": row_id}
                    ),
                }
            )
        )
        _store_match(session, profile.user_id, row_id, reranked[-1])

    state["ranked"] = reranked
    state["opportunities"] = [
        opportunity.model_copy(update={"id": stored[opportunity.id]})
        for opportunity in state.get("opportunities", [])
        if opportunity.id in stored
    ]
    best = state.get("best_next_move")
    if best is not None and best.opportunity_id in stored:
        state["best_next_move"] = best.model_copy(
            update={"opportunity_id": stored[best.opportunity_id]}
        )
    elif best is not None:
        state["best_next_move"] = None

    analytics.record(
        session,
        "opportunities_returned",
        user_id=profile.user_id,
        returned=len(reranked),
        considered=state.get("considered", 0),
        blocked_unsafe=state.get("blocked_unsafe", 0),
        blocked_injection=state.get("blocked_injection", 0),
        deduped=state.get("duplicates_removed", 0),
        sources=state.get("sources_queried", 0),
    )
    log_event(
        logger,
        Event.MONEY_MAP_BUILT,
        "discovery run complete",
        returned=len(reranked),
        considered=state.get("considered", 0),
        live_search=state.get("live_search_used", False),
    )
    return state


def _upsert(session: Session, opportunity: Opportunity) -> str:
    """Insert or refresh one opportunity row. Returns its id."""
    fingerprint = opportunity.fingerprint()
    row = session.execute(
        select(OpportunityRow).where(OpportunityRow.fingerprint == fingerprint)
    ).scalar_one_or_none()
    values = mappers.opportunity_to_row_values(opportunity)

    if row is None:
        row = OpportunityRow(**values)
        session.add(row)
        session.flush()
        return row.id

    # Refresh what may have changed, but never overwrite a known value with an
    # unknown one: a source that omits a field this time has not retracted it.
    protected = {
        "compensation_min_minor",
        "compensation_max_minor",
        "deadline",
        "estimated_hours_min",
        "estimated_hours_max",
        "description",
    }
    for key, value in values.items():
        if key == "fingerprint":
            continue
        if key in protected and value is None and getattr(row, key) is not None:
            continue
        setattr(row, key, value)
    row.updated_at = datetime.now(UTC)
    return row.id


def _store_match(
    session: Session, user_id: str, opportunity_id: str, ranked: RankedOpportunity
) -> None:
    row = session.execute(
        select(OpportunityMatch).where(
            OpportunityMatch.user_id == user_id,
            OpportunityMatch.opportunity_id == opportunity_id,
        )
    ).scalar_one_or_none()
    values = {
        "total_score": ranked.match.total_score,
        "components": {"items": [c.model_dump() for c in ranked.match.components]},
        "hard_failures": {"items": [f.model_dump() for f in ranked.match.hard_failures]},
        "uncertainties": {"items": [u.model_dump() for u in ranked.match.uncertainties]},
        "explanation_inputs": ranked.match.explanation_inputs,
        "actionability_score": ranked.actionability.score,
        "actionability_band": ranked.actionability.band.value,
        "actionability_factors": {
            "items": [f.model_dump() for f in ranked.actionability.factors]
        },
        "weights_version": ranked.match.weights_version,
    }
    if row is None:
        session.add(
            OpportunityMatch(user_id=user_id, opportunity_id=opportunity_id, **values)
        )
    else:
        for key, value in values.items():
            setattr(row, key, value)


def dismissed_ids(session: Session, user_id: str) -> set[str]:
    """Opportunities the user has actively dismissed. Excluded from results.

    Kept out of the ranking rather than merely sorted down: the user has told
    us they do not want to see this, and showing it again with a slightly lower
    score is not respecting that.
    """
    rows = session.execute(
        select(SavedOpportunity.opportunity_id).where(
            SavedOpportunity.user_id == user_id,
            SavedOpportunity.dismissed_at.isnot(None),
        )
    ).scalars()
    return set(rows)


def saved_ids(session: Session, user_id: str) -> set[str]:
    rows = session.execute(
        select(SavedOpportunity.opportunity_id).where(
            SavedOpportunity.user_id == user_id,
            SavedOpportunity.dismissed_at.is_(None),
        )
    ).scalars()
    return set(rows)
