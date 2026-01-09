"""
Docker stats tool - get container resource usage.
"""

import subprocess
from typing import Any, Dict, Optional

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class DockerStatsTool(Tool):
    """Get Docker container resource usage statistics."""
    
    @property
    def name(self) -> str:
        return "docker_stats"
    
    @property
    def description(self) -> str:
        return "Get resource usage statistics for Docker containers (CPU, memory, network, disk)."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "container": {
                    "type": "string",
                    "description": "Container name/ID (optional, default: all containers)"
                },
                "no_stream": {
                    "type": "boolean",
                    "default": True,
                    "description": "Return stats once without streaming"
                }
            }
        }
    
    def execute(self, container: Optional[str] = None, no_stream: bool = True) -> ToolResult:
        """Execute docker stats."""
        try:
            cmd = ["docker", "stats", "--no-trunc"]
            
            if no_stream:
                cmd.append("--no-stream")
            
            if container:
                cmd.append(container)
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                return ToolResult(success=True, output=result.stdout)
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=result.stderr or "Docker stats failed"
                )
        
        except Exception as e:
            logger.error(f"Error getting Docker stats: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error getting Docker stats: {str(e)}"
            )
