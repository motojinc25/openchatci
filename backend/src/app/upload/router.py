"""Image upload REST API (CTR-0022).

Provides endpoints for uploading images and serving uploaded files.
Uploaded files are stored in {UPLOAD_DIR}/{thread_id}/{filename}.
"""

import logging
import mimetypes
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Upload"])

ALLOWED_MEDIA_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


def _upload_dir() -> Path:
    return Path(settings.upload_dir)


class UploadResponse(BaseModel):
    uri: str
    media_type: str
    filename: str


@router.post("/api/upload/{thread_id}")
async def upload_image(thread_id: str, file: UploadFile) -> UploadResponse:
    """Upload an image file for a session."""
    content_type = file.content_type or ""
    if content_type not in ALLOWED_MEDIA_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {content_type}. Allowed: {', '.join(sorted(ALLOWED_MEDIA_TYPES))}",
        )

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    # Sanitize filename (prevent path traversal)
    safe_name = Path(file.filename).name
    if not safe_name or safe_name.startswith("."):
        raise HTTPException(status_code=400, detail="Invalid filename")

    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024 * 1024)}MB",
        )

    # Save to {UPLOAD_DIR}/{thread_id}/{filename}
    dest_dir = _upload_dir() / thread_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / safe_name
    dest_path.write_bytes(data)

    uri = f"/api/uploads/{thread_id}/{safe_name}"
    logger.info("Uploaded %s (%d bytes) to %s", safe_name, len(data), dest_path)

    return UploadResponse(uri=uri, media_type=content_type, filename=safe_name)


@router.get("/api/uploads/{thread_id}/{filename}")
async def serve_upload(thread_id: str, filename: str) -> FileResponse:
    """Serve an uploaded file."""
    safe_name = Path(filename).name
    file_path = (_upload_dir() / thread_id / safe_name).resolve()
    upload_root = _upload_dir().resolve()

    if not file_path.is_relative_to(upload_root):
        raise HTTPException(status_code=403, detail="Access denied")
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    media_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    return FileResponse(file_path, media_type=media_type)
