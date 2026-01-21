"""
Tool registry for managing available tools.
"""

from typing import Dict, List, Optional

from clis.tools.base import Tool


class ToolRegistry:
    """Registry for managing available tools."""
    
    def __init__(self):
        """Initialize tool registry."""
        self._tools: Dict[str, Tool] = {}
    
    def register(self, tool: Tool) -> None:
        """
        Register a tool.
        
        Args:
            tool: Tool to register
        """
        self._tools[tool.name] = tool
    
    def unregister(self, tool_name: str) -> None:
        """
        Unregister a tool.
        
        Args:
            tool_name: Name of tool to unregister
        """
        if tool_name in self._tools:
            del self._tools[tool_name]
    
    def get(self, tool_name: str) -> Optional[Tool]:
        """
        Get a tool by name.
        
        Args:
            tool_name: Name of tool
            
        Returns:
            Tool if found, None otherwise
        """
        return self._tools.get(tool_name)
    
    def list_tools(self) -> List[Tool]:
        """
        List all registered tools.
        
        Returns:
            List of all tools
        """
        return list(self._tools.values())
    
    def get_tool_definitions(self) -> List[Dict]:
        """
        Get tool definitions for LLM.
        
        Returns:
            List of tool definitions
        """
        return [tool.to_dict() for tool in self._tools.values()]


# Global registry instance
_global_registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    """Get the global tool registry."""
    return _global_registry


def get_all_tools():
    """
    Get list of all available tool instances
    
    Returns:
        List containing all tool instances
    """
    # Builtin tools
    from clis.tools.builtin import (
        ListFilesTool, ReadFileTool, ExecuteCommandTool,
        GitStatusTool, DockerPsTool
    )
    
    # Filesystem tools
    from clis.tools.filesystem.write_file import WriteFileTool
    from clis.tools.filesystem.edit_file import EditFileTool
    from clis.tools.filesystem.delete_file import DeleteFileTool
    from clis.tools.filesystem.search_replace import SearchReplaceTool
    from clis.tools.filesystem.insert_code import InsertCodeTool
    from clis.tools.filesystem.delete_lines import DeleteLinesTool
    from clis.tools.filesystem.grep import GrepTool
    from clis.tools.filesystem.search_files import SearchFilesTool
    from clis.tools.filesystem.file_tree import FileTreeTool
    from clis.tools.filesystem.get_file_info import GetFileInfoTool
    from clis.tools.filesystem.read_lints import ReadLintsTool
    from clis.tools.filesystem.codebase_search import CodebaseSearchTool
    from clis.tools.filesystem.find_definition import FindDefinitionTool
    from clis.tools.filesystem.find_references import FindReferencesTool
    from clis.tools.filesystem.get_symbols import GetSymbolsTool
    
    # System tools
    from clis.tools.system.system_info import SystemInfoTool
    from clis.tools.system.check_command import CheckCommandTool
    from clis.tools.system.get_env import GetEnvTool
    from clis.tools.system.list_processes import ListProcessesTool
    from clis.tools.system.start_service import StartServiceTool
    from clis.tools.system.list_terminals import ListTerminalsTool
    from clis.tools.system.read_terminal_output import ReadTerminalOutputTool
    
    # Git tools
    from clis.tools.git.git_diff import GitDiffTool
    from clis.tools.git.git_log import GitLogTool
    from clis.tools.git.git_add import GitAddTool
    from clis.tools.git.git_commit import GitCommitTool
    from clis.tools.git.git_push import GitPushTool
    from clis.tools.git.git_pull import GitPullTool
    from clis.tools.git.git_branch import GitBranchTool
    from clis.tools.git.git_checkout import GitCheckoutTool
    
    # Docker tools
    from clis.tools.docker.docker_inspect import DockerInspectTool
    from clis.tools.docker.docker_logs import DockerLogsTool
    from clis.tools.docker.docker_stats import DockerStatsTool
    from clis.tools.docker.docker_images import DockerImagesTool
    from clis.tools.docker.docker_rmi import DockerRmiTool
    
    # Network tools
    from clis.tools.network.http_request import HttpRequestTool
    from clis.tools.network.check_port import CheckPortTool
    
    return [
        # Builtin (5 tools)
        ListFilesTool(), ReadFileTool(), ExecuteCommandTool(),
        GitStatusTool(), DockerPsTool(),
        
        # Filesystem (17 tools)
        WriteFileTool(), EditFileTool(), DeleteFileTool(),
        SearchReplaceTool(), InsertCodeTool(), DeleteLinesTool(),
        GrepTool(), SearchFilesTool(), FileTreeTool(),
        GetFileInfoTool(), ReadLintsTool(), CodebaseSearchTool(),
        FindDefinitionTool(), FindReferencesTool(), GetSymbolsTool(),
        
        # System (7 tools)
        SystemInfoTool(), CheckCommandTool(), GetEnvTool(),
        ListProcessesTool(), StartServiceTool(),
        ListTerminalsTool(), ReadTerminalOutputTool(),
        
        # Git (8 tools)
        GitDiffTool(), GitLogTool(), GitAddTool(), GitCommitTool(),
        GitPushTool(), GitPullTool(), GitBranchTool(), GitCheckoutTool(),
        
        # Docker (5 tools)
        DockerInspectTool(), DockerLogsTool(), DockerStatsTool(),
        DockerImagesTool(), DockerRmiTool(),
        
        # Network (2 tools)
        HttpRequestTool(), CheckPortTool()
    ]
