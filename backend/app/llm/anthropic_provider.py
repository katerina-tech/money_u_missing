"""Anthropic Messages API provider.

Uses ``client.beta.messages.parse`` with ``output_format`` set to the caller's
Pydantic model, so schema conformance is enforced by the API rather than by
parsing JSON out of prose and hoping. The SDK returns a validated instance;
anything that does not conform never reaches the caller.

Three choices worth stating:

* **Effort is set per purpose, not globally.** Reading a CV into a schema and
  deciding whether a sentence is a prompt injection are not equally hard, and
  the default of ``high`` on every call is how an MVP's unit economics quietly
  become indefensible. The map below is measured against the eval set in
  ``backend/evals``, and is a configuration decision, not a quality ceiling.
* **Server-side fallbacks are on by default.** Opus 5 can return
  ``stop_reason: "refusal"``, and this product routinely sends it text that
  looks adversarial - because some of it *is*, arriving from third-party pages.
  A refused turn should degrade to another model rather than to an error page.
* **Usage is recorded on failure too.** A provider that only bills the happy
  path makes retries and timeouts invisible in cost reporting, which is exactly
  where surprise spend hides.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import anthropic

from app.llm.base import (
    LLMError,
    LLMProvider,
    Message,
    Purpose,
    Role,
    SchemaT,
    Usage,
    UsageRecorder,
)
from app.logging_config import Event, log_event

logger = logging.getLogger(__name__)

#: Reasoning effort per purpose. Extraction and planning are the value path and
#: get a real budget; classification is a narrow judgement on short text.
EFFORT_BY_PURPOSE: dict[Purpose, str] = {
    Purpose.CV_EXTRACTION: "medium",
    Purpose.SKILL_INFERENCE: "low",
    Purpose.SEARCH_PLANNING: "medium",
    Purpose.OPPORTUNITY_EXTRACTION: "medium",
    Purpose.MATCH_EXPLANATION: "low",
    Purpose.APPLICATION_DRAFT: "medium",
    Purpose.TAX_ANSWER: "high",
    Purpose.INJECTION_CLASSIFIER: "low",
    Purpose.INTENT_CLASSIFIER: "low",
}

#: USD per million tokens, as published for the models this product uses. Used
#: only for models present here - an absent model yields a NULL cost rather than
#: an extrapolated one, because a made-up cost figure in a unit-economics table
#: is worse than an empty cell.
PRICING_USD_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
}

_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(
        self,
        api_key: str,
        *,
        model: str,
        classifier_model: str,
        max_tokens: int = 2048,
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        recorder: UsageRecorder | None = None,
        enable_fallbacks: bool = True,
    ) -> None:
        super().__init__(recorder)
        self._client = anthropic.Anthropic(
            api_key=api_key,
            timeout=timeout_seconds,
            # The SDK's own backoff handles 429/5xx/connection errors. Adding a
            # second retry loop on top would multiply the worst-case latency
            # without improving the outcome.
            max_retries=max_retries,
        )
        self._model = model
        self._classifier_model = classifier_model
        self._max_tokens = max_tokens
        self._enable_fallbacks = enable_fallbacks

    # ------------------------------------------------------------- public
    def structured(
        self,
        schema: type[SchemaT],
        messages: list[Message],
        *,
        purpose: Purpose,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> SchemaT:
        chosen_model = model or self._model_for(purpose)
        system, turns = _split_system(messages)
        started = time.perf_counter()

        request: dict[str, Any] = {
            "model": chosen_model,
            "max_tokens": max_tokens or self._max_tokens,
            "system": system,
            "messages": turns,
            "output_format": schema,
            "output_config": {"effort": EFFORT_BY_PURPOSE.get(purpose, "medium")},
            # Adaptive is the only supported on-mode on current models, and it
            # is what makes lower effort settings safe to use here.
            "thinking": {"type": "adaptive"},
        }
        if self._enable_fallbacks:
            request["betas"] = [_FALLBACK_BETA]
            request["fallbacks"] = "default"

        try:
            response = self._client.beta.messages.parse(**request)
        except anthropic.APIStatusError as error:
            raise self._record_and_wrap(error, chosen_model, purpose, started) from error
        except anthropic.APIConnectionError as error:
            raise self._record_and_wrap(error, chosen_model, purpose, started) from error

        latency_ms = int((time.perf_counter() - started) * 1000)

        # A refusal is HTTP 200. Checking stop_reason before touching content is
        # not optional: the content list may be empty or partial.
        if response.stop_reason == "refusal":
            self._record_usage(
                response, chosen_model, purpose, latency_ms, success=False, error_kind="refusal"
            )
            raise LLMError(
                "The model declined to process this content.",
                kind="refusal",
                content_filtered=True,
                retryable=False,
            ) from None

        parsed = getattr(response, "parsed_output", None)
        if parsed is None or not isinstance(parsed, schema):
            self._record_usage(
                response,
                chosen_model,
                purpose,
                latency_ms,
                success=False,
                error_kind="schema_mismatch",
            )
            raise LLMError(
                f"Response did not conform to {schema.__name__}.",
                kind="schema_mismatch",
                retryable=True,
            )

        self._record_usage(response, chosen_model, purpose, latency_ms, success=True)
        return parsed

    def health_check(self) -> bool:
        """Cheap liveness probe. Never raises - callers use it to pick a message."""
        try:
            self._client.models.retrieve(self._classifier_model)
        except Exception:  # any failure means "not usable right now"
            return False
        return True

    # ------------------------------------------------------------ internal
    def _model_for(self, purpose: Purpose) -> str:
        if purpose in {Purpose.INJECTION_CLASSIFIER, Purpose.INTENT_CLASSIFIER}:
            return self._classifier_model
        return self._model

    def _record_and_wrap(
        self, error: Exception, model: str, purpose: Purpose, started: float
    ) -> LLMError:
        latency_ms = int((time.perf_counter() - started) * 1000)
        kind = type(error).__name__
        retryable = False
        content_filtered = False

        if isinstance(error, anthropic.RateLimitError):
            kind, retryable = "rate_limited", True
        elif isinstance(error, anthropic.APIConnectionError):
            kind, retryable = "connection", True
        elif isinstance(error, anthropic.APIStatusError):
            if error.status_code >= 500:
                kind, retryable = "server_error", True
            elif error.status_code == 400:
                # The API rejects some content on policy grounds with a 400.
                # That is information about the text, so it is surfaced as a
                # content filter rather than a generic bad request - the
                # injection guard folds it into its evidence.
                body = str(getattr(error, "message", "")).lower()
                content_filtered = "content" in body and (
                    "policy" in body or "filter" in body or "blocked" in body
                )
                kind = "content_filtered" if content_filtered else "bad_request"
            else:
                kind = f"http_{error.status_code}"

        self._record(
            Usage(
                provider=self.name,
                model=model,
                purpose=purpose,
                latency_ms=latency_ms,
                success=False,
                error_kind=kind,
            )
        )
        log_event(
            logger,
            Event.LLM_ERROR,
            "model call failed",
            level=logging.WARNING,
            provider=self.name,
            model=model,
            purpose=purpose.value,
            error_kind=kind,
            retryable=retryable,
        )
        return LLMError(
            str(error), kind=kind, content_filtered=content_filtered, retryable=retryable
        )

    def _record_usage(
        self,
        response: Any,
        model: str,
        purpose: Purpose,
        latency_ms: int,
        *,
        success: bool,
        error_kind: str | None = None,
    ) -> None:
        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "input_tokens", None)
        output_tokens = getattr(usage, "output_tokens", None)
        total = None
        if input_tokens is not None and output_tokens is not None:
            total = input_tokens + output_tokens

        self._record(
            Usage(
                provider=self.name,
                model=model,
                purpose=purpose,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total,
                latency_ms=latency_ms,
                success=success,
                error_kind=error_kind,
                estimated_cost_micros=estimate_cost_micros(model, input_tokens, output_tokens),
            )
        )
        log_event(
            logger,
            Event.LLM_CALL,
            "model call completed",
            provider=self.name,
            model=model,
            purpose=purpose.value,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            success=success,
        )


def estimate_cost_micros(
    model: str, input_tokens: int | None, output_tokens: int | None
) -> int | None:
    """Cost in USD micros, or ``None`` when the model has no published price here.

    Returning ``None`` rather than zero matters: a zero would sum silently into
    a cost dashboard and make an unpriced model look free.
    """
    price = PRICING_USD_PER_MTOK.get(model)
    if price is None or input_tokens is None or output_tokens is None:
        return None
    input_price, output_price = price
    usd = (input_tokens * input_price + output_tokens * output_price) / 1_000_000
    return round(usd * 1_000_000)


def _split_system(messages: list[Message]) -> tuple[str, list[dict[str, str]]]:
    """Separate system instructions from the conversation.

    System content is authored only in :mod:`app.llm.prompts`; this function
    exists so a caller physically cannot promote user or retrieved text into the
    system channel by constructing a message with the wrong role - anything not
    authored as SYSTEM stays in the user turn where the fence applies.
    """
    system_parts = [m.content for m in messages if m.role is Role.SYSTEM]
    turns = [
        {"role": m.role.value, "content": m.content}
        for m in messages
        if m.role is not Role.SYSTEM
    ]
    if not turns:
        raise LLMError("At least one user message is required.", kind="bad_request")
    return "\n\n".join(system_parts), turns
