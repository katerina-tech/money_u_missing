"""Discovery graph nodes.

Each node is a pure-ish function of ``(state, deps)`` returning a partial state
update. The graph is a genuine pipeline rather than a set of agents talking to
each other: exactly one node calls a model for planning, one calls it for
extraction, one for explanation, and the four that decide anything - safety,
eligibility, matching, actionability - contain no model call at all.

That division is the architecture, not a detail. It is what makes the same
inputs produce the same ranking twice, and what lets the product tell a user
precisely why an opportunity scored what it scored.
"""

from __future__ import annotations

import logging

from app.domain.enums import SafetyVerdict
from app.domain.matching import BestNextMove, RankedOpportunity
from app.graph.state import Deps, DiscoveryState
from app.logging_config import Event, log_event
from app.services import actionability as actionability_service
from app.services import matching as matching_service
from app.services.dedupe import deduplicate
from app.services.learning import load_preferences
from app.services.normalize import Normaliser, is_fresh
from app.services.search_planner import SearchPlanner

logger = logging.getLogger(__name__)

#: Opportunities returned to the UI in one run. Beyond this the list stops
#: being a map and becomes another job board - which is the thing the product
#: exists not to be.
MAX_RESULTS = 25


def build_search_plan(state: DiscoveryState, deps: Deps) -> DiscoveryState:
    planner = SearchPlanner(deps.provider, deps.guard)
    plan = planner.plan(state["profile"])
    return DiscoveryState(plan=plan)


def search_sources(state: DiscoveryState, deps: Deps) -> DiscoveryState:
    """Query every registered source. One failure never ends the run."""
    plan = state["plan"]
    sources = deps.registry.build()
    candidates = []
    failed: list[str] = []
    live_used = False

    for source in sources:
        result = source.search(plan)
        if not result.ok:
            failed.append(f"{source.name}: {result.error}")
            continue
        candidates.extend(result.candidates)
        if source.source_type.value in {"SEARCH_API", "RSS", "PUBLIC_API"}:
            live_used = True

    notices: list[str] = []
    if failed:
        notices.append(
            "Live opportunity search is partly unavailable. Showing verified cached "
            "and curated opportunities."
        )
    if not live_used:
        notices.append(
            "Live web search is not configured, so these results come from our curated "
            "and demo datasets only."
        )

    return DiscoveryState(
        candidates=candidates,
        sources_queried=len(sources),
        sources_failed=failed,
        live_search_used=live_used,
        notices=notices,
    )


def normalise(state: DiscoveryState, deps: Deps) -> DiscoveryState:
    normaliser = Normaliser(deps.provider, deps.guard)
    report = normaliser.normalise(state["candidates"])
    return DiscoveryState(
        opportunities=report.opportunities,
        considered=report.considered,
        blocked_unsafe=report.blocked_unsafe,
        blocked_injection=report.blocked_injection,
        extraction_failures=report.extraction_failures,
        rejected=report.rejected,
    )


def deduplicate_node(state: DiscoveryState, deps: Deps) -> DiscoveryState:
    report = deduplicate(state["opportunities"])
    log_event(
        logger,
        Event.OPPORTUNITIES_DEDUPED,
        "de-duplication complete",
        kept=len(report.kept),
        removed=report.removed_count,
    )
    return DiscoveryState(opportunities=report.kept, duplicates_removed=report.removed_count)


def safety_check(state: DiscoveryState, deps: Deps) -> DiscoveryState:
    """Final safety gate. Normalisation already screened; this catches merges.

    De-duplication merges fields between records, so a listing can acquire text
    it did not have when it was first classified. Re-checking after the merge is
    cheap and closes that gap.
    """
    from app.services.safety import DEFAULT_CLASSIFIER

    kept = []
    blocked = state.get("blocked_unsafe", 0)
    rejected = list(state.get("rejected", []))
    for opportunity in state["opportunities"]:
        assessment = DEFAULT_CLASSIFIER.classify(opportunity)
        if assessment.verdict is SafetyVerdict.BLOCKED:
            blocked += 1
            rejected.append((opportunity.title[:80], assessment.reasons[0]))
            continue
        kept.append(opportunity.model_copy(update={"safety": assessment}))
    return DiscoveryState(opportunities=kept, blocked_unsafe=blocked, rejected=rejected)


