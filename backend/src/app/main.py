"""FastAPI application entry point.

- Mounts AG-UI endpoint (CTR-0009)
- Launches DevUI server (CTR-0025, PRP-0016)
- Mounts session management API (CTR-0015)
- Mounts image upload API (CTR-0022)
- Mounts speech-to-text API (CTR-0021)
- Mounts text-to-speech API (CTR-0039)
- Mounts prompt templates API (CTR-0047)
- Serves frontend build artifacts (CTR-0005)
- Loads configuration (CTR-0006)
"""

import importlib.metadata
from pathlib import Path
import sys
import warnings

# Ensure UTF-8 output on Windows to prevent garbled non-ASCII characters (e.g. °C) in logs
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from azure.identity import AzureCliCredential, get_bearer_token_provider
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from openai import AzureOpenAI

from app.agui.agent_factory import create_agent
from app.agui.endpoint import register_agui_endpoints
from app.core.config import settings
from app.devui.launcher import launch_devui_if_enabled
from app.prompt_templates.router import router as templates_router
from app.session.router import router as session_router
from app.stt.router import router as stt_router
from app.stt.router import set_stt_provider
from app.stt.whisper import AzureOpenAIWhisperProvider
from app.tts.elevenlabs import ElevenLabsTTSProvider
from app.tts.router import router as tts_router
from app.tts.router import set_tts_provider
from app.upload.router import router as upload_router

# Suppress pydantic warnings from agent-framework-ag-ui's Field(validation_alias=...) usage
warnings.filterwarnings("ignore", category=UserWarning, module=r"pydantic\._internal\._generate_schema")

load_dotenv()

# Logging is configured via log_conf.yaml (passed to uvicorn --log-config)

# Read version: importlib.metadata (pip install) -> pyproject.toml fallback (dev)
try:
    _app_version = importlib.metadata.version("openchatci")
except importlib.metadata.PackageNotFoundError:
    import tomllib

    _pyproject_path = Path(__file__).resolve().parent.parent.parent / "pyproject.toml"
    if _pyproject_path.exists():
        with _pyproject_path.open("rb") as _f:
            _app_version = tomllib.load(_f).get("project", {}).get("version", "0.0.0")
    else:
        _app_version = "0.0.0"

app = FastAPI(
    title="OpenChatCi",
    version=_app_version,
    docs_url="/docs" if settings.app_debug else None,
    redoc_url="/redoc" if settings.app_debug else None,
    openapi_url="/openapi.json" if settings.app_debug else None,
)

cors_origins = [origin.strip() for origin in settings.cors_allowed_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session management API (CTR-0015)
app.include_router(session_router)

# Prompt Templates API (CTR-0047)
app.include_router(templates_router)

# Image upload API (CTR-0022)
app.include_router(upload_router)

# Speech-to-Text API (CTR-0021)
if settings.azure_openai_endpoint:
    token_provider = get_bearer_token_provider(AzureCliCredential(), "https://cognitiveservices.azure.com/.default")
    stt_client = AzureOpenAI(
        azure_ad_token_provider=token_provider,
        azure_endpoint=settings.azure_openai_endpoint,
        api_version="2024-10-21",
    )
    set_stt_provider(AzureOpenAIWhisperProvider(stt_client, model=settings.whisper_deployment_name))
app.include_router(stt_router)

# Text-to-Speech API (CTR-0039)
if settings.elevenlabs_api_key and settings.tts_voice_id:
    set_tts_provider(
        ElevenLabsTTSProvider(
            api_key=settings.elevenlabs_api_key,
            voice_id=settings.tts_voice_id,
            model_id=settings.tts_model_id,
        )
    )
app.include_router(tts_router)

# Shared agent instance (CTR-0026)
agent = create_agent()

# AG-UI endpoint (CTR-0009)
register_agui_endpoints(app, agent=agent)

# DevUI server (CTR-0025)
launch_devui_if_enabled(agent)


# Model info endpoint (CTR-0041, PRP-0023)
@app.get("/api/model", tags=["Model"])
async def get_model_info():
    """Return model configuration for frontend context window display."""
    return {"max_context_tokens": settings.model_max_context_tokens}


# Static file serving (CTR-0005)
# Dual-mode path resolution: explicit override -> dev layout -> bundled assets
_explicit = Path(settings.frontend_dist).resolve()
if _explicit.is_dir():
    dist_path = _explicit
else:
    _dev_path = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist"
    _bundled_path = Path(__file__).resolve().parent / "_frontend_dist"
    if _dev_path.is_dir():
        dist_path = _dev_path
    elif _bundled_path.is_dir():
        dist_path = _bundled_path
    else:
        dist_path = None

if dist_path is not None:
    app.mount("/assets", StaticFiles(directory=dist_path / "assets"), name="static-assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """SPA fallback: serve index.html for all non-API routes."""
        resolved = (dist_path / full_path).resolve()
        if resolved.is_file() and resolved.is_relative_to(dist_path):
            return FileResponse(resolved)
        return FileResponse(dist_path / "index.html")
