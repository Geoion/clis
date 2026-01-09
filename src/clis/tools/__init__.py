"""
Tool calling system for CLIS.

Enables LLM to actively call tools to gather information and execute commands.
"""

from clis.tools.base import Tool, ToolResult, ToolExecutor
from clis.tools.registry import ToolRegistry
from clis.tools.builtin import (
    ListFilesTool,
    ReadFileTool,
    ExecuteCommandTool,
    GitStatusTool,
    DockerPsTool,
)

__all__ = [
    "Tool",
    "ToolResult",
    "ToolExecutor",
    "ToolRegistry",
    "ListFilesTool",
    "ReadFileTool",
    "ExecuteCommandTool",
    "GitStatusTool",
    "DockerPsTool",
]
