"""Application configuration.

This is the ONLY module that reads the environment. Everything else receives
configuration through :func:`get_settings`, which keeps secrets in one auditable
place and lets tests override settings without touching ``os.environ``.

Design rule that shapes this whole file: every external dependency is optional
and has a working default. An empty ``.env`` must still produce a running
product. The degradation is then reported to the user through the capability
endpoint rather than crashing - or, far worse, silently faking a result.
"""

from __future__ import annotations

import os
import secrets
from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent

# Values that mean "nobody edited .env yet" rather than a usable credential.
_PLACEHOLDERS = frozenset(
    {
        "",
        "sk-",
        "sk-...",
        "sk-ant-...",
        "sk-or-...",
        "your-key-here",
        "changeme",
        "todo",
        "none",
    }
)


def _is_real(value: SecretStr) -> bool:
    return value.get_secret_value().strip().lower() not in _PLACEHOLDERS


class LLMProviderName(StrEnum):
    ANTHROPIC = "anthropic"
    OPENROUTER = "openrouter"
    SCRIPTED = "scripted"
    NONE = "none"


class SearchProviderName(StrEnum):
    NONE = "none"
    TAVILY = "tavily"
    BRAVE = "brave"
    SERPER = "serper"


class EmbeddingBackend(StrEnum):
    #: Always available. BM25 over the curated corpus, implemented in numpy.
    LEXICAL = "lexical"
    #: On-device dense vectors via fastembed. Needs the ``local-embed`` extra.
    LOCAL = "local"
    #: Hosted embedding endpoint. Needs a key and bills per call.
    OPENAI = "openai"


class AuthBackend(StrEnum):
    LOCAL = "local"
    SUPABASE = "supabase"


