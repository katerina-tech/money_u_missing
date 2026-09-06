"""Provider selection and the usage recorder that persists what they spend."""

from __future__ import annotations

import logging

from app.config import LLMProviderName, Settings, get_settings
from app.llm.anthropic_provider import AnthropicProvider
from app.llm.base import LLMProvider, LLMUnavailableError, Message, Purpose, SchemaT, Usage
from app.llm.openrouter_provider import OpenRouterProvider
from app.llm.testing import ScriptedProvider
from app.logging_config import Event, log_event

logger = logging.getLogger(__name__)


class NullProvider(LLMProvider):
    """Configured absence of a model. Every call raises :class:`LLMUnavailableError`.

    Distinct from :class:`~app.llm.testing.FailingProvider`, which simulates an
    outage: this one is the correct, expected state of a deployment with no key,
    and callers are written to degrade around it rather than treat it as a bug.
    """

    name = "none"

    def structured(
        self,
        schema: type[SchemaT],
        messages: list[Message],
        *,
        purpose: Purpose,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> SchemaT:
        raise LLMUnavailableError()

    def health_check(self) -> bool:
        return False

    @property
    def available(self) -> bool:
        return False


def persist_usage(usage: Usage, user_id: str | None = None) -> None:
    """Write one usage record. Never raises into the calling request.

    Cost accounting must not be able to fail a user's request: if the write
    fails, that is logged and the feature continues.
    """
    from app.db.base import session_scope
    from app.db.models import LlmUsage

    try:
        with session_scope() as session:
            session.add(
                LlmUsage(
                    user_id=user_id,
                    provider=usage.provider,
                    model=usage.model,
                    purpose=usage.purpose.value,
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    total_tokens=usage.total_tokens,
                    latency_ms=usage.latency_ms,
                    estimated_cost_micros=usage.estimated_cost_micros,
                    success=usage.success,
                    error_kind=usage.error_kind,
                )
            )
    except Exception:  # accounting must never break the feature
        logger.warning("could not persist llm usage", exc_info=True)


def build_provider(
    settings: Settings | None = None,
    *,
    user_id: str | None = None,
    persist: bool = True,
) -> LLMProvider:
    """Construct the configured provider, or :class:`NullProvider`.

    Never raises on missing credentials. A deployment with no key is a supported
    configuration, and the capability endpoint reports it so the UI can say what
    is unavailable instead of failing at the first click.
    """
    settings = settings or get_settings()
    recorder = (lambda usage: persist_usage(usage, user_id)) if persist else None

    if not settings.llm_available:
        log_event(
            logger,
            Event.CONFIG_PROBLEM,
            "no language model configured; AI-assisted features will degrade",
            level=logging.INFO,
            provider=settings.llm_provider.value,
        )
        return NullProvider(recorder)

    match settings.llm_provider:
        case LLMProviderName.ANTHROPIC:
            return AnthropicProvider(
                settings.anthropic_api_key.get_secret_value(),
                model=settings.llm_model,
                classifier_model=settings.llm_classifier_model,
                max_tokens=settings.llm_max_tokens,
                timeout_seconds=settings.llm_timeout_seconds,
                max_retries=settings.llm_max_retries,
                recorder=recorder,
            )
        case LLMProviderName.OPENROUTER:
            return OpenRouterProvider(
                settings.openrouter_api_key.get_secret_value(),
                model=settings.llm_model,
                classifier_model=settings.llm_classifier_model,
                max_tokens=settings.llm_max_tokens,
                timeout_seconds=settings.llm_timeout_seconds,
                temperature=settings.llm_temperature,
                recorder=recorder,
            )
        case LLMProviderName.SCRIPTED:
            # Offline demo mode. Responses are supplied by the demo fixtures.
            return ScriptedProvider(recorder=recorder)
        case _:
            return NullProvider(recorder)
