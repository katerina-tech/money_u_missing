"""Turning a confirmed profile into a search plan.

This is the one place where a language model's generative ability is the right
tool. Knowing that a data engineer in Berlin should also be searched for as an
"expert network" candidate, or that a German-speaking statistician is a
plausible fit for a Hochschule's Lehrauftrag listings, is an associative leap
that a keyword system does not make - and it is the difference between showing
someone the jobs they already know about and showing them the money they are
missing.

It is safe because of what the model produces: **queries, never records**.
Everything a query finds still has to exist on a real page, survive fetching,
survive safety and injection screening, and validate against the Opportunity
schema. A hallucinated query finds nothing and costs one search call.

There is a full deterministic fallback. With no model configured, the planner
builds queries from the profile's own skills and role using templates. The
results are narrower - that is the honest cost of no model - but the product
works.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import (
    P0_CATEGORIES,
    IncomeStreamCategory,
    RemoteType,
    SearchIntent,
    Tristate,
)
from app.domain.profile import UserProfile
from app.llm import prompts
from app.llm.base import LLMError, LLMProvider, Purpose
from app.logging_config import Event, log_event
from app.security.guard import InjectionGuard, Provenance
from app.sources.base import SearchPlan, SearchQuery

logger = logging.getLogger(__name__)

MAX_QUERIES = 8


class PlannedQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(max_length=200)
    intent: SearchIntent
    language: str = Field(default="en", max_length=5)


class PlannedSearch(BaseModel):
    """The model's output. Queries and a rationale - nothing that looks like data."""

    model_config = ConfigDict(extra="forbid")

    queries: list[PlannedQuery] = Field(max_length=MAX_QUERIES)
    rationale: str = Field(
        max_length=600,
        description=(
            "One short paragraph the user reads, explaining what is being searched for."
        ),
    )


#: Deterministic templates. ``{skill}`` and ``{role}`` are filled from the
#: profile. Written in both languages because German listings are written in
#: German and an English-only search misses the local market entirely.
_TEMPLATES: tuple[tuple[SearchIntent, str], ...] = (
    (SearchIntent.EXPERT_CALL, "{skill} expert network paid consultation Germany"),
    (SearchIntent.EXPERT_CALL, "Experten Netzwerk {skill} bezahlte Beratung"),
    (SearchIntent.CONSULTING, "{role} freelance consulting project remote Germany"),
    (SearchIntent.FREELANCE, "freiberuflich {skill} Projekt remote"),
    (SearchIntent.TEACHING, "Lehrauftrag {skill} Hochschule Honorar"),
    (SearchIntent.TEACHING, "{skill} workshop trainer paid Germany"),
    (SearchIntent.PAID_PROGRAM, "paid fellowship programme {skill} Europe application"),
    (SearchIntent.GRANT, "Foerderprogramm {skill} Antrag Deutschland"),
    (SearchIntent.COMPETITION, "{skill} competition prize Europe apply"),
    (SearchIntent.PART_TIME, "{role} Teilzeit remote Nebentaetigkeit"),
)


def _profile_summary(profile: UserProfile) -> str:
    """The profile as text, for the planner. Never includes contact details.

    Only what is needed to plan a search: skills, role, seniority, languages,
    location and availability. The display name, portfolio URL and anything
    else identifying is left out - the planner does not need it, and it would
    otherwise travel to a third-party model for no reason.
    """
    professional = profile.professional
    skills = ", ".join(
        s.name for s in professional.skills if s.confirmed or not s.is_inferred
    ) or "not stated"
    languages = (
        ", ".join(f"{lang.code}:{lang.level.value}" for lang in professional.languages)
        or "not stated"
    )
    return "\n".join(
        [
            f"Role: {professional.current_role or 'not stated'}",
            f"Years of experience: {professional.years_experience or 'not stated'}",
            f"Confirmed skills: {skills}",
            f"Industries: {', '.join(professional.industries) or 'not stated'}",
            f"Languages: {languages}",
            f"Location: {profile.general.city or 'not stated'}, "
            f"{profile.general.federal_state or ''} {profile.general.country}",
            f"Work arrangement preference: {profile.time.remote_preference.value}",
            f"Hours available per week: {profile.time.hours_per_week or 'not stated'}",
            f"Work status: {profile.work_status.value}",
        ]
    )


def _goal_summary(profile: UserProfile) -> str:
    income = profile.income
    goal = (
        f"{income.desired_additional_monthly_minor / 100:,.0f} EUR per month"
        if income.desired_additional_monthly_minor
        else "not stated"
    )
    minimum = (
        f"{income.minimum_worthwhile_minor / 100:,.0f} EUR"
        if income.minimum_worthwhile_minor
        else "not stated"
    )
    return "\n".join(
        [
            f"Additional monthly income goal: {goal}",
            f"Minimum amount worth pursuing: {minimum}",
            f"Preference: {income.preference.value}",
        ]
    )


