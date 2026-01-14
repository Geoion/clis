"""
Base classes for tool calling system.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from clis.tools.base import Tool


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
    
    @property
    def is_readonly(self) -> bool:
        """
        Whether this tool is read-only (safe to execute in parallel).
        
        Read-only tools don't modify system state and can be executed
        concurrently. Write tools modify state and must be executed serially.
        
        Returns:
            True if tool is read-only, False otherwise
        """
        return True  # Default to read-only for safety
    
    @property
    def risk_score(self) -> int:
        """
        Base risk score for this tool (0-100).
        
        This provides a baseline risk level that can be adjusted based on
        parameters during execution. High-risk tools should override this.
        
        Scoring guide:
        - 0-30: Low risk (read-only operations)
        - 31-60: Medium risk (write operations)
        - 61-90: High risk (destructive operations)
        - 91-100: Critical risk (system-level operations)
        
        Returns:
            Risk score (0-100)
        """
        # Default: low risk if readonly, medium risk if not
        return 10 if self.is_readonly else 50
    
    @property
    def requires_confirmation(self) -> bool:
        """
        Whether this tool requires user confirmation before execution.
        
        Tools that modify state or perform risky operations should
        require confirmation. The actual confirmation logic uses both
        this property and dynamic risk scoring.
        
        Returns:
            True if confirmation is required
        """
        # Default: require confirmation for non-readonly tools
        return not self.is_readonly
    
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
            "parameters": self.parameters,
            "is_readonly": self.is_readonly
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
    
    def get_tool(self, tool_name: str) -> Optional[Tool]:
        """
        Get a tool by name.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Tool instance or None if not found
        """
        return self.tools.get(tool_name)
    
    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get all tool definitions for LLM."""
        return [tool.to_dict() for tool in self.tools.values()]
