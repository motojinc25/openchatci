"""MCP tool provider factory (CTR-0060, PRP-0031).

Creates MAF MCPStdioTool / MCPStreamableHTTPTool instances from parsed
MCP server configurations. Tool instances are returned unstarted; the
lifecycle module (CTR-0061) handles startup via AsyncExitStack.
"""

import logging

from agent_framework import MCPStdioTool, MCPStreamableHTTPTool

from app.mcp.config import MCPServerConfig

logger = logging.getLogger(__name__)


def create_mcp_tool(server: MCPServerConfig) -> MCPStdioTool | MCPStreamableHTTPTool:
    """Create a single MAF MCP tool instance from config.

    Args:
        server: Parsed MCP server configuration.

    Returns:
        MCPStdioTool or MCPStreamableHTTPTool instance (not yet started).
    """
    if server.transport == "stdio":
        tool = MCPStdioTool(
            name=server.name,
            command=server.command,
            args=server.args,
            env=server.env or None,
        )
        logger.debug("MCPStdioTool created: %s (command=%s)", server.name, server.command)
        return tool

    # http transport
    tool = MCPStreamableHTTPTool(
        name=server.name,
        url=server.url,
        headers=server.headers or None,
    )
    logger.debug("MCPStreamableHTTPTool created: %s (url=%s)", server.name, server.url)
    return tool