class SearchPlanner:
    def __init__(self, provider: LLMProvider, guard: InjectionGuard) -> None:
        self._provider = provider
        self._guard = guard

    def plan(self, profile: UserProfile, *, max_queries: int = MAX_QUERIES) -> SearchPlan:
        """Build a plan. Falls back to templates when no model is available."""
        constraints = _constraints(profile)

        if not self._provider.available:
            return _deterministic_plan(profile, constraints, max_queries)

        # The profile is the user's own text, so it is screened (normalised and
        # fence-defanged) rather than blocked - see the guard's provenance
        # policy. A CV containing "ignore previous instructions" is a curiosity,
        # not a reason to refuse to help someone find work.
        profile_text = self._guard.screen(_profile_summary(profile), Provenance.USER_TEXT)
        goal_text = self._guard.screen(_goal_summary(profile), Provenance.USER_TEXT)

        try:
            planned = self._provider.structured(
                PlannedSearch,
                prompts.search_plan_messages(profile_text, goal_text),
                purpose=Purpose.SEARCH_PLANNING,
            )
        except LLMError as error:
            log_event(
                logger,
                Event.LLM_ERROR,
                "search planning unavailable; using deterministic templates",
                level=logging.WARNING,
                error_kind=error.kind,
            )
            return _deterministic_plan(profile, constraints, max_queries)

        queries = [
            SearchQuery(
                text=query.text.strip(),
                intent=query.intent,
                region=profile.general.country or "DE",
                language=query.language,
            )
            for query in planned.queries
            if query.text.strip()
        ][:max_queries]

        if not queries:
            return _deterministic_plan(profile, constraints, max_queries)

        plan = SearchPlan(
            queries=queries,
            categories=list(P0_CATEGORIES),
            countries=constraints["countries"],
            languages=constraints["languages"],
            max_hours_per_week=constraints["max_hours"],
            remote_only=constraints["remote_only"],
            rationale=planned.rationale.strip(),
        )
        log_event(
            logger,
            Event.SEARCH_PLAN_BUILT,
            "search plan built",
            query_count=len(plan.queries),
            planner="model",
        )
        return plan


def _constraints(profile: UserProfile) -> dict[str, Any]:
    languages = [lang.code for lang in profile.professional.languages] or ["de", "en"]
    if "en" not in languages:
        languages.append("en")
    return {
        "countries": [profile.general.country or "DE"],
        "languages": languages,
        "max_hours": profile.time.hours_per_week,
        # A *preference* for remote work is scored, not filtered on - see
        # app.services.matching.score_location_fit. This flag means "onsite is
        # not possible for this person", which requires them to have said both
        # that they want remote and that they will not travel.
        "remote_only": (
            profile.time.remote_preference is RemoteType.REMOTE
            and profile.time.willing_to_travel is Tristate.NO
        ),
    }


def _deterministic_plan(
    profile: UserProfile, constraints: dict[str, Any], max_queries: int
) -> SearchPlan:
    """Template-based fallback. Narrower, but honest and free."""
    skills = [
        s.name
        for s in profile.professional.skills
        if s.confirmed or not s.is_inferred
    ][:3] or ["professional"]
    role = profile.professional.current_role or skills[0]

    queries: list[SearchQuery] = []
    for index, (intent, template) in enumerate(_TEMPLATES):
        if len(queries) >= max_queries:
            break
        skill = skills[index % len(skills)]
        queries.append(
            SearchQuery(
                text=template.format(skill=skill, role=role),
                intent=intent,
                region=constraints["countries"][0],
                language=(
                    "de"
                    if any(
                        word in template
                        for word in ("Netzwerk", "frei", "Lehr", "Foerder", "Teilzeit")
                    )
                    else "en"
                ),
            )
        )

    log_event(
        logger,
        Event.SEARCH_PLAN_BUILT,
        "search plan built from templates",
        query_count=len(queries),
        planner="deterministic",
    )
    return SearchPlan(
        queries=queries,
        categories=list(P0_CATEGORIES),
        countries=constraints["countries"],
        languages=constraints["languages"],
        max_hours_per_week=constraints["max_hours"],
        remote_only=constraints["remote_only"],
        rationale=(
            "Built from your confirmed skills and role using standard search patterns. "
            "AI-assisted planning is unavailable, so this search is narrower than usual."
        ),
    )


def categories_for(intent: SearchIntent) -> tuple[IncomeStreamCategory, ...]:
    """Which opportunity categories a search intent is expected to surface."""
    return {
        SearchIntent.FREELANCE: (IncomeStreamCategory.FREELANCE_PROJECT,),
        SearchIntent.CONSULTING: (
            IncomeStreamCategory.CONSULTING,
            IncomeStreamCategory.ADVISORY,
        ),
        SearchIntent.EXPERT_CALL: (
            IncomeStreamCategory.EXPERT_CALL,
            IncomeStreamCategory.PAID_RESEARCH,
        ),
        SearchIntent.TEACHING: (
            IncomeStreamCategory.TEACHING,
            IncomeStreamCategory.WORKSHOP,
            IncomeStreamCategory.MENTORING,
        ),
        SearchIntent.PAID_PROGRAM: (
            IncomeStreamCategory.PAID_PROGRAM,
            IncomeStreamCategory.FELLOWSHIP,
        ),
        SearchIntent.GRANT: (IncomeStreamCategory.GRANT,),
        SearchIntent.COMPETITION: (
            IncomeStreamCategory.COMPETITION,
            IncomeStreamCategory.PRIZE,
        ),
        SearchIntent.PART_TIME: (IncomeStreamCategory.PART_TIME_JOB,),
    }[intent]
