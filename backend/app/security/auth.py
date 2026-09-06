"""Authentication: password hashing, tokens, and the verifier interface.

Two backends behind one interface. ``local`` issues and verifies our own JWTs
against Argon2id password hashes; ``supabase`` verifies tokens Supabase Auth
issued, so identity can be delegated without touching a single route. The
interface is :class:`TokenVerifier`, and route code depends only on that.

Decisions worth stating:

* **Argon2id, not bcrypt.** Memory-hard, so a stolen hash database is expensive
  to attack with GPUs. The parameters below are the library defaults, which
  track current guidance; they are recorded in the hash string, so raising them
  later re-hashes users transparently on their next login.
* **Refresh tokens are stored hashed and can be revoked.** A stateless refresh
  token cannot be logged out. Only the SHA-256 of the token is stored, so a
  database read does not yield a usable credential.
* **Login is constant-work.** A request for an unknown email still performs a
  hash verification against a dummy hash, so response timing does not reveal
  which addresses have accounts.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.config import AuthBackend, Settings, get_settings

logger = logging.getLogger(__name__)

_hasher = PasswordHasher()

#: Verified against on unknown-email logins so the work performed - and so the
#: response time - does not depend on whether the account exists.
_DUMMY_HASH = _hasher.hash("timing-equalisation-only")

ACCESS_AUDIENCE = "mym-access"


class AuthError(Exception):
    """Authentication failed. The message is safe to show to the caller."""

    def __init__(self, message: str = "Invalid credentials.", *, code: str = "invalid") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Principal:
    """Who is making the request."""

    user_id: str
    email: str | None = None
    is_demo: bool = False


# ------------------------------------------------------------------ passwords


def hash_password(plaintext: str, *, min_length: int = 10) -> str:
    """Hash a password, refusing ones that are trivially weak.

    The only rule is length. Composition rules (a digit, a symbol, a capital)
    push people towards `Password1!` and are worse than a length floor.
    """
    if len(plaintext) < min_length:
        raise AuthError(
            f"Please choose a password of at least {min_length} characters.", code="weak_password"
        )
    if len(plaintext) > 1024:
        # Argon2 is memory-hard by design; an unbounded input is a cheap DoS.
        raise AuthError("That password is too long.", code="weak_password")
    return _hasher.hash(plaintext)


def verify_password(stored_hash: str | None, plaintext: str) -> bool:
    """Constant-work verification. A missing hash still costs a full verify."""
    target = stored_hash or _DUMMY_HASH
    try:
        _hasher.verify(target, plaintext)
    except (VerifyMismatchError, InvalidHashError):
        return False
    except Exception:  # a corrupt hash must fail closed, not raise into a route
        logger.warning("password verification error", exc_info=True)
        return False
    return stored_hash is not None


def needs_rehash(stored_hash: str) -> bool:
    """True when the hash uses weaker parameters than the current policy."""
    try:
        return bool(_hasher.check_needs_rehash(stored_hash))
    except InvalidHashError:
        return True


# --------------------------------------------------------------------- tokens


def issue_access_token(principal: Principal, settings: Settings | None = None) -> tuple[str, int]:
    """Return ``(token, expires_in_seconds)``."""
    settings = settings or get_settings()
    now = datetime.now(UTC)
    expires = now + timedelta(minutes=settings.access_token_ttl_minutes)
    payload = {
        "sub": principal.user_id,
        "email": principal.email,
        "demo": principal.is_demo,
        "aud": ACCESS_AUDIENCE,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
        "jti": secrets.token_urlsafe(12),
    }
    token = jwt.encode(
        payload, settings.jwt_secret.get_secret_value(), algorithm=settings.jwt_algorithm
    )
    return token, settings.access_token_ttl_minutes * 60


def new_refresh_token() -> tuple[str, str]:
    """Return ``(plaintext, sha256_hex)``. Only the hash is ever stored."""
    plaintext = secrets.token_urlsafe(48)
    return plaintext, hash_refresh_token(plaintext)


def hash_refresh_token(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


# ------------------------------------------------------------------ verifiers


class TokenVerifier(ABC):
    """Turns a bearer token into a :class:`Principal`, or raises."""

    @abstractmethod
    def verify(self, token: str) -> Principal: ...


class LocalTokenVerifier(TokenVerifier):
    """Verifies tokens this service issued."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def verify(self, token: str) -> Principal:
        try:
            payload = jwt.decode(
                token,
                self._settings.jwt_secret.get_secret_value(),
                algorithms=[self._settings.jwt_algorithm],
                audience=ACCESS_AUDIENCE,
                # Explicit: an unsigned or alg=none token must not verify, and
                # an expired one must not be quietly accepted.
                options={"require": ["exp", "sub", "aud"], "verify_exp": True},
            )
        except jwt.ExpiredSignatureError as error:
            raise AuthError("Your session has expired.", code="expired") from error
        except jwt.InvalidTokenError as error:
            raise AuthError("Invalid session token.", code="invalid_token") from error

        subject = payload.get("sub")
        if not isinstance(subject, str) or not subject:
            raise AuthError("Invalid session token.", code="invalid_token")
        return Principal(
            user_id=subject,
            email=payload.get("email"),
            is_demo=bool(payload.get("demo", False)),
        )


class SupabaseTokenVerifier(TokenVerifier):
    """Verifies tokens issued by Supabase Auth.

    Supabase signs project JWTs with the project's JWT secret (HS256) and sets
    ``aud`` to ``authenticated``. Verifying locally means no network round trip
    on every request, and no dependency on Supabase being reachable for an
    already-authenticated user to read their own data.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        secret = self._settings.supabase_jwt_secret.get_secret_value()
        if not secret:
            raise ValueError(
                "MYM_AUTH_BACKEND=supabase requires MYM_SUPABASE_JWT_SECRET."
            )
        self._secret = secret

    def verify(self, token: str) -> Principal:
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=["HS256"],
                audience="authenticated",
                options={"require": ["exp", "sub"], "verify_exp": True},
            )
        except jwt.ExpiredSignatureError as error:
            raise AuthError("Your session has expired.", code="expired") from error
        except jwt.InvalidTokenError as error:
            raise AuthError("Invalid session token.", code="invalid_token") from error
        return Principal(user_id=str(payload["sub"]), email=payload.get("email"))


def build_verifier(settings: Settings | None = None) -> TokenVerifier:
    settings = settings or get_settings()
    if settings.auth_backend is AuthBackend.SUPABASE:
        return SupabaseTokenVerifier(settings)
    return LocalTokenVerifier(settings)
