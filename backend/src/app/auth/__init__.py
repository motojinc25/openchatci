"""API Authentication Dependency (CTR-0083, PRP-0045).

Shared FastAPI dependencies that enforce Bearer API_KEY authentication.

Two dependencies are exposed:

- ``verify_api_key`` (default for write endpoints used by the SPA)
    Bypassed when the request's **client address** is a loopback
    address (``127.0.0.1``, ``::1``, or the starlette TestClient
    sentinel). This covers the ``APP_HOST=0.0.0.0`` / LAN-exposure
    scenario correctly: same-machine browsers reach the server over
    the loopback interface and remain zero-configuration, while LAN
    peers (e.g. ``192.168.x.x``) are authenticated.

- ``verify_api_key_strict`` (for external-app entry points)
    Always requires ``API_KEY`` and a matching Bearer header regardless
    of client address. Used by the OpenAI-compatible Responses API
    (``/v1/responses``) where the key is the caller's identity even
    when the external app runs on the same host as the server.

Behavior matrix for ``verify_api_key``:

- Client on loopback (127.0.0.1, ::1, test harness)
    Auth is skipped regardless of API_KEY.
- Client on non-loopback, APP_REQUIRE_AUTH_ON_LAN=True (default)
    API_KEY must be set and the request must present a matching
    ``Authorization: Bearer {API_KEY}`` header. Missing config -> 503.
    Missing/mismatched header -> 401.
- Client on non-loopback, APP_REQUIRE_AUTH_ON_LAN=False
    Auth is skipped. A startup-time warning is logged so the operator
    is explicit about the insecure mode.

The server-side startup validator still inspects
``settings.is_loopback_bind`` so operators who bind to a non-loopback
address without ``API_KEY`` get a clear warning at boot, but the
runtime auth decision is made per-request against the actual client.

Behavior for ``verify_api_key_strict`` is identical to the non-loopback
path of ``verify_api_key``, applied to every request regardless of
client address.
"""

from __future__ import annotations

import ipaddress
import logging

from fastapi import HTTPException, Request

from app.core.config import settings

logger = logging.getLogger(__name__)

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
    """Return True when the request's client address is a loopback peer.

    Accepts IPv4/IPv6 loopback literals, the reserved ``localhost``
    hostname, and the starlette TestClient sentinel. Any other value
    (including ``None`` / unknown) is treated as non-loopback so the
    dependency fails closed by default.
    """
    if not client_host:
        return False
    host = client_host.strip().lower()
    if host in _LOOPBACK_HOSTNAMES:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _check_bearer_header(request: Request) -> None:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail=_MISSING_HEADER_DETAIL)
    token = auth_header[len("Bearer ") :]
    if token != settings.api_key:
        raise HTTPException(status_code=401, detail=_INVALID_KEY_DETAIL)


async def verify_api_key(request: Request) -> None:
    """FastAPI dependency: validate Bearer API key on write endpoints.

    Bypassed when the request's client address is loopback (same-machine
    peer) so ``APP_HOST=0.0.0.0`` + local SPA / curl keeps working with
    zero configuration. LAN peers are authenticated via ``API_KEY``.

    Raises:
        HTTPException 503: Non-loopback client with auth required but
            no API_KEY configured.
        HTTPException 401: Missing or mismatched ``Authorization``
            header on a non-loopback client with auth required.
    """
    client_host = request.client.host if request.client else None
    if _is_client_loopback(client_host):
        return

    if not settings.app_require_auth_on_lan:
        return

    if not settings.api_key:
        raise HTTPException(status_code=503, detail=_MISSING_API_KEY_DETAIL)

    _check_bearer_header(request)


async def verify_api_key_strict(request: Request) -> None:
    """FastAPI dependency: always validate Bearer API key (external-app paths).

    Used by external-app-facing endpoints (e.g. ``/v1/responses``) where
    the Bearer token is the caller's identity and the endpoint must
    authenticate even on a loopback bind.

    Raises:
        HTTPException 503: ``API_KEY`` is not configured.
        HTTPException 401: Missing or mismatched ``Authorization`` header.
    """
    if not settings.api_key:
        raise HTTPException(status_code=503, detail=_MISSING_API_KEY_STRICT_DETAIL)
    _check_bearer_header(request)


__all__ = ["verify_api_key", "verify_api_key_strict"]
