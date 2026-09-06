"""The provider contract.

Deliberately narrow. There is exactly one method that reaches a model, and it
takes a Pydantic schema and returns a validated instance of it. There is no
``complete(prompt) -> str`` anywhere in this codebase, and that absence is a
security control rather than a style preference: a successful prompt injection
can at most produce a differently-populated instance of a closed schema, never
free text that some caller goes on to trust, and never a field the system acts
on that the schema did not declare.

Every implementation must satisfy the same three properties, which
``tests/test_llm_providers.py`` checks against all of them including the fakes:

* a failure raises :class:`LLMError` and never returns a partial object;
* usage is reported through :class:`UsageRecorder` whether the call succeeded or
  not, so cost accounting is not biased towards happy paths;
* nothing user-authored is ever placed in a system message.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, TypeVar

from pydantic import BaseModel

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class Purpose(StrEnum):
    """Why a call was made. Recorded per call so unit economics are per-feature.

    Cost-per-user is not actionable; cost-per-Money-Map is.
    """

    CV_EXTRACTION = "cv_extraction"
    SKILL_INFERENCE = "skill_inference"
    SEARCH_PLANNING = "search_planning"
    OPPORTUNITY_EXTRACTION = "opportunity_extraction"
    MATCH_EXPLANATION = "match_explanation"
    APPLICATION_DRAFT = "application_draft"
    TAX_ANSWER = "tax_answer"
    INJECTION_CLASSIFIER = "injection_classifier"
    INTENT_CLASSIFIER = "intent_classifier"


class Role(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class Message:
    role: Role
    content: str


class LLMError(RuntimeError):
    """Any failure to obtain a valid structured response.

    ``content_filtered`` is separated out because a provider declining to
    process text on its own content policy is *evidence about the text*, which
    the injection guard folds into its score, rather than an outage.
    """

    def __init__(
        self,
        message: str,
        *,
        kind: str = "unknown",
        content_filtered: bool = False,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.content_filtered = content_filtered
        self.retryable = retryable


class LLMUnavailableError(LLMError):
    """No provider is configured, or its credentials are absent.

    A distinct type so routes can answer "we could not analyse this right now,
    your saved data is safe" rather than a 500.
    """

    def __init__(self, message: str = "No language model provider is configured.") -> None:
        super().__init__(message, kind="unavailable", retryable=False)


@dataclass
class Usage:
    """What one call consumed. ``None`` where the provider did not report it."""

    provider: str
    model: str
    purpose: Purpose
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    latency_ms: int | None = None
    success: bool = True
    error_kind: str | None = None
    #: Only set when a deterministic price list covers the model. Left None
    #: otherwise - an invented cost figure is worse than no cost figure.
    estimated_cost_micros: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


#: Called once per model call. Wired to the ``llm_usage`` table in production
#: and to a list in tests.
UsageRecorder = Callable[[Usage], None]


def _noop_recorder(_usage: Usage) -> None:
    return None


class LLMProvider(ABC):
    """One method that reaches a model, and it always returns a validated object."""

    name: str = "abstract"

    def __init__(self, recorder: UsageRecorder | None = None) -> None:
        self._record = recorder or _noop_recorder

    @abstractmethod
    def structured(
        self,
        schema: type[SchemaT],
        messages: list[Message],
        *,
        purpose: Purpose,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> SchemaT:
        """Return a validated ``schema`` instance, or raise :class:`LLMError`."""

    @abstractmethod
    def health_check(self) -> bool:
        """Whether a call would plausibly succeed. Must not raise."""

    @property
    def available(self) -> bool:
        return True
