"""Analyst identity for approval endpoints.

The shared token is not per-user authentication. A valid configured token
identifies only the generic actor ``analyst``. Development without a token
records ``unverified``. Arbitrary ``X-Analyst-Id`` headers are ignored.
"""

from __future__ import annotations

import hmac
from hashlib import sha256

from app.core.config import Settings

ACTOR_ANALYST = "analyst"
ACTOR_UNVERIFIED = "unverified"


class AnalystAuthError(ValueError):
    def __init__(self, detail: str, *, status_code: int) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def _tokens_match(provided: str, expected: str) -> bool:
    """Constant-time compare that does not leak token length via compare_digest."""
    digest = hmac.new(b"aisoc-analyst-token", expected.encode("utf-8"), sha256).digest()
    provided_digest = hmac.new(b"aisoc-analyst-token", provided.encode("utf-8"), sha256).digest()
    return hmac.compare_digest(provided_digest, digest)


def _bearer_token(authorization: str | None) -> str | None:
    if authorization is None:
        return None
    scheme, separator, remainder = authorization.partition(" ")
    if separator == "" or scheme.lower() != "bearer":
        return None
    token = remainder.strip()
    return token or None


def resolve_actor(settings: Settings, authorization: str | None) -> str:
    """Return ``analyst`` or ``unverified``, or raise ``AnalystAuthError``.

    ``APP_ENV`` defaults to ``development`` when unset. ``test`` follows the
    development policy. ``production`` with an empty token is refused (403).
    """
    configured = settings.analyst_api_token
    if settings.is_production and configured is None:
        raise AnalystAuthError(
            "ANALYST_API_TOKEN is required in production",
            status_code=403,
        )
    if configured is None:
        return ACTOR_UNVERIFIED
    provided = _bearer_token(authorization)
    if provided is None or not _tokens_match(provided, configured):
        raise AnalystAuthError("Invalid or missing analyst token", status_code=401)
    return ACTOR_ANALYST
