"""
Check port tool - verify port availability.
"""

import socket
from typing import Any, Dict

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class CheckPortTool(Tool):
    """Check if a port is open."""
    
    @property
    def name(self) -> str:
        return "check_port"
    
    @property
    def description(self) -> str:
        return "Check if a port is open/listening on a host."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "port": {
                    "type": "integer",
                    "description": "Port number to check"
                },
                "host": {
                    "type": "string",
                    "default": "localhost",
                    "description": "Host to check"
                },
                "timeout": {
                    "type": "integer",
                    "default": 5,
                    "description": "Connection timeout in seconds"
                }
            },
            "required": ["port"]
        }
    
    def execute(self, port: int, host: str = "localhost", timeout: int = 5) -> ToolResult:
        """Execute port check."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result == 0:
                return ToolResult(
                    success=True,
                    output=f"Port {port} is OPEN on {host}",
                    metadata={"host": host, "port": port, "status": "open"}
                )
            else:
                return ToolResult(
                    success=True,
                    output=f"Port {port} is CLOSED on {host}",
                    metadata={"host": host, "port": port, "status": "closed"}
                )
        
        except Exception as e:
            logger.error(f"Error checking port: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error checking port: {str(e)}"
            )
