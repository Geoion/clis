"""
Base classes for tool calling system.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ToolResult:
    """Tool execution result."""
    
    success: bool
    output: str
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata or {}
        }


class Tool(ABC):
    """Base class for tools."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description."""
        pass
    
    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        """Tool parameters schema (JSON Schema format)."""
        pass
    
    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """
        Execute the tool.
        
        Args:
            **kwargs: Tool parameters
            
        Returns:
            ToolResult with execution result
        """
        pass
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert tool to dictionary format for LLM."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }


class ToolExecutor:
    """Executes tools safely."""
    
    def __init__(self, tools: List[Tool]):
        """
        Initialize tool executor.
        
        Args:
            tools: List of available tools
        """
        self.tools = {tool.name: tool for tool in tools}
    
    def execute(self, tool_name: str, parameters: Dict[str, Any]) -> ToolResult:
        """
        Execute a tool.
        
        Args:
            tool_name: Name of the tool to execute
            parameters: Tool parameters
            
        Returns:
            ToolResult with execution result
        """
        if tool_name not in self.tools:
            return ToolResult(
                success=False,
                output="",
                error=f"Tool '{tool_name}' not found"
            )
        
        tool = self.tools[tool_name]
        
        try:
            result = tool.execute(**parameters)
            return result
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Tool execution failed: {str(e)}"
            )
    
    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get all tool definitions for LLM."""
        return [tool.to_dict() for tool in self.tools.values()]
