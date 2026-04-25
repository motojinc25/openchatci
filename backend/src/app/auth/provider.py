"""Auth Provider Protocol (CTR-0084, PRP-0048).

Defines the pluggable authentication surface that the CTR-0083
dependencies delegate to. OSS ships two providers:

- ``NullAuthProvider`` — the default when ``AUTH_PROVIDER`` is unset and
  ``API_KEY`` is empty. Returns an anonymous ``Identity`` for every
  request and never raises. Preserves the OSS zero-configuration
  localhost experience.
- ``ApiKeyAuthProvider`` — selected automatically when ``API_KEY`` is
  set, or explicitly via ``AUTH_PROVIDER=api_key``. Implements the
  pre-PRP-0048 ``verify_api_key`` behavior: loopback clients bypass,
  non-loopback clients require a ``Authorization: Bearer <API_KEY>``
  header when ``APP_REQUIRE_AUTH_ON_LAN`` is true.

Commercial deployments (e.g. WeDXChatCi) register their own provider
(``MsalAuthProvider`` in CTR-0086) by importing
``register_auth_provider`` from this module before the FastAPI routes
are first invoked.

Only one provider is active per process. ``get_auth_provider`` returns
the registered singleton, auto-resolving the default on first call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import ipaddress
import logging
from typing import Any, ClassVar, Protocol, runtime_checkable

from fastapi import HTTPException, Request

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---- Constants shared with CTR-0083 dependencies ----

_MISSING_API_KEY_DETAIL = (
    "Client is on a non-loopback address but API_KEY is not configured. "
    "Set API_KEY in .env, or set APP_REQUIRE_AUTH_ON_LAN=false to acknowledge "
    "unauthenticated LAN exposure."
)
_MISSING_API_KEY_STRICT_DETAIL = "API is not configured. Set API_KEY in .env to enable external-app access."
_MISSING_HEADER_DETAIL = "Missing or invalid Authorization header. Expected: Bearer <token>"
_INVALID_KEY_DETAIL = "Invalid API key."

# Starlette TestClient uses "testclient" as the client host in its ASGI
# scope. Treat it as loopback so in-process tests do not need to inject
# Bearer headers.
_LOOPBACK_HOSTNAMES = frozenset({"localhost", "testclient"})


def _is_client_loopback(client_host: str | None) -> bool:
    """Return True when the request's client address is a loopback peer."""
    if not client_host:
        return False
    host = client_host.strip().lower()
    if host in _LOOPBACK_HOSTNAMES:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


# ---- Identity ----


@dataclass(frozen=True)
class Identity:
    """Authenticated principal surfaced by an ``AuthProvider``.

    Attributes:
        subject: Provider-defined stable identifier for the principal
            (e.g. MSAL ``oid`` claim, or the literal ``"local"`` for the
            static-key flow).
        tenant_id: Best-effort tenant attribution from the provider.
            For the ``null`` and ``api_key`` providers this is always
            ``"default"``. For ``msal`` it is populated from the JWT
            tenant claim. The ``TenantExtractor`` (CTR-0085) has the
            final say and may override this when writing the
            ``tenant_var`` contextvar.
        scopes: Provider-supplied scopes (empty for the OSS providers).
        raw: Provider-specific extra data such as the full JWT claim
            map. Extractors read configured keys from here.
    """

    subject: str
    tenant_id: str = "default"
    scopes: tuple[str, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict)


# ---- Provider Protocol ----


@runtime_checkable
class AuthProvider(Protocol):
    """Pluggable authentication contract consumed by CTR-0083.

    Implementations:
        - MUST set ``name`` to one of the registered provider names
          (``"null"``, ``"api_key"``, ``"msal"``, or a future registered
          value).
        - MUST implement ``authenticate`` as a best-effort identity
          resolver that returns ``None`` when no credential is present
          and does not raise on missing credentials.
        - MUST implement ``require`` so that it raises ``HTTPException``
          when the request cannot be authenticated under the active
          policy. ``require`` is what CTR-0083's standard FastAPI
          dependency delegates to.
        - MUST implement ``require_strict`` for the external-app entry
          points (e.g. ``/v1/responses``) where the Bearer token is the
          caller identity and the check applies regardless of client
          address. Providers that are always strict (e.g. MSAL) may
          simply return ``await self.require(request)``.
    """

    name: str

    async def authenticate(self, request: Request) -> Identity | None: ...

    async def require(self, request: Request) -> Identity: ...

    async def require_strict(self, request: Request) -> Identity: ...


# ---- NullAuthProvider (OSS default, localhost-first) ----


class NullAuthProvider:
    """Anonymous provider: never authenticates, never rejects.

    Used when the runtime is intentionally unauthenticated. Every
    request resolves to the same anonymous identity and passes through
    the ``require`` gate unchanged. This preserves the OSS
    zero-configuration localhost experience documented in UDR-0001.
    """

    name: ClassVar[str] = "null"

    _ANONYMOUS: ClassVar[Identity] = Identity(subject="anonymous", tenant_id="default")

    async def authenticate(self, request: Request) -> Identity | None:
        return self._ANONYMOUS

    async def require(self, request: Request) -> Identity:
        return self._ANONYMOUS

    async def require_strict(self, request: Request) -> Identity:
        # Strict endpoints (e.g. /v1/responses) require real enforcement.
        # The null provider cannot enforce, so surface a clear 503 so
        # operators see the configuration error instead of silently
        # letting unauthenticated clients through.
        raise HTTPException(status_code=503, detail=_MISSING_API_KEY_STRICT_DETAIL)


