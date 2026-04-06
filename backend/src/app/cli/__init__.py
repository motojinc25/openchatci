"""CLI package for OpenChatCi (CTR-0033 v3).

Re-exports main() to preserve the app.cli:main entry point
defined in pyproject.toml [project.scripts].
"""

from app.cli.main import main
