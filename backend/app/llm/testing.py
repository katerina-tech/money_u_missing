"""Deterministic providers for tests, evals and the offline demo.

The entire test suite and the whole evaluation harness run against these. No
test in this repository makes a paid model call, which is what makes it
reasonable to run them on every commit and to hand the repo to someone who has
no API key.

:class:`ScriptedProvider` is also what powers ``MYM_LLM_PROVIDER=scripted``: the
accelerator demo can be shown end to end, offline, with no credentials, and the
UI still marks everything it produces as demo output.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, cast

from pydantic import BaseModel

from app.llm.base import (
    LLMError,
    LLMProvider,
    Message,
    Purpose,
    SchemaT,
    Usage,
    UsageRecorder,
)

#: A canned answer: either a ready instance, a factory taking the messages, or
#: an exception to raise.
Response = BaseModel | Callable[[list[Message]], BaseModel] | Exception


class ScriptedProvider(LLMProvider):
    """Returns pre-agreed answers, keyed by purpose.

    Records every call, so a test can assert not only on the result but on
    *what was sent* - which is how the prompt-injection tests verify that
    untrusted text was fenced and never reached a system message.
    """

    name = "scripted"

    def __init__(
        self,
        responses: dict[Purpose, Response | Sequence[Response]] | None = None,
        *,
        default: Response | None = None,
        recorder: UsageRecorder | None = None,
    ) -> None:
        super().__init__(recorder)
        self._responses: dict[Purpose, list[Response]] = {}
        for purpose, value in (responses or {}).items():
            # A bare BaseModel/Exception is one response; a list or tuple is a
            # queue. Strings are not a valid response, so Sequence is safe here.
            if isinstance(value, list | tuple):
                self._responses[purpose] = list(value)
            else:
                self._responses[purpose] = [cast(Response, value)]
        self._default = default
        self.calls: list[dict[str, Any]] = []

    def structured(
        self,
        schema: type[SchemaT],
        messages: list[Message],
        *,
        purpose: Purpose,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> SchemaT:
        self.calls.append(
            {
                "purpose": purpose,
                "schema": schema.__name__,
                "messages": messages,
                "system": "\n".join(m.content for m in messages if m.role.value == "system"),
                "user": "\n".join(m.content for m in messages if m.role.value == "user"),
            }
        )
        self._record(
            Usage(
                provider=self.name,
                model=model or "scripted",
                purpose=purpose,
                input_tokens=sum(len(m.content) // 4 for m in messages),
                output_tokens=0,
                latency_ms=0,
                success=True,
            )
        )

        queue = self._responses.get(purpose)
        # A queue of one is sticky - repeated calls keep returning it. Longer
        # queues are consumed in order, so a test can script a retry sequence.
        response: Response | None = (
            (queue.pop(0) if len(queue) > 1 else queue[0]) if queue else self._default
        )

        if response is None:
            raise LLMError(
                f"ScriptedProvider has no response for {purpose.value}.", kind="unscripted"
            )
        if isinstance(response, Exception):
            raise response
        if callable(response) and not isinstance(response, BaseModel):
            response = response(messages)
        if not isinstance(response, schema):
            raise LLMError(
                f"Scripted response is {type(response).__name__}, expected {schema.__name__}.",
                kind="schema_mismatch",
            )
        return response

    def health_check(self) -> bool:
        return True

    # ------------------------------------------------------- test helpers
    def last_call(self, purpose: Purpose | None = None) -> dict[str, Any]:
        for call in reversed(self.calls):
            if purpose is None or call["purpose"] is purpose:
                return call
        raise AssertionError(f"no call recorded for {purpose}")

    def system_text(self, purpose: Purpose | None = None) -> str:
        return str(self.last_call(purpose)["system"])


class FailingProvider(LLMProvider):
    """Always raises. Used to prove every feature degrades rather than breaks.

    Each service that consults a model has a test asserting that with this
    provider installed, the request still returns something honest: cached
    opportunities, a profile the user can fill in by hand, or a refusal to
    answer a tax question. Nothing fakes success.
    """

    name = "failing"

    def __init__(
        self,
        error: LLMError | None = None,
        *,
        recorder: UsageRecorder | None = None,
    ) -> None:
        super().__init__(recorder)
        self._error = error or LLMError(
            "Simulated provider outage.", kind="server_error", retryable=True
        )
        self.call_count = 0

    def structured(
        self,
        schema: type[SchemaT],
        messages: list[Message],
        *,
        purpose: Purpose,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> SchemaT:
        self.call_count += 1
        self._record(
            Usage(
                provider=self.name,
                model=model or "failing",
                purpose=purpose,
                success=False,
                error_kind=self._error.kind,
            )
        )
        raise self._error

    def health_check(self) -> bool:
        return False

    @property
    def available(self) -> bool:
        return False


class RecordingRecorder:
    """Collects :class:`Usage` in memory. Passed to providers under test."""

    def __init__(self) -> None:
        self.records: list[Usage] = []

    def __call__(self, usage: Usage) -> None:
        self.records.append(usage)

    @property
    def failures(self) -> list[Usage]:
        return [u for u in self.records if not u.success]