# ---- ApiKeyAuthProvider (static Bearer, preserves PRP-0045 semantics) ----


class ApiKeyAuthProvider:
    """Static Bearer API key provider.

    Preserves the pre-PRP-0048 behavior of ``verify_api_key``:

    - Loopback clients always pass (same-machine dev experience).
    - Non-loopback clients require ``Authorization: Bearer <API_KEY>``
      when ``APP_REQUIRE_AUTH_ON_LAN`` is true.
    - Missing ``API_KEY`` on a non-loopback client with auth required
      raises 503 so the operator sees a clear signal at request time.

    ``require`` implements the full policy. ``authenticate`` is a
    best-effort resolver: when a valid header is present it returns the
    identity, when no header is present it returns ``None`` (so callers
    that only need an optional identity do not break on loopback).
    """

    name: ClassVar[str] = "api_key"

    _LOCAL: ClassVar[Identity] = Identity(subject="local", tenant_id="default")

    async def authenticate(self, request: Request) -> Identity | None:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None
        token = auth_header[len("Bearer ") :]
        if not settings.api_key or token != settings.api_key:
            return None
        return self._LOCAL

    async def require(self, request: Request) -> Identity:
        client_host = request.client.host if request.client else None
        if _is_client_loopback(client_host):
            return self._LOCAL

        if not settings.app_require_auth_on_lan:
            return self._LOCAL

        if not settings.api_key:
            raise HTTPException(status_code=503, detail=_MISSING_API_KEY_DETAIL)

        self._check_bearer_header(request)
        return self._LOCAL

    async def require_strict(self, request: Request) -> Identity:
        """Always-on variant used by the OpenAI Responses API (CTR-0057).

        The external-app flow treats the Bearer token as the caller's
        identity and must authenticate even on a loopback bind.
        """
        if not settings.api_key:
            raise HTTPException(status_code=503, detail=_MISSING_API_KEY_STRICT_DETAIL)
        self._check_bearer_header(request)
        return self._LOCAL

    @staticmethod
    def _check_bearer_header(request: Request) -> None:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail=_MISSING_HEADER_DETAIL)
        token = auth_header[len("Bearer ") :]
        if token != settings.api_key:
            raise HTTPException(status_code=401, detail=_INVALID_KEY_DETAIL)


# ---- Provider registry (process-global singleton) ----

_provider: AuthProvider | None = None


def register_auth_provider(provider: AuthProvider) -> None:
    """Register the active ``AuthProvider`` for this process.

    Called by commercial / enterprise packages at startup (for example
    ``wedxchatci.app_factory.create_app``) to install an MSAL or other
    provider before the FastAPI routes handle their first request.
    Subsequent calls replace the previous provider.
    """
    global _provider
    if not isinstance(provider, AuthProvider):
        msg = f"{provider!r} does not satisfy the AuthProvider Protocol"
        raise TypeError(msg)
    logger.info("Registering auth provider: %s", provider.name)
    _provider = provider


def get_auth_provider() -> AuthProvider:
    """Return the active provider, auto-resolving the default on first call.

    Resolution order:
        1. Explicit registration via ``register_auth_provider``
           (commercial builds).
        2. ``settings.auth_provider = "null"`` — explicit opt-out.
        3. ``settings.auth_provider = "api_key"`` — explicit opt-in.
        4. Default: ``ApiKeyAuthProvider``. Preserves CTR-0083
           (PRP-0045) behavior regardless of whether ``API_KEY`` is
           set: loopback clients bypass, LAN clients get the 503/401
           gate when ``APP_REQUIRE_AUTH_ON_LAN`` is true.
    """
    global _provider
    if _provider is not None:
        return _provider
    _provider = _auto_select_provider()
    logger.info("Auth provider auto-selected: %s", _provider.name)
    return _provider


def reset_auth_provider() -> None:
    """Test-only hook: clear the registered provider.

    Lets unit tests exercise the auto-selection path and isolate
    per-test provider state.
    """
    global _provider
    _provider = None


def _auto_select_provider() -> AuthProvider:
    configured = (settings.auth_provider or "").strip().lower()
    if configured == "null":
        return NullAuthProvider()
    if configured == "api_key":
        return ApiKeyAuthProvider()
    if configured and configured not in {"null", "api_key"}:
        logger.warning(
            "AUTH_PROVIDER=%r is not a registered OSS provider; "
            "commercial builds register their own provider at startup. "
            "Falling back to ApiKeyAuthProvider (CTR-0083 behavior).",
            configured,
        )
    # Default preserves CTR-0083 (PRP-0045) behavior bit-for-bit:
    # the ApiKeyAuthProvider handles loopback bypass, the LAN 503
    # gate, and the 401 bearer-check uniformly whether API_KEY is
    # set or not. NullAuthProvider is opt-in only.
    return ApiKeyAuthProvider()


__all__ = [
    "ApiKeyAuthProvider",
    "AuthProvider",
    "Identity",
    "NullAuthProvider",
    "get_auth_provider",
    "register_auth_provider",
    "reset_auth_provider",
]
