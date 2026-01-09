"""
Get environment variable tool.
"""

import os
from typing import Any, Dict, Optional

from clis.tools.base import Tool, ToolResult


class GetEnvTool(Tool):
    """Get environment variable value."""
    
    @property
    def name(self) -> str:
        return "get_env"
    
    @property
    def description(self) -> str:
        return "Get environment variable value. Useful for configuration checks."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Environment variable name"
                },
                "default": {
                    "type": "string",
                    "description": "Default value if variable is not set"
                }
            },
            "required": ["name"]
        }
    
    def execute(self, name: str, default: Optional[str] = None) -> ToolResult:
        """Execute get env."""
        try:
            value = os.environ.get(name, default)
            
            if value is None:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Environment variable '{name}' is not set"
                )
            
            return ToolResult(
                success=True,
                output=f"{name}={value}",
                metadata={"name": name, "value": value}
            )
        
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Error getting environment variable: {str(e)}"
            )
