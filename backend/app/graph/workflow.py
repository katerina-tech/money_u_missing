"""The discovery graph.

Built with LangGraph because the discovery path genuinely is a graph with
conditional edges and early exits, and expressing it as one makes the pipeline
inspectable - ``describe()`` renders the exact sequence, which is what the
architecture doc and the demo script both quote.

What it deliberately is *not*: a set of agents delegating to each other. There
is one linear pipeline with two early exits. Multi-agent structure here would
add failure modes and token cost while making the ranking less reproducible,
which is the opposite of what this product needs. See docs/ARCHITECTURE.md.

The graph degrades to a plain function call if LangGraph is unavailable at
runtime, so an import problem in an optional orchestration library cannot take
down the product's core feature.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from app.domain.profile import UserProfile
from app.graph import nodes
from app.graph.state import Deps, DiscoveryState, initial_state

logger = logging.getLogger(__name__)

Node = Callable[[DiscoveryState, Deps], DiscoveryState]

#: The pipeline, in order. Named here rather than only inside the graph builder
#: so the sequence can be documented, tested and run without LangGraph.
PIPELINE: tuple[tuple[str, Node], ...] = (
    ("build_search_plan", nodes.build_search_plan),
    ("search_sources", nodes.search_sources),
    ("normalize", nodes.normalise),
    ("deduplicate", nodes.deduplicate_node),
    ("safety_check", nodes.safety_check),
    ("freshness_check", nodes.freshness_check),
    ("deterministic_match", nodes.deterministic_match),
    ("rank", nodes.rank),
    ("best_next_move", nodes.pick_best_next_move),
)

#: Stages after which an empty result set makes the rest pointless. Exiting
#: early here is not an optimisation - it stops the run reporting "0 matches"
#: when the truth is "no sources returned anything".
EARLY_EXIT_AFTER = frozenset({"search_sources", "normalize", "freshness_check"})


def _is_empty(stage: str, state: DiscoveryState) -> bool:
    if stage == "search_sources":
        return not state.get("candidates")
    return not state.get("opportunities")


def run_pipeline(profile: UserProfile, deps: Deps) -> DiscoveryState:
    """Run discovery directly, without LangGraph. The reference implementation.

    The graph below wraps exactly this. Keeping the plain version as the
    definition means the orchestration library is a convenience rather than a
    dependency of the product's core behaviour.
    """
    state = initial_state(profile)
    for stage, node in PIPELINE:
        try:
            update = node(state, deps)
        except Exception:  # one stage must not lose the whole run
            logger.exception("discovery stage %s failed", stage)
            state["error"] = f"The {stage.replace('_', ' ')} step failed."
            state.setdefault("notices", []).append(
                "Part of the search could not complete, so these results may be incomplete."
            )
            break
        state.update(update)
        if stage in EARLY_EXIT_AFTER and _is_empty(stage, state):
            logger.info("discovery stopped after %s: nothing to carry forward", stage)
            break
    return state


def build_graph() -> object | None:
    """Compile the LangGraph version, or ``None`` if the library is unavailable."""
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError:  # pragma: no cover - depends on install
        logger.info("langgraph unavailable; discovery will run as a direct pipeline")
        return None

    builder = StateGraph(DiscoveryState)
    for stage, node in PIPELINE:
        builder.add_node(stage, _bind(node))  # type: ignore[call-overload]

    builder.add_edge(START, PIPELINE[0][0])
    names = [stage for stage, _ in PIPELINE]
    for index, stage in enumerate(names[:-1]):
        following = names[index + 1]
        if stage in EARLY_EXIT_AFTER:
            builder.add_conditional_edges(
                stage,
                _make_gate(stage, following),
                {following: following, END: END},
            )
        else:
            builder.add_edge(stage, following)
    builder.add_edge(names[-1], END)
    return builder.compile()


def _bind(node: Node) -> Callable[[DiscoveryState], DiscoveryState]:
    """Adapt a ``(state, deps)`` node to LangGraph's single-argument signature.

    Deps arrive through the state's ``extra`` slot rather than a closure so the
    compiled graph is reusable across requests with different sessions.
    """

    def wrapped(state: DiscoveryState) -> DiscoveryState:
        deps = state["extra"]["deps"]
        return node(state, deps)

    return wrapped


def _make_gate(stage: str, following: str) -> Callable[[DiscoveryState], str]:
    from langgraph.graph import END

    def gate(state: DiscoveryState) -> str:
        return END if _is_empty(stage, state) else following

    return gate


def describe() -> list[str]:
    """The pipeline as a list of stage names. Quoted in the architecture doc."""
    return [stage for stage, _ in PIPELINE]
