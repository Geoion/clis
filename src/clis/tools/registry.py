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
