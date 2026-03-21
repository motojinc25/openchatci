import logging

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_host: str = "127.0.0.1"
    app_port: int = 8000
    app_debug: bool = True
    frontend_dist: str = "../frontend/dist"
    cors_allowed_origins: str = "http://localhost:5173"

    # TLS / HTTPS (CTR-0054, PRP-0029)
    app_ssl_certfile: str = ""
    app_ssl_keyfile: str = ""

    # Azure OpenAI
    azure_openai_endpoint: str = ""

    # Multi-Model Configuration (CTR-0069, PRP-0035)
    # Comma-separated deployment names. First entry is the default model.
    azure_openai_models: str = ""

    # Backward compatibility: old single-model variable (removed in PRP-0035).
    # If AZURE_OPENAI_MODELS is empty, this value is used as fallback.
    azure_openai_responses_deployment_name: str = ""

    # Web Search
    web_search_country: str = "US"

    # Reasoning Effort (CTR-0069, PRP-0035)
    # Per-model format: "o3:high,o4-mini:medium" (only listed models get reasoning)
    # Single value fallback: "high" (applies to ALL models, deprecated)
    # Empty: reasoning disabled for all models
    # Valid effort values: low, medium, high, xhigh
    reasoning_effort: str = ""

    # Session
    sessions_dir: str = ".sessions"

    # File Upload
    upload_dir: str = ".uploads"

    # Speech-to-Text
    whisper_deployment_name: str = "whisper-1"

    # Model Context Window (CTR-0069, PRP-0035)
    # Per-model format: "gpt-4o:128000,o3:200000,gpt-4.1-mini:1047576"
    # Single integer fallback: "128000" (applies to all models)
    # | Model                    | max_context_tokens |
    # | gpt-4o / gpt-4o-mini    | 128000             |
    # | gpt-4.1 / gpt-4.1-mini  | 1047576            |
    # | o3 / o4-mini             | 200000             |
    model_max_context_tokens: str = "128000"

    # Text-to-Speech (CTR-0039, PRP-0022)
    elevenlabs_api_key: str = ""
    tts_model_id: str = "eleven_multilingual_v2"
    tts_voice_id: str = ""

    # Image Generation (CTR-0049, CTR-0050, PRP-0027)
    image_deployment_name: str = ""

    # Coding Tools (CTR-0031, CTR-0032, PRP-0019)
    coding_enabled: bool = False
    coding_workspace_dir: str = ""
    coding_bash_timeout: int = 30
    coding_max_output_chars: int = 100000
    coding_max_turns: int = 50

    # Agent Skills (CTR-0042, PRP-0024)
    skills_dir: str = ".skills"

    # Prompt Templates (CTR-0046, PRP-0026)
    templates_dir: str = ".templates"

    # MCP Integration (CTR-0059, PRP-0031)
    mcp_config_file: str = ""

    # MCP Apps (CTR-0066, PRP-0034)
    mcp_apps_sandbox_port: int = 8081

    # OpenAI Compatible API (CTR-0056, PRP-0030)
    api_key: str = ""

    # DevUI (CTR-0024, PRP-0016)
    devui_enabled: bool = False
    devui_port: int = 8080
    devui_auth_enabled: bool = True
    devui_auth_token: str = ""
    devui_tracing: bool = False
    devui_mode: str = "developer"

    # ---- Multi-Model helpers (CTR-0069) ----

    @property
    def model_list(self) -> list[str]:
        """Parse AZURE_OPENAI_MODELS into an ordered list of deployment names."""
        return [m.strip() for m in self.azure_openai_models.split(",") if m.strip()]

    @property
    def default_model(self) -> str:
        """First model in the list is the default."""
        models = self.model_list
        if not models:
            return ""
        return models[0]

    def get_max_context_tokens(self, model: str | None = None) -> int:
        """Resolve max context tokens for a specific model.

        Supports two formats:
        - Per-model: "gpt-4o:128000,o3:200000"
        - Single integer: "128000" (applies to all models)
        """
        raw = self.model_max_context_tokens.strip()
        if ":" not in raw:
            # Single integer fallback
            try:
                return int(raw)
            except ValueError:
                return 128000
        # Per-model format
        pairs: dict[str, str] = {}
        for entry in raw.split(","):
            entry = entry.strip()
            if ":" in entry:
                name, value = entry.split(":", 1)
                pairs[name.strip()] = value.strip()
        target = model or self.default_model
        if target in pairs:
            try:
                return int(pairs[target])
            except ValueError:
                pass
        # Fallback: default model's value, or 128000
        if self.default_model in pairs:
            try:
                return int(pairs[self.default_model])
            except ValueError:
                pass
        return 128000

    @property
    def max_context_tokens_map(self) -> dict[str, int]:
        """Return a map of model -> max_context_tokens for all configured models."""
        return {model: self.get_max_context_tokens(model) for model in self.model_list}

    def get_reasoning_effort(self, model: str | None = None) -> str | None:
        """Resolve reasoning effort for a specific model.

        Returns the effort level string if configured for the model, or None
        if reasoning should not be applied.

        Supports two formats:
        - Per-model: "o3:high,o4-mini:medium" -> only listed models get reasoning
        - Single value (deprecated): "high" -> applies to ALL models
        - Empty: disabled for all models

        Models NOT listed in per-model format receive None (no reasoning parameter).
        This is the "not set" semantic: the model does not send reasoning.effort.
        """
        raw = self.reasoning_effort.strip()
        if not raw:
            return None

        if ":" not in raw:
            # Single value (deprecated backward compat): applies to all models
            _logger.warning(
                "REASONING_EFFORT='%s' (single value) applies to ALL models. "
                "Migrate to per-model format: REASONING_EFFORT=model:%s",
                raw,
                raw,
            )
            return raw

        # Per-model format: "o3:high,o4-mini:medium"
        pairs: dict[str, str] = {}
        for entry in raw.split(","):
            entry = entry.strip()
            if ":" in entry:
                name, value = entry.split(":", 1)
                pairs[name.strip()] = value.strip()

        target = model or self.default_model
        return pairs.get(target)  # None if model not listed -> no reasoning

    # ---- Validators ----

    @model_validator(mode="after")
    def _validate_models(self) -> "Settings":
        # Backward compatibility: migrate old single-model variable (PRP-0035)
        if not self.azure_openai_models and self.azure_openai_responses_deployment_name:
            self.azure_openai_models = self.azure_openai_responses_deployment_name
            _logger.warning(
                "AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME is deprecated. "
                "Please migrate to AZURE_OPENAI_MODELS=%s in your .env file.",
                self.azure_openai_models,
            )
        if not self.model_list:
            _logger.warning("AZURE_OPENAI_MODELS is empty; agent creation will be skipped.")
        return self

    @model_validator(mode="after")
    def _validate_ssl_pair(self) -> "Settings":
        has_cert = bool(self.app_ssl_certfile)
        has_key = bool(self.app_ssl_keyfile)
        if has_cert != has_key:
            msg = "APP_SSL_CERTFILE and APP_SSL_KEYFILE must both be provided or both omitted."
            raise ValueError(msg)
        if has_cert and has_key:
            from pathlib import Path

            cert_path = Path(self.app_ssl_certfile)
            key_path = Path(self.app_ssl_keyfile)
            if not cert_path.exists():
                msg = f"SSL certificate file not found: {cert_path}"
                raise ValueError(msg)
            if not key_path.exists():
                msg = f"SSL key file not found: {key_path}"
                raise ValueError(msg)
        return self


settings = Settings()
