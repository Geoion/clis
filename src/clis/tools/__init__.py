"""
Tool calling system for CLIS.

Enables LLM to actively call tools to gather information and execute commands.
"""

# Core
from clis.tools.base import Tool, ToolResult, ToolExecutor
from clis.tools.registry import ToolRegistry

# Built-in tools (Phase 0)
from clis.tools.builtin import (
    ListFilesTool,
    ReadFileTool,
    ExecuteCommandTool,
    GitStatusTool,
    DockerPsTool,
)

# Filesystem tools
from clis.tools.filesystem import (
    DeleteFileTool,
    SearchFilesTool,
    FileTreeTool,
    WriteFileTool,
    GetFileInfoTool,
)

# File chunking
from clis.tools.filesystem.file_chunker import (
    FileChunker,
    FileChunk,
    MODEL_PRESETS,
    get_model_preset,
)

# Git tools
from clis.tools.git import (
    GitAddTool,
    GitCommitTool,
    GitDiffTool,
    GitLogTool,
)

# Docker tools
from clis.tools.docker import (
    DockerLogsTool,
    DockerInspectTool,
    DockerStatsTool,
)

# System tools
from clis.tools.system import (
    SystemInfoTool,
    CheckCommandTool,
    GetEnvTool,
    ListProcessesTool,
)

# Network tools
from clis.tools.network import (
    HttpRequestTool,
    CheckPortTool,
)

__all__ = [
    # Core
    "Tool",
    "ToolResult",
    "ToolExecutor",
    "ToolRegistry",
    # Built-in (Phase 0)
    "ListFilesTool",
    "ReadFileTool",
    "ExecuteCommandTool",
    "GitStatusTool",
    "DockerPsTool",
    # Filesystem
    "DeleteFileTool",
    "SearchFilesTool",
    "FileTreeTool",
    "WriteFileTool",
    "GetFileInfoTool",
    # File chunking
    "FileChunker",
    "FileChunk",
    "MODEL_PRESETS",
    "get_model_preset",
    # Git
    "GitAddTool",
    "GitCommitTool",
    "GitDiffTool",
    "GitLogTool",
    # Docker
    "DockerLogsTool",
    "DockerInspectTool",
    "DockerStatsTool",
    # System
    "SystemInfoTool",
    "CheckCommandTool",
    "GetEnvTool",
    "ListProcessesTool",
    # Network
    "HttpRequestTool",
    "CheckPortTool",
]
