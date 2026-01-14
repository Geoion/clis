"""
Docker images tool - list Docker images.
"""

import subprocess
from typing import Any, Dict, Optional

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class DockerImagesTool(Tool):
    """List Docker images."""
    
    @property
    def name(self) -> str:
        return "docker_images"
    
    @property
    def description(self) -> str:
        return "List Docker images with details (repository, tag, image ID, size)."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "all": {
                    "type": "boolean",
                    "default": False,
                    "description": "Show all images (including intermediate images)"
                },
                "filter": {
                    "type": "string",
                    "description": "Filter output based on conditions (e.g., 'dangling=true' for <none> images)"
                },
                "format": {
                    "type": "string",
                    "description": "Format output using Go template (e.g., 'table' or '{{.ID}}\t{{.Repository}}')"
                }
            }
        }
    
    @property
    def is_readonly(self) -> bool:
        """This is a read-only operation."""
        return True
    
    @property
    def risk_score(self) -> int:
        """Docker images is a safe read-only command."""
        return 0
    
    def execute(
        self,
        all: bool = False,
        filter: Optional[str] = None,
        format: Optional[str] = None
    ) -> ToolResult:
        """Execute docker images."""
        try:
            cmd = ["docker", "images"]
            
            if all:
                cmd.append("--all")
            
            if filter:
                cmd.extend(["--filter", filter])
            
            if format:
                cmd.extend(["--format", format])
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                return ToolResult(success=True, output=result.stdout)
            else:
                error_msg = result.stderr.strip() if result.stderr else "Docker images command failed"
                return ToolResult(
                    success=False,
                    output="",
                    error=error_msg
                )
        
        except Exception as e:
            logger.error(f"Error listing Docker images: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error listing Docker images: {str(e)}"
            )
