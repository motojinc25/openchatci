"""Tenant Context (CTR-0085, PRP-0048).

Phase 1 groundwork for multi-tenant deployments. Exposes a single
``tenant_var`` contextvar plus a named ``TenantExtractor`` registry.
The default resolved value is ``"default"`` so OSS code written
against this module works unchanged in the single-tenant case and
stays compatible with the Phase 2 storage Protocols that will consume
``tenant_var``.

Registered extractor names and their status:

- ``none`` — OSS default. Ignores the request and returns ``"default"``.
- ``jwt_claim`` — Phase 1 implementation. Reads a configured claim
  (``TENANT_JWT_CLAIM``, default ``tid``) from ``Identity.raw`` and
  falls back to ``Identity.tenant_id`` / ``"default"``.
- ``subdomain`` — reserved name for a future request-host-based
  extractor. Calling this name before a concrete implementation lands
  raises ``NotImplementedError``.
- ``api_key`` — reserved name for a future API-key-to-tenant-mapping
  extractor. Same raise-until-implemented semantics as ``subdomain``.

Commercial builds register their own selected extractor via
``register_tenant_extractor`` before the FastAPI routes handle their
first request.
"""

from __future__ import annotations

from contextvars import ContextVar
import logging
import os
from typing import TYPE_CHECKING, Any, ClassVar, Protocol, runtime_checkable

from app.core.config import settings

if TYPE_CHECKING:
    from fastapi import Request

    from app.auth.provider import Identity

logger = logging.getLogger(__name__)

# The default tenant_id seen by storage code running in the
# single-tenant OSS case. Multi-tenant commercial deployments override
# this per-request via TenantMiddleware (CTR-0085).
DEFAULT_TENANT_ID = "default"

tenant_var: ContextVar[str] = ContextVar("tenant_id", default=DEFAULT_TENANT_ID)

# Names reserved in the registry. Unknown names raise a clear error so
# operators learn about unsupported extractors at configuration time
# instead of through silent default-tenant routing.
RESERVED_EXTRACTOR_NAMES: frozenset[str] = frozenset({"none", "jwt_claim", "subdomain", "api_key"})


@runtime_checkable
class TenantExtractor(Protocol):
    """Contract that maps a request + identity to a tenant id string.

    Implementations MUST:
        - set ``name`` to one of ``RESERVED_EXTRACTOR_NAMES``
        - return a non-empty string; falling back to
          ``DEFAULT_TENANT_ID`` is the expected behavior when the
          extractor has nothing useful to say for a given request
    """

    name: str

    async def extract(self, request: Request, identity: Identity | None) -> str: ...


# ---- OSS extractors ----


class NoneTenantExtractor:
    """Single-tenant extractor: every request maps to ``"default"``.

    Default on OSS. Has no configuration surface.
    """

    name: ClassVar[str] = "none"

    async def extract(
        self,
        request: Request,
        identity: Identity | None,
    ) -> str:
        return DEFAULT_TENANT_ID


class JwtClaimTenantExtractor:
    """Extract tenant id from a JWT claim surfaced by the AuthProvider.

    Reads ``Identity.raw[claim]`` first. When the provider did not
    attach the claim, falls back to ``Identity.tenant_id`` and then to
    ``DEFAULT_TENANT_ID``.

    This extractor is provider-agnostic: any ``AuthProvider`` that
    populates ``Identity.raw`` with a decoded JWT claim map works.
    Commercial ``MsalAuthProvider`` (CTR-0086) is the canonical Phase 1
    user.
    """

    name: ClassVar[str] = "jwt_claim"

    def __init__(self, claim: str = "tid") -> None:
        self.claim = claim

    async def extract(
        self,
        request: Request,
        identity: Identity | None,
    ) -> str:
        if identity is None:
            return DEFAULT_TENANT_ID
        value: Any = None
        if isinstance(identity.raw, dict):
            value = identity.raw.get(self.claim)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if identity.tenant_id:
            return identity.tenant_id
        return DEFAULT_TENANT_ID

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> JwtClaimTenantExtractor:
        src = env if env is not None else os.environ
        return cls(claim=src.get("TENANT_JWT_CLAIM", "tid"))


class _ReservedTenantExtractor:
    """Sentinel for reserved-but-unimplemented extractor names.

    Calling ``extract`` raises ``NotImplementedError`` with a clear
    message so misconfiguration surfaces at request time instead of
    silently routing every tenant to ``"default"``.
    """

    def __init__(self, name: str) -> None:
        self.name = name

    async def extract(
        self,
        request: Request,
        identity: Identity | None,
    ) -> str:
        msg = (
            f"Tenant extractor {self.name!r} is reserved but not implemented. "
            f"Commercial builds must register an implementation before use, "
            f"or choose 'none' / 'jwt_claim' for Phase 1."
        )
        raise NotImplementedError(msg)


# ---- Registry ----

_extractor: TenantExtractor | None = None


def register_tenant_extractor(extractor: TenantExtractor) -> None:
    """Register the active tenant extractor for this process.

    Validates that ``extractor.name`` is one of the reserved names so
    the configuration surface stays small and predictable. Commercial
    builds call this at startup before the first request.
    """
    global _extractor
    if not isinstance(extractor, TenantExtractor):
        msg = f"{extractor!r} does not satisfy the TenantExtractor Protocol"
        raise TypeError(msg)
    if extractor.name not in RESERVED_EXTRACTOR_NAMES:
        msg = f"Unknown tenant extractor name {extractor.name!r}. Allowed names: {sorted(RESERVED_EXTRACTOR_NAMES)}"
        raise ValueError(msg)
    logger.info("Registering tenant extractor: %s", extractor.name)
    _extractor = extractor


def get_tenant_extractor() -> TenantExtractor:
    """Return the active extractor, auto-resolving from settings on first call."""
    global _extractor
    if _extractor is not None:
        return _extractor
    _extractor = _auto_select_extractor()
    logger.info("Tenant extractor auto-selected: %s", _extractor.name)
    return _extractor


def reset_tenant_extractor() -> None:
    """Test-only hook: clear the registered extractor."""
    global _extractor
    _extractor = None


def _auto_select_extractor() -> TenantExtractor:
    configured = (settings.tenant_extractor or "").strip().lower() or "none"
    if configured == "none":
        return NoneTenantExtractor()
    if configured == "jwt_claim":
        return JwtClaimTenantExtractor.from_env()
    if configured in RESERVED_EXTRACTOR_NAMES:
        return _ReservedTenantExtractor(configured)
    logger.warning(
        "TENANT_EXTRACTOR=%r is not a registered name; allowed: %s. Falling back to 'none'.",
        configured,
        sorted(RESERVED_EXTRACTOR_NAMES),
    )
    return NoneTenantExtractor()


__all__ = [
    "DEFAULT_TENANT_ID",
    "RESERVED_EXTRACTOR_NAMES",
    "JwtClaimTenantExtractor",
    "NoneTenantExtractor",
    "TenantExtractor",
    "get_tenant_extractor",
    "register_tenant_extractor",
    "reset_tenant_extractor",
    "tenant_var",
]
