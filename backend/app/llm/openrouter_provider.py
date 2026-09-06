"""OpenRouter provider - a second implementation, to keep the abstraction honest.

An abstraction with one implementation is an assumption wearing a costume. This
one exists so the contract in :mod:`app.llm.base` is genuinely provider-neutral,
and so the product is not a single vendor outage away from having no AI at all.

It speaks the OpenAI-compatible Chat Completions shape over plain ``httpx``
rather than pulling in a second SDK, because the surface actually used here is
one POST with a JSON-schema response format.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

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

_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterProvider(LLMProvider):
    name = "openrouter"

    def __init__(
        self,
        api_key: str,
        *,
        model: str,
        classifier_model: str,
        max_tokens: int = 2048,
        timeout_seconds: float = 60.0,
        temperature: float = 0.0,
        recorder: UsageRecorder | None = None,
    ) -> None:
        super().__init__(recorder)
        self._client = httpx.Client(
            base_url=_BASE_URL,
            timeout=timeout_seconds,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                # OpenRouter attributes traffic from these; they are not secrets.
                "HTTP-Referer": "https://github.com/katerina-tech/money_u_missing",
                "X-Title": "Money You're Missing",
            },
        )
        self._model = model
        self._classifier_model = classifier_model
        self._max_tokens = max_tokens
        self._temperature = temperature

    def structured(
        self,
        schema: type[SchemaT],
        messages: list[Message],
        *,
        purpose: Purpose,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> SchemaT:
        chosen = model or (
            self._classifier_model
            if purpose in {Purpose.INJECTION_CLASSIFIER, Purpose.INTENT_CLASSIFIER}
            else self._model
        )
        payload = {
            "model": chosen,
            "max_tokens": max_tokens or self._max_tokens,
            "temperature": self._temperature,
            "messages": [{"role": m.role.value, "content": m.content} for m in messages],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__,
                    "strict": True,
                    "schema": _strict_schema(schema),
                },
            },
        }
        started = time.perf_counter()
        try:
            response = self._client.post("/chat/completions", json=payload)
            response.raise_for_status()
            body = response.json()
        except httpx.HTTPStatusError as error:
            raise self._fail(error, chosen, purpose, started, error.response.status_code) from error
        except httpx.HTTPError as error:
            raise self._fail(error, chosen, purpose, started, None) from error

        latency_ms = int((time.perf_counter() - started) * 1000)
        usage = body.get("usage") or {}
        try:
            content = body["choices"][0]["message"]["content"]
            parsed = schema.model_validate(json.loads(content))
        except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValueError) as error:
            self._emit(chosen, purpose, usage, latency_ms, False, "schema_mismatch")
            raise LLMError(
                f"Response did not conform to {schema.__name__}.",
                kind="schema_mismatch",
                retryable=True,
            ) from error

        self._emit(chosen, purpose, usage, latency_ms, True, None)
        return parsed

    def health_check(self) -> bool:
        try:
            response = self._client.get("/models", timeout=10.0)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    # ------------------------------------------------------------ internal
    def _fail(
        self, error: Exception, model: str, purpose: Purpose, started: float, status: int | None
    ) -> LLMError:
        latency_ms = int((time.perf_counter() - started) * 1000)
        if status == 429:
            kind, retryable = "rate_limited", True
        elif status is not None and status >= 500:
            kind, retryable = "server_error", True
        elif status is None:
            kind, retryable = "connection", True
        else:
            kind, retryable = f"http_{status}", False
        self._emit(model, purpose, {}, latency_ms, False, kind)
        log_event(
            logger,
            Event.LLM_ERROR,
            "model call failed",
            level=logging.WARNING,
            provider=self.name,
            model=model,
            purpose=purpose.value,
            error_kind=kind,
        )
        return LLMError(str(error), kind=kind, retryable=retryable)

    def _emit(
        self,
        model: str,
        purpose: Purpose,
        usage: dict[str, Any],
        latency_ms: int,
        success: bool,
        error_kind: str | None,
    ) -> None:
        self._record(
            Usage(
                provider=self.name,
                model=model,
                purpose=purpose,
                input_tokens=usage.get("prompt_tokens"),
                output_tokens=usage.get("completion_tokens"),
                total_tokens=usage.get("total_tokens"),
                latency_ms=latency_ms,
                success=success,
                error_kind=error_kind,
                # OpenRouter prices vary per upstream model and change without
                # notice, so no cost is estimated here rather than a wrong one.
                estimated_cost_micros=None,
            )
        )


def _strict_schema(schema: type[SchemaT]) -> dict[str, Any]:
    """Pydantic JSON schema, adjusted for strict structured-output validators.

    Two adjustments are required by every strict implementation and are not what
    Pydantic emits by default: ``additionalProperties: false`` on every object,
    and every property listed in ``required`` (optionality is expressed by a
    nullable type, not by absence).
    """
    raw = schema.model_json_schema()
    _tighten(raw)
    for definition in (raw.get("$defs") or {}).values():
        _tighten(definition)
    return raw


def _tighten(node: dict[str, Any]) -> None:
    if node.get("type") == "object" or "properties" in node:
        node["additionalProperties"] = False
        properties = node.get("properties") or {}
        node["required"] = sorted(properties)
        for child in properties.values():
            if isinstance(child, dict):
                _tighten(child)
    items = node.get("items")
    if isinstance(items, dict):
        _tighten(items)
    for key in ("anyOf", "oneOf", "allOf"):
        for child in node.get(key) or []:
            if isinstance(child, dict):
                _tighten(child)


def system_role_supported() -> Role:
    """OpenRouter accepts a system role in the messages array, unlike some models."""
    return Role.SYSTEM
