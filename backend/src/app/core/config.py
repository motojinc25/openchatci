from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_host: str = "127.0.0.1"
    app_port: int = 8000
    app_debug: bool = True
    frontend_dist: str = "../frontend/dist"
    cors_allowed_origins: str = "http://localhost:5173"

    # Azure OpenAI
    azure_openai_endpoint: str = ""
    azure_openai_responses_deployment_name: str = "gpt-5.4"

    # Web Search
    web_search_country: str = "US"

    # Reasoning (for supported models: low/medium/high/xhigh, empty to disable)
    reasoning_effort: str = ""

    # Session
    sessions_dir: str = ".sessions"

    # File Upload
    upload_dir: str = ".uploads"

    # Speech-to-Text
    whisper_deployment_name: str = "whisper-1"

    # Model Context Window (CTR-0041, PRP-0023)
    model_max_context_tokens: int = 128000

    # Text-to-Speech (CTR-0039, PRP-0022)
    elevenlabs_api_key: str = ""
    tts_model_id: str = "eleven_multilingual_v2"
    tts_voice_id: str = ""

    # Coding Tools (CTR-0031, CTR-0032, PRP-0019)
    coding_enabled: bool = False
    coding_workspace_dir: str = ""
    coding_bash_timeout: int = 30
    coding_max_output_chars: int = 100000
    coding_max_turns: int = 50

    # Agent Skills (CTR-0042, PRP-0024)
    skills_dir: str = ".skills"

    # DevUI (CTR-0024, PRP-0016)
    devui_enabled: bool = False
    devui_port: int = 8080
    devui_auth_enabled: bool = True
    devui_auth_token: str = ""
    devui_tracing: bool = False
    devui_mode: str = "developer"


settings = Settings()
