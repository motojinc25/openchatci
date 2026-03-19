"""MCP configuration parser (CTR-0059, PRP-0031).

Parses a Claude Desktop-compatible mcp_servers.json configuration file
and returns structured server definitions for tool creation.
"""

from dataclasses import dataclass, field
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class MCPServerConfig:
    """Parsed MCP server configuration entry."""

    name: str
    transport: str  # "stdio" or "http"
    # stdio fields
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    # http fields
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)


def parse_mcp_config(config_path: Path) -> list[MCPServerConfig]:
    """Parse Claude Desktop-compatible MCP configuration file.

    Args:
        config_path: Path to mcp_servers.json

    Returns:
        List of MCPServerConfig entries. Invalid entries are skipped with warnings.
    """
    try:
        raw = config_path.read_text(encoding="utf-8")
        config = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("MCP config file is not valid JSON: %s", config_path)
        return []
    except OSError:
        logger.error("Failed to read MCP config file: %s", config_path)
        return []

    servers_dict = config.get("mcpServers", {})
    if not isinstance(servers_dict, dict):
        logger.warning("mcpServers key is not a dict in %s, skipping", config_path)
        return []

    servers: list[MCPServerConfig] = []
    for name, entry in servers_dict.items():
        if not isinstance(entry, dict):
            logger.warning("MCP server '%s': entry is not a dict, skipping", name)
            continue

        if "command" in entry:
            servers.append(
                MCPServerConfig(
                    name=name,
                    transport="stdio",
                    command=entry["command"],
                    args=entry.get("args", []),
                    env=entry.get("env", {}),
                )
            )
        elif "url" in entry:
            servers.append(
                MCPServerConfig(
                    name=name,
                    transport="http",
                    url=entry["url"],
                    headers=entry.get("headers", {}),
                )
            )
        else:
            logger.warning("MCP server '%s': no 'command' or 'url' field, skipping", name)

    return servers