class Settings(BaseSettings):
    """Runtime settings, loaded from environment and ``.env``."""

    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        env_prefix="MYM_",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "Money You are Missing"
    environment: str = "development"

    # ------------------------------------------------------------- database
    # Unset -> SQLite at data/app.db. Set -> Postgres, with pgvector used when
    # the extension is present. This single URL drives the dialect, the vector
    # strategy and the Alembic target; nothing else branches on deployment.
    database_url: str | None = None
    database_echo: bool = False

    # ----------------------------------------------------------------- auth
    auth_backend: AuthBackend = AuthBackend.LOCAL
    # Ephemeral in development so a fresh clone just works. A startup check
    # refuses to boot without an explicit one outside development.
    jwt_secret: SecretStr = Field(default_factory=lambda: SecretStr(secrets.token_urlsafe(48)))
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 14
    supabase_url: str | None = None
    supabase_jwt_secret: SecretStr = SecretStr("")

    # ------------------------------------------------------------------ llm
    llm_provider: LLMProviderName = LLMProviderName.ANTHROPIC
    anthropic_api_key: SecretStr = Field(default=SecretStr(""), alias="ANTHROPIC_API_KEY")
    openrouter_api_key: SecretStr = Field(default=SecretStr(""), alias="OPENROUTER_API_KEY")
    llm_model: str = "claude-opus-5"
    llm_classifier_model: str = "claude-haiku-4-5"
    llm_temperature: float = 0.0
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 2
    # Every call returns a small structured object, so a large completion budget
    # buys nothing, and some gateways gate on the reserved amount up front.
    llm_max_tokens: int = 2048

    # ---------------------------------------------------------- live search
    search_provider: SearchProviderName = SearchProviderName.NONE
    tavily_api_key: SecretStr = Field(default=SecretStr(""), alias="TAVILY_API_KEY")
    brave_api_key: SecretStr = Field(default=SecretStr(""), alias="BRAVE_SEARCH_API_KEY")
    serper_api_key: SecretStr = Field(default=SecretStr(""), alias="SERPER_API_KEY")
    search_timeout_seconds: float = 20.0
    search_max_results_per_query: int = 10
    search_max_queries_per_run: int = 6

    # -------------------------------------------------------- web retrieval
    # Applies to every outbound fetch of third-party content. See app/security/web.py.
    fetch_timeout_seconds: float = 15.0
    fetch_max_bytes: int = 2_000_000
    fetch_user_agent: str = (
        "MoneyYoureMissing/0.1 (+https://github.com/katerina-tech/money_u_missing; "
        "opportunity discovery bot)"
    )
    fetch_min_interval_seconds: float = 1.0
    fetch_cache_ttl_seconds: int = 3600
    respect_robots_txt: bool = True

    # ------------------------------------------------------------ retrieval
    embedding_backend: EmbeddingBackend = EmbeddingBackend.LEXICAL
    local_embedding_model: str = "BAAI/bge-small-en-v1.5"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_api_key: SecretStr = Field(default=SecretStr(""), alias="OPENAI_API_KEY")
    chunk_size: int = 900
    chunk_overlap: int = 150
    rag_top_k: int = 6
    # A legal fact past this age is reported as NEEDS_REVIEW instead of being
    # answered from. German tax thresholds change yearly; silence beats
    # confident staleness.
    legal_fact_max_age_days: int = 365

    # ------------------------------------------------------------- security
    injection_classifier_enabled: bool = True
    injection_heuristic_threshold: float = 0.3
    max_upload_bytes: int = 5_000_000
    rate_limit_per_minute: int = 60
    rate_limit_burst: int = 20
    # Discovery runs cost real money (search + model). Its own tighter bucket.
    discovery_rate_limit_per_hour: int = 20
    password_min_length: int = 10

    # ---------------------------------------------------------------- paths
    data_dir: Path = BACKEND_ROOT / "data"
    knowledge_dir: Path = BACKEND_ROOT / "data" / "knowledge"
    upload_dir: Path = BACKEND_ROOT / "data" / "uploads"
    sqlite_path: Path = BACKEND_ROOT / "data" / "app.db"

    # ------------------------------------------------------------- features
    demo_mode_enabled: bool = True
    payments_enabled: bool = False
    cors_origins: str = "http://localhost:3000"

    # -------------------------------------------------------------- logging
    log_level: str = "INFO"
    log_format: str = "console"

    @field_validator("cors_origins")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()

    # -------------------------------------------------------- derived state
    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite+pysqlite:///{self.sqlite_path.as_posix()}"

    @property
    def uses_postgres(self) -> bool:
        return self.resolved_database_url.startswith("postgres")

    @property
    def llm_key(self) -> SecretStr:
        if self.llm_provider is LLMProviderName.OPENROUTER:
            return self.openrouter_api_key
        return self.anthropic_api_key

    @property
    def llm_available(self) -> bool:
        """True when a model call can actually be made.

        ``scripted`` counts as available on purpose: it is the deterministic
        provider the tests and the offline demo run against.
        """
        if self.llm_provider is LLMProviderName.SCRIPTED:
            return True
        if self.llm_provider is LLMProviderName.NONE:
            return False
        return _is_real(self.llm_key)

    @property
    def search_key(self) -> SecretStr:
        return {
            SearchProviderName.TAVILY: self.tavily_api_key,
            SearchProviderName.BRAVE: self.brave_api_key,
            SearchProviderName.SERPER: self.serper_api_key,
        }.get(self.search_provider, SecretStr(""))

    @property
    def live_search_available(self) -> bool:
        return self.search_provider is not SearchProviderName.NONE and _is_real(self.search_key)

    def startup_problems(self) -> list[str]:
        """Configuration that is fatal in production but fine locally."""
        problems: list[str] = []
        if not self.is_production:
            return problems
        if "MYM_JWT_SECRET" not in os.environ:
            problems.append(
                "MYM_JWT_SECRET is unset. Outside development the signing key must be "
                "explicit, or every deploy silently invalidates all sessions."
            )
        if not self.database_url:
            problems.append(
                "MYM_DATABASE_URL is unset. The SQLite fallback is a development "
                "convenience; container filesystems are ephemeral."
            )
        if "*" in self.cors_origin_list:
            problems.append("MYM_CORS_ORIGINS must not be '*' in production.")
        return problems


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