def freshness_check(state: DiscoveryState, deps: Deps) -> DiscoveryState:
    fresh = [o for o in state["opportunities"] if is_fresh(o)]
    removed = len(state["opportunities"]) - len(fresh)
    notices = list(state.get("notices", []))
    if removed:
        notices.append(
            f"{removed} opportunit{'y' if removed == 1 else 'ies'} were excluded because "
            "their deadline has passed or we have not seen them recently."
        )
    return DiscoveryState(opportunities=fresh, stale_removed=removed, notices=notices)


def deterministic_match(state: DiscoveryState, deps: Deps) -> DiscoveryState:
    """Score every opportunity. No model is reachable from here."""
    profile = state["profile"]
    adjustment = load_preferences(deps.session, profile.user_id)
    ranked: list[RankedOpportunity] = []

    for opportunity in state["opportunities"]:
        match = matching_service.score(profile, opportunity, adjustment=adjustment)
        action = actionability_service.assess(profile, opportunity, match)
        ranked.append(
            RankedOpportunity(
                opportunity_id=opportunity.id,
                match=match,
                actionability=action,
                rank_score=_rank_score(match.total_score, action.score),
            )
        )

    log_event(
        logger,
        Event.MATCHING_COMPLETED,
        "matching complete",
        scored=len(ranked),
        eligible=sum(1 for r in ranked if r.match.eligible),
    )
    return DiscoveryState(ranked=ranked)


def _rank_score(match: int, actionability: int) -> float:
    """Fit first, actionability as the tie-breaker.

    The 0.7/0.3 split is deliberate. Actionability alone would put a trivially
    easy but irrelevant application at the top; fit alone would recommend a
    perfect grant that closes tomorrow to someone with two free hours this week.
    Fit dominates because a recommendation the user cannot do is worthless, but
    a recommendation they will never get round to is nearly as bad.
    """
    return round(match * 0.7 + actionability * 0.3, 3)


def rank(state: DiscoveryState, deps: Deps) -> DiscoveryState:
    """Order results. Ineligible ones sink but are not hidden.

    Hiding a hard failure would leave the user wondering why an opportunity
    they saw last week vanished. It is shown, last, with the failure stated.
    """
    ranked = sorted(
        state["ranked"],
        key=lambda r: (r.match.eligible, r.rank_score),
        reverse=True,
    )
    by_id = {o.id: o for o in state["opportunities"]}
    trimmed = ranked[:MAX_RESULTS]
    return DiscoveryState(
        ranked=trimmed,
        opportunities=[by_id[r.opportunity_id] for r in trimmed if r.opportunity_id in by_id],
    )


def pick_best_next_move(state: DiscoveryState, deps: Deps) -> DiscoveryState:
    """Exactly one recommendation, with the reason it is this one.

    The product's answer to choice overload. A list of twenty-five is a
    research task; one concrete action with a stated rationale is a decision the
    user can make in ten seconds.
    """
    eligible = [r for r in state["ranked"] if r.match.eligible]
    if not eligible:
        return DiscoveryState(best_next_move=None)

    by_id = {o.id: o for o in state["opportunities"]}
    # Among the strong fits, prefer the one that is most actionable now. This is
    # the one place actionability outranks fit, because the user has already
    # decided to act - the question is only on what.
    threshold = max(50, eligible[0].match.total_score - 12)
    top_band = [r for r in eligible if r.match.total_score >= threshold]
    choice = max(top_band or eligible, key=lambda r: r.actionability.score)
    opportunity = by_id.get(choice.opportunity_id)
    if opportunity is None:
        return DiscoveryState(best_next_move=None)

    reasons = [
        line[2:] for line in choice.match.explanation_inputs if line.startswith("+ ")
    ][:3]
    reasons.append(choice.actionability.headline_reason)

    caveat: str | None = None
    if len(state["ranked"]) < 4:
        caveat = (
            f"This is the best of only {len(state['ranked'])} opportunit"
            f"{'y' if len(state['ranked']) == 1 else 'ies'} we found for you. "
            "Completing your profile usually widens the search."
        )
    elif opportunity.is_demo:
        caveat = "This is a demo opportunity, shown to illustrate the product."

    return DiscoveryState(
        best_next_move=BestNextMove(
            opportunity_id=opportunity.id,
            title=opportunity.title,
            organization=opportunity.organization,
            reasons=[r for r in reasons if r],
            call_to_action="PREPARE APPLICATION",
            caveat=caveat,
        )
    )
