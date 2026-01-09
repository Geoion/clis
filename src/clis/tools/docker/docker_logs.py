"""
Docker logs tool - get container logs.
"""

import subprocess
from typing import Any, Dict, Optional

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class DockerLogsTool(Tool):
    """Get logs from Docker containers."""
    
    @property
    def name(self) -> str:
        return "docker_logs"
    
    @property
    def description(self) -> str:
        return "Get logs from a Docker container. Essential for debugging."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "container": {
                    "type": "string",
                    "description": "Container name or ID"
                },
                "tail": {
                    "type": "integer",
                    "default": 100,
                    "description": "Number of lines to show from end"
                },
                "since": {
                    "type": "string",
                    "description": "Show logs since timestamp (e.g., '1h', '30m')"
                },
                "timestamps": {
                    "type": "boolean",
                    "default": True,
                    "description": "Show timestamps"
                }
            },
            "required": ["container"]
        }
    
    def execute(self, container: str, tail: int = 100, since: Optional[str] = None,
                timestamps: bool = True) -> ToolResult:
        """Execute docker logs."""
        try:
            cmd = ["docker", "logs", f"--tail={tail}"]
            
            if timestamps:
                cmd.append("--timestamps")
            
            if since:
                cmd.append(f"--since={since}")
            
            cmd.append(container)
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                # Docker logs can go to stdout or stderr
                output = result.stdout or result.stderr
                if not output:
                    output = f"No logs found for container: {container}"
                
                return ToolResult(
                    success=True,
                    output=output,
                    metadata={"lines": len(output.split('\n'))}
                )
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=result.stderr or f"Container not found: {container}"
                )
                
        except Exception as e:
            logger.error(f"Error getting Docker logs: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error getting Docker logs: {str(e)}"
            )
