"""Agent factory for Multi-Model Agent Registry (CTR-0026, CTR-0070, PRP-0035).

Creates an AgentRegistry maintaining one Agent instance per configured
deployment name. All agents share the same Tools, Skills, MCP tools,
and context_providers. Only the underlying client differs.

Weather tools (CTR-0027, PRP-0017) are registered as AI functions.
Coding tools (CTR-0031, CTR-0032, PRP-0019) are conditionally registered.
Agent Skills (CTR-0043, PRP-0024) are conditionally loaded via SkillsProvider.
MCP tools (CTR-0060, PRP-0031) are dynamically loaded from config file.
"""

import logging
from pathlib import Path
import platform
from typing import Any

from app.agui.agent_registry import AgentRegistry
from app.core.config import settings
from app.mcp.lifecycle import get_mcp_server_names, get_mcp_tools
from app.session.provider import FileHistoryProvider
from app.skills.provider import create_skills_provider
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


def create_agent_registry() -> AgentRegistry:
    """Create the AgentRegistry with one Agent per configured model (CTR-0070).

    Replaces the former create_agent() single-instance pattern.
    """
    # Web search tool requires a client -- use the default model's client to obtain it.
    # The tool object itself is model-agnostic (it calls a separate search service).
    from agent_framework.azure import AzureOpenAIResponsesClient
    from azure.identity import AzureCliCredential

    _temp_client = AzureOpenAIResponsesClient(
        credential=AzureCliCredential(),
        endpoint=settings.azure_openai_endpoint or None,
        deployment_name=settings.default_model,
    )
    web_search_tool = _temp_client.get_web_search_tool(
        user_location={"type": "approximate", "country": settings.web_search_country},
    )

    history_provider = FileHistoryProvider(
        sessions_dir=Path(settings.sessions_dir),
    )

    # NOTE: reasoning_effort is resolved per-model in AgentRegistry (CTR-0069)

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

    # Conditionally register image generation tools (CTR-0050, PRP-0027)
    if settings.image_deployment_name:
        from app.image_gen.tools import edit_image, generate_image

        tools.extend([generate_image, edit_image])
        instructions += (
            " You can generate images from text descriptions using generate_image. "
            "You can also edit existing images using edit_image by providing the filename "
            "of an uploaded or previously generated image. "
            "After generating or editing an image, describe what was created."
        )
        logger.info("Image generation tools enabled (deployment=%s)", settings.image_deployment_name)

    # MCP tools (CTR-0060, PRP-0031)
    mcp_tools = get_mcp_tools()
    if mcp_tools:
        tools.extend(mcp_tools)
        mcp_server_names = get_mcp_server_names()
        servers_list = ", ".join(mcp_server_names)
        instructions += (
            f" You have MCP (Model Context Protocol) tools available from the following "
            f"connected servers: {servers_list}. "
            "When the user's request can be fulfilled by an MCP tool, ALWAYS prefer "
            "using the MCP tool over web search or other built-in tools. "
            "MCP tools provide direct, structured access to external services and "
            "are more reliable than general web search for their specific domains. "
            "After using an MCP tool, summarize the result clearly for the user."
        )
        logger.info("MCP tools added to agent: %d tool(s) from servers: %s", len(mcp_tools), servers_list)

    # Context providers (CTR-0043, PRP-0024)
    context_providers: list[Any] = [history_provider]
    skills_provider = create_skills_provider()
    if skills_provider:
        context_providers.append(skills_provider)

    registry = AgentRegistry(
        tools=tools,
        context_providers=context_providers,
        instructions=instructions,
    )

    return registry
