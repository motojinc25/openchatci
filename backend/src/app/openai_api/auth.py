"""Bearer token authentication for OpenAI API (CTR-0056, PRP-0030)."""

import logging

from fastapi import HTTPException, Request

from app.core.config import settings

logger = logging.getLogger(__name__)


async def verify_api_key(request: Request) -> None:
    """Validate Bearer token against API_KEY setting.

    Raises:
        HTTPException 503: API_KEY not configured
        HTTPException 401: Invalid or missing token
    """
    if not settings.api_key:
        raise HTTPException(status_code=503, detail="OpenAI API is not configured. Set API_KEY in .env.")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header. Expected: Bearer <token>")

    token = auth_header[7:]  # len("Bearer ") == 7
    if token != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key.")
