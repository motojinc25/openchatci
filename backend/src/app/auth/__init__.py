"""API Authentication Dependency (CTR-0083, PRP-0045, PRP-0048).

Public FastAPI dependencies used by every authenticated REST endpoint.
Since PRP-0048 these are thin wrappers that delegate to the registered
``AuthProvider`` (CTR-0084). OSS ships ``NullAuthProvider`` (default)
and ``ApiKeyAuthProvider`` (auto-selected when ``API_KEY`` is set).
Commercial builds register ``MsalAuthProvider`` (CTR-0086) via
``register_auth_provider`` before routes handle their first request.

Two dependencies are exposed to keep the call-site surface stable:

- ``verify_api_key`` — for write endpoints consumed by the SPA.
  Delegates to ``provider.require``.
- ``verify_api_key_strict`` — for external-app endpoints such as
  ``/v1/responses`` (CTR-0057). Delegates to ``provider.require_strict``.

Behavior of the shipped providers is summarized on the provider
classes. The ``Identity`` returned by the dependency is discarded by
callers that only care about the pass/fail decision; forward-looking
code (Phase 2 storage Protocols) can type the dependency as
``Annotated[Identity, Depends(verify_api_key)]``.
"""

from __future__ import annotations

# NOTE: ``Request`` is kept as a runtime import (not under TYPE_CHECKING)
# because FastAPI's dependency-injection machinery resolves the annotation
# on ``verify_api_key`` / ``verify_api_key_strict`` at route-registration
# time via ``get_type_hints``. Moving it under TYPE_CHECKING makes FastAPI
# fall back to treating ``request`` as a body parameter, which causes a
# 422 on every authenticated write endpoint.
from fastapi import Request  # noqa: TC002

from app.auth.provider import (
    ApiKeyAuthProvider,
    AuthProvider,
    Identity,
    NullAuthProvider,
    get_auth_provider,
    register_auth_provider,
    reset_auth_provider,
)


async def verify_api_key(request: Request) -> Identity:
    """FastAPI dependency: validate the caller on write endpoints.

    Delegates to the active provider's ``require`` method. Behavior for
    the OSS providers:

    - Null provider: always passes with the anonymous identity.
    - API key provider: loopback bypass; non-loopback requires
      ``Authorization: Bearer ${API_KEY}`` when
      ``APP_REQUIRE_AUTH_ON_LAN`` is true.
    - Missing ``API_KEY`` on non-loopback with auth required -> 503.
    - Missing / mismatched header on non-loopback -> 401.
    """
    return await get_auth_provider().require(request)


async def verify_api_key_strict(request: Request) -> Identity:
    """FastAPI dependency: always-on variant for external-app paths.

    Used by the OpenAI-compatible Responses API (``/v1/responses``,
    CTR-0057) where the Bearer token is the caller's identity.

    - Null provider: 503 (strict enforcement is not available under
      an unauthenticated configuration).
    - API key provider: always requires ``Authorization: Bearer
      ${API_KEY}`` regardless of client address.
    - MSAL / other strict providers: identical to ``require``.
    """
    return await get_auth_provider().require_strict(request)


__all__ = [
    "ApiKeyAuthProvider",
    "AuthProvider",
    "Identity",
    "NullAuthProvider",
    "get_auth_provider",
    "register_auth_provider",
    "reset_auth_provider",
    "verify_api_key",
    "verify_api_key_strict",
]
