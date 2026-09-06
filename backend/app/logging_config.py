"""The single logging configuration for the backend.

Every module gets its logger with ``logging.getLogger(__name__)``. Structured
events go through :func:`log_event` so event names are a closed enum rather than
free-form strings scattered across the codebase.

Redaction policy, which matters more here than in most products because the
inputs are CVs and personal tax questions:

* CV text, profile free text and legal questions are NEVER logged in full.
  :func:`redact_text` reduces them to a length, a truncated hash and nothing
  else - not even a preview, unlike a generic implementation, because the first
  200 characters of a CV are exactly the identifying ones.
* User ids appear only as a salted, truncated hash, so logs can be correlated
  per user without being personal data on their own.
* Secrets are ``SecretStr`` in :class:`~app.config.Settings` and so cannot be
  stringified into a record by accident.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
from enum import StrEnum
from typing import Any

RESERVED = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


class Event(StrEnum):
    """Closed set of structured log events. See docs/ARCHITECTURE.md."""

    API_STARTED = "api_started"
    CONFIG_PROBLEM = "config_problem"

    # --- identity
    SIGNUP_COMPLETED = "signup_completed"
    LOGIN_SUCCEEDED = "login_succeeded"
    LOGIN_FAILED = "login_failed"
    TOKEN_REFRESHED = "token_refreshed"
    ACCOUNT_DELETED = "account_deleted"

    # --- profile
    CV_UPLOAD_ACCEPTED = "cv_upload_accepted"
    CV_UPLOAD_REJECTED = "cv_upload_rejected"
    CV_EXTRACTION_STARTED = "cv_extraction_started"
    CV_EXTRACTION_COMPLETED = "cv_extraction_completed"
    CV_DELETED = "cv_deleted"
    PROFILE_CONFIRMED = "profile_confirmed"

    # --- discovery
    SEARCH_PLAN_BUILT = "search_plan_built"
    SOURCE_QUERIED = "source_queried"
    SOURCE_FAILED = "source_failed"
    OPPORTUNITIES_NORMALISED = "opportunities_normalised"
    OPPORTUNITIES_DEDUPED = "opportunities_deduped"
    OPPORTUNITY_REJECTED_UNSAFE = "opportunity_rejected_unsafe"
    MATCHING_COMPLETED = "matching_completed"
    MONEY_MAP_BUILT = "money_map_built"

    # --- action
    OPPORTUNITY_SAVED = "opportunity_saved"
    OPPORTUNITY_DISMISSED = "opportunity_dismissed"
    APPLICATION_TRANSITIONED = "application_transitioned"
    INCOME_RECORDED = "income_recorded"

    # --- keep / grow
    TAX_QUESTION_ASKED = "tax_question_asked"
    TAX_ANSWER_REFUSED = "tax_answer_refused"
    LEGAL_FACT_STALE = "legal_fact_stale"
    GOAL_CREATED = "goal_created"

    # --- infrastructure
    LLM_CALL = "llm_call"
    LLM_ERROR = "llm_error"
    SEARCH_ERROR = "search_error"
    FETCH_BLOCKED = "fetch_blocked"
    INJECTION_SUSPECTED = "injection_suspected"
    RATE_LIMITED = "rate_limited"
    VALIDATION_ERROR = "validation_error"
    UNHANDLED_ERROR = "unhandled_error"


class JsonFormatter(logging.Formatter):
    """One JSON object per line, including any ``extra`` fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in RESERVED:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


class ConsoleFormatter(logging.Formatter):
    """Human-readable format for local development."""

    def format(self, record: logging.LogRecord) -> str:
        extras = " ".join(
            f"{k}={v}" for k, v in record.__dict__.items() if k not in RESERVED and k != "event"
        )
        event = getattr(record, "event", "-")
        stamp = self.formatTime(record, "%H:%M:%S")
        base = f"{stamp} {record.levelname:<7} [{event}] {record.getMessage()}"
        return f"{base}  {extras}".rstrip()


def configure_logging(level: str = "INFO", fmt: str = "json") -> None:
    """Install the single root handler. Idempotent - safe to call twice."""
    formatter: logging.Formatter = JsonFormatter() if fmt == "json" else ConsoleFormatter()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level.upper())

    for noisy in ("httpx", "httpcore", "urllib3", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def log_event(
    logger: logging.Logger,
    event: Event,
    message: str = "",
    *,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    """Emit a structured event.

    Domain fields passed as keyword arguments land as top-level JSON keys. Never
    pass secrets or user documents here - use :func:`redact_text` and
    :func:`hash_user_id`.
    """
    logger.log(level, message or event.value, extra={"event": event.value, **fields})


def redact_text(text: str | None) -> dict[str, Any]:
    """Summarise user-supplied text for logs: length and a truncated hash only.

    Deliberately no preview. For a CV or a tax question the opening words are
    the identifying ones, so the usual "first 200 characters" compromise would
    put a name, an employer and a city straight into log storage.
    """
    if not text:
        return {"text_len": 0, "text_sha256": None}
    digest = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]
    return {"text_len": len(text), "text_sha256": digest}


def hash_user_id(user_id: str | None) -> str | None:
    """Stable pseudonym for a user id, so logs correlate without identifying.

    Truncated to 12 hex characters: enough to follow one user through a request
    trace, not enough to be a durable cross-system identifier.
    """
    if not user_id:
        return None
    return hashlib.sha256(f"mym:{user_id}".encode()).hexdigest()[:12]
