"""Tenant Middleware (CTR-0085, PRP-0048).

ASGI middleware that:

1. Calls the registered ``AuthProvider.authenticate`` once per request
   to obtain a best-effort ``Identity`` (no 401 raised at this layer —
   that is the dependency's job via ``verify_api_key``).
2. Invokes the registered ``TenantExtractor.extract`` with the request
   and the resolved identity.
3. Sets ``tenant_var`` for the duration of the downstream request
   pipeline so storage-layer code (Phase 2) can scope reads/writes by
   the resolved tenant id.

OSS does not activate this middleware by default because the default
extractor is ``NoneTenantExtractor`` and the default provider is
``NullAuthProvider``; activating it in OSS would only populate a
constant value that already matches the contextvar's default.

Commercial builds add this middleware in ``wedxchatci.create_app``
(CTR-0087).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware

from app.auth.provider import get_auth_provider
from app.auth.tenant import DEFAULT_TENANT_ID, get_tenant_extractor, tenant_var

if TYPE_CHECKING:
    from starlette.middleware.base import RequestResponseEndpoint
    from starlette.requests import Request
    from starlette.responses import Response

logger = logging.getLogger(__name__)


class TenantMiddleware(BaseHTTPMiddleware):
    """Populate ``tenant_var`` for every request.

    Failures are intentionally non-fatal: if authentication or tenant
    extraction raises, the middleware logs and falls back to the
    default tenant id so that transport-level errors are still raised
    by the downstream dependency (``verify_api_key``) rather than here.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        tenant_id = DEFAULT_TENANT_ID
        try:
            identity = await get_auth_provider().authenticate(request)
        except Exception:
            logger.exception("AuthProvider.authenticate raised; falling back to default tenant")
            identity = None

        try:
            tenant_id = await get_tenant_extractor().extract(request, identity)
        except NotImplementedError:
            # Surface misconfiguration of a reserved extractor name
            # without crashing the middleware; the downstream storage
            # layer (Phase 2) will treat the default tenant as a safe
            # fallback until the extractor is implemented.
            logger.exception("Tenant extractor is reserved but not implemented")
        except Exception:
            logger.exception("TenantExtractor.extract raised; falling back to default tenant")

        if not tenant_id:
            tenant_id = DEFAULT_TENANT_ID

        token = tenant_var.set(tenant_id)
        try:
            return await call_next(request)
        finally:
            tenant_var.reset(token)


__all__ = ["TenantMiddleware"]
