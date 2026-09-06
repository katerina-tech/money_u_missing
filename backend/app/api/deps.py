"""Request-scoped dependencies: session, principal, services, rate limits.

Authorisation is centralised here rather than repeated per route. Every
authenticated endpoint depends on :func:`current_principal`, and every query
that touches user data filters by ``principal.user_id`` - there is no route that
takes a user id from the request body or path, which is the structural way to
prevent one user reading another's Money Map.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.base import get_session_factory
from app.db.models import User
from app.llm.base import LLMProvider
from app.llm.factory import build_provider
from app.rag.store import KnowledgeStore
from app.security.auth import AuthError, Principal, TokenVerifier, build_verifier
from app.security.guard import InjectionGuard
from app.security.ratelimit import RateLimiter, apply_headers, client_key
from app.services.legal_facts import LegalFactRepository
from app.sources.registry import SourceRegistry

# Built once. The BM25 index inside the store is rebuilt lazily when the corpus
# changes, so sharing it across requests is both safe and the point.
_knowledge_store: KnowledgeStore | None = None
_rate_limiter: RateLimiter | None = None
_verifier: TokenVerifier | None = None


def get_db() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def settings_dep() -> Settings:
    return get_settings()


def get_knowledge_store() -> KnowledgeStore:
    global _knowledge_store
    if _knowledge_store is None:
        _knowledge_store = KnowledgeStore()
    return _knowledge_store


def get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(get_settings())
    return _rate_limiter


def get_verifier() -> TokenVerifier:
    global _verifier
    if _verifier is None:
        _verifier = build_verifier()
    return _verifier


def reset_singletons() -> None:
    """Used by tests between configurations."""
    global _knowledge_store, _rate_limiter, _verifier
    _knowledge_store = None
    _rate_limiter = None
    _verifier = None


# ------------------------------------------------------------------ identity


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in to continue.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return authorization.split(" ", 1)[1].strip()


def current_principal(
    authorization: Annotated[str | None, Header()] = None,
    verifier: TokenVerifier = Depends(get_verifier),
) -> Principal:
    try:
        return verifier.verify(_bearer(authorization))
    except AuthError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
            headers={"WWW-Authenticate": "Bearer"},
        ) from error


def optional_principal(
    authorization: Annotated[str | None, Header()] = None,
    verifier: TokenVerifier = Depends(get_verifier),
) -> Principal | None:
    """For endpoints that work signed-out, such as the landing page's demo."""
    if not authorization:
        return None
    try:
        return verifier.verify(_bearer(authorization))
    except (AuthError, HTTPException):
        return None


def current_user(
    principal: Principal = Depends(current_principal),
    session: Session = Depends(get_db),
) -> User:
    user = session.get(User, principal.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="This account is no longer active."
        )
    return user


# ------------------------------------------------------------------ services


def get_provider(principal: Principal | None = Depends(optional_principal)) -> LLMProvider:
    return build_provider(user_id=principal.user_id if principal else None)


def get_guard(provider: LLMProvider = Depends(get_provider)) -> InjectionGuard:
    return InjectionGuard(provider=provider)


def get_registry() -> SourceRegistry:
    return SourceRegistry()


def get_legal_facts() -> LegalFactRepository:
    return LegalFactRepository()


# -------------------------------------------------------------- rate limits


def rate_limit(
    request: Request,
    principal: Principal | None = Depends(optional_principal),
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> None:
    key = client_key(request, principal.user_id if principal else None)
    decision = limiter.general.take(key)
    if not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please wait a moment.",
            headers={"Retry-After": str(decision.retry_after_seconds)},
        )
    request.state.rate_decision = decision


def discovery_rate_limit(
    principal: Principal = Depends(current_principal),
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> None:
    """A tighter bucket for the one endpoint that spends real money.

    A discovery run performs search-API calls and model extraction per page. The
    general limit is sized for browsing and would allow a loop to run up a bill
    in minutes.
    """
    decision = limiter.discovery.take(f"discovery:{principal.user_id}")
    if not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "You have run a lot of searches recently. New opportunities appear over "
                "days rather than minutes, so this limit rarely costs you anything."
            ),
            headers={"Retry-After": str(decision.retry_after_seconds)},
        )


__all__ = [
    "apply_headers",
    "current_principal",
    "current_user",
    "discovery_rate_limit",
    "get_db",
    "get_guard",
    "get_knowledge_store",
    "get_legal_facts",
    "get_provider",
    "get_rate_limiter",
    "get_registry",
    "optional_principal",
    "rate_limit",
    "reset_singletons",
    "settings_dep",
]
