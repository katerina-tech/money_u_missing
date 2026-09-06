"""Match and actionability result types.

These are *results*, computed in :mod:`app.services.matching` and
:mod:`app.services.actionability` by ordinary Python. The language model is
handed a finished :class:`MatchScore` and may phrase it; it cannot produce one,
cannot alter one, and never sees a code path that would let it. That division is
the reason a score cannot be argued up by an opportunity page that flatters
itself, and it is tested directly in ``tests/test_matching.py``.

Two separate questions get two separate numbers, deliberately:

* :class:`MatchScore` - "does this fit me?"
* :class:`Actionability` - "is this worth acting on now?"

A perfectly-fitting grant that closed yesterday scores high on the first and low
on the second, and collapsing them into one number would hide exactly that.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import ActionabilityBand, RequirementStrength


class ScoreComponent(BaseModel):
    """One weighted dimension of a match, with the reasoning kept legible."""

    model_config = ConfigDict(extra="forbid")

    name: str
    #: 0.0-1.0 before weighting.
    score: float = Field(ge=0.0, le=1.0)
    weight: float = Field(ge=0.0)
    #: Short factual statement of what produced the score, e.g.
    #: "4 of 5 required skills matched". Not model-written.
    detail: str
    #: True when the component had insufficient information and fell back to a
    #: neutral value. Surfaced as an uncertainty rather than hidden in the total.
    was_unknown: bool = False

    @property
    def weighted(self) -> float:
        return self.score * self.weight


class HardFailure(BaseModel):
    """A stated requirement the profile demonstrably does not meet.

    Only ever produced from a requirement whose strength is
    :attr:`~app.domain.enums.RequirementStrength.HARD` *and* a profile field
    that is populated. An unknown on either side yields an
    :class:`Uncertainty` instead - never a rejection.
    """

    model_config = ConfigDict(extra="forbid")

    requirement: str
    strength: RequirementStrength = RequirementStrength.HARD
    profile_value: str | None = None
    explanation: str


class Uncertainty(BaseModel):
    """Something we could not determine, stated plainly on the card."""

    model_config = ConfigDict(extra="forbid")

    topic: str
    explanation: str
    #: What the user could check to resolve it, when there is a concrete answer.
    how_to_resolve: str | None = None


class MatchScore(BaseModel):
    """The deterministic fit assessment for one opportunity and one profile."""

    model_config = ConfigDict(extra="forbid")

    opportunity_id: str
    #: 0-100, rounded. Presented as a percentage in the UI.
    total_score: int = Field(ge=0, le=100)
    components: list[ScoreComponent] = Field(default_factory=list)
    hard_failures: list[HardFailure] = Field(default_factory=list)
    uncertainties: list[Uncertainty] = Field(default_factory=list)
    #: Factual bullet points the explainer may rephrase but not extend. Any
    #: sentence in the UI's "Why this matches" traces back to one of these.
    explanation_inputs: list[str] = Field(default_factory=list)
    #: Version of the weight set used, so a score stored today remains
    #: interpretable after the weights are tuned.
    weights_version: str = "v1"

    @property
    def eligible(self) -> bool:
        """False only on a demonstrated hard failure. Unknown never disqualifies."""
        return not self.hard_failures

    @property
    def has_unknowns(self) -> bool:
        return bool(self.uncertainties) or any(c.was_unknown for c in self.components)


class ActionabilityFactor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    score: float = Field(ge=0.0, le=1.0)
    weight: float = Field(ge=0.0)
    detail: str

    @property
    def weighted(self) -> float:
        return self.score * self.weight


class Actionability(BaseModel):
    """"Is this worth doing now?" - separate from, and never merged with, fit.

    Named a band rather than a euro figure on purpose. Calling this "expected
    net income" would imply a financial calculation the product has not done and
    in most cases could not do, since the majority of listings publish no
    compensation at all.
    """

    model_config = ConfigDict(extra="forbid")

    opportunity_id: str
    score: int = Field(ge=0, le=100)
    band: ActionabilityBand
    factors: list[ActionabilityFactor] = Field(default_factory=list)
    #: The single biggest reason for the band, shown under the badge.
    headline_reason: str = ""
    blockers: list[str] = Field(default_factory=list)


class RankedOpportunity(BaseModel):
    """What discovery returns: an opportunity with both scores attached."""

    model_config = ConfigDict(extra="forbid")

    opportunity_id: str
    match: MatchScore
    actionability: Actionability
    #: Final ordering key. Fit first, actionability as the tie-breaker within a
    #: band - a strong fit the user cannot act on for six weeks should not
    #: outrank a strong fit they can act on today, but neither should a weak fit
    #: win on convenience alone.
    rank_score: float = 0.0


class BestNextMove(BaseModel):
    """Exactly one recommendation. The product's answer to choice overload."""

    model_config = ConfigDict(extra="forbid")

    opportunity_id: str
    title: str
    organization: str | None = None
    #: Why this one, now. Every bullet is drawn from a computed score component
    #: or a stated source fact.
    reasons: list[str] = Field(default_factory=list)
    call_to_action: str = "PREPARE APPLICATION"
    #: Present when the recommendation is weaker than we would like, e.g.
    #: "this is the best available, but only three opportunities were found".
    caveat: str | None = None
