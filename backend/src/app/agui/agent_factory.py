"""Agent factory for shared Agent instance (CTR-0026, PRP-0016).

Extracts agent creation logic from endpoint.py so the same Agent instance
can be used by both the AG-UI endpoint (CTR-0009) and DevUI server (CTR-0025).
Weather tools (CTR-0027, PRP-0017) are registered as AI functions.
Coding tools (CTR-0031, CTR-0032, PRP-0019) are conditionally registered.
"""

import logging
from pathlib import Path
import platform
from typing import Any

from agent_framework import Agent
from agent_framework.azure import AzureOpenAIResponsesClient
from azure.identity import AzureCliCredential

from app.core.config import settings
from app.session.provider import FileHistoryProvider
from app.weather.tools import get_coords_by_city, get_current_weather_by_coords, get_weather_next_week

logger = logging.getLogger(__name__)


def _build_coding_instructions() -> str:
    """Build platform-aware coding tool instructions."""
    os_name = platform.system()  # "Windows", "Darwin", "Linux"
    shell = "cmd.exe (Windows)" if os_name == "Windows" else "bash"
    os_label = {"Windows": "Windows", "Darwin": "macOS", "Linux": "Linux"}.get(os_name, os_name)

    platform_note = (
        f"The current platform is {os_label} with {shell}. Use platform-appropriate commands for bash_execute. "
    )
    if os_name == "Windows":
        platform_note += (
            "Use 'dir' instead of 'ls', 'type' instead of 'cat', "
            "'findstr' instead of 'grep', 'where' instead of 'which'. "
            "Use backslash for paths in commands or quote forward-slash paths. "
            "Prefer file_glob/file_grep tools over shell find/grep commands for cross-platform safety."
        )

    return (
        "You have access to coding tools for working with files in the workspace directory. "
        "Use file_glob to find files by pattern before reading them. "
        "Use file_grep to search for specific content across files. "
        "Use file_read to read file content. Use offset/limit for large files. "
        "Use file_write to create or modify files. "
        "Use bash_execute to run shell commands (build, test, git, etc.). "
        "All file paths are relative to the workspace directory. " + platform_note
    )


def _validate_coding_config() -> None:
    """Validate coding configuration at startup (CTR-0032)."""
    workspace = settings.coding_workspace_dir
    if not workspace:
        msg = "CODING_WORKSPACE_DIR must be set when CODING_ENABLED=true"
        raise ValueError(msg)
    if not Path(workspace).is_absolute():
        msg = f"CODING_WORKSPACE_DIR must be an absolute path: {workspace}"
        raise ValueError(msg)
    if not Path(workspace).is_dir():
        msg = f"CODING_WORKSPACE_DIR does not exist: {workspace}"
        raise ValueError(msg)


def create_chat_client() -> AzureOpenAIResponsesClient:
    """Create an AzureOpenAIResponsesClient for the agent."""
    return AzureOpenAIResponsesClient(
        credential=AzureCliCredential(),
        endpoint=settings.azure_openai_endpoint or None,
        deployment_name=settings.azure_openai_responses_deployment_name,
    )


def create_agent() -> Agent:
    """Create the shared Agent instance for AG-UI and DevUI (CTR-0026)."""
    client = create_chat_client()

    web_search_tool = client.get_web_search_tool(
        user_location={"type": "approximate", "country": settings.web_search_country},
    )

    history_provider = FileHistoryProvider(
        sessions_dir=Path(settings.sessions_dir),
    )

    default_options: dict[str, Any] = {}
    if settings.reasoning_effort:
        default_options["reasoning"] = {"effort": settings.reasoning_effort, "summary": "detailed"}

    # Base tools and instructions
    tools: list[Any] = [web_search_tool, get_coords_by_city, get_current_weather_by_coords, get_weather_next_week]
    instructions = (
        "You are a helpful AI assistant. "
        "You can search the web for up-to-date information. "
        "When you use web search results, include source links in your response "
        "as Markdown links: [source title](URL). "
        "Place citation links inline near the relevant text. "
        "You can also look up weather information for any city worldwide. "
        "For weather queries: first use get_coords_by_city to get coordinates, "
        "then use get_current_weather_by_coords or get_weather_next_week. "
        "After calling weather tools, provide a clear summary of the weather information."
    )

    # Conditionally register coding tools (CTR-0032, PRP-0019)
    if settings.coding_enabled:
        _validate_coding_config()
        from app.coding.tools import bash_execute, file_glob, file_grep, file_read, file_write

        tools.extend([file_read, file_write, bash_execute, file_glob, file_grep])
        instructions += " " + _build_coding_instructions()
        logger.info(
            "Coding tools enabled (workspace=%s, max_turns=%d)",
            settings.coding_workspace_dir,
            settings.coding_max_turns,
        )

    agent = Agent(
        name="OpenChatCi-Agent",
        instructions=instructions,
        client=client,
        tools=tools,
        context_providers=[history_provider],
        default_options=default_options or None,
    )

    logger.info("Agent created: %s (model=%s)", agent.name, settings.azure_openai_responses_deployment_name)
    return agent
