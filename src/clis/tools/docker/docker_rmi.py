"""
Docker rmi tool - remove Docker images.
"""

import subprocess
from typing import Any, Dict, List, Union

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class DockerRmiTool(Tool):
    """Remove Docker images."""
    
    @property
    def name(self) -> str:
        return "docker_rmi"
    
    @property
    def description(self) -> str:
        return "Remove one or more Docker images by image ID or repository:tag."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "images": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of image IDs or repository:tag to remove"
                },
                "force": {
                    "type": "boolean",
                    "default": False,
                    "description": "Force removal of the image"
                }
            },
            "required": ["images"]
        }
    
    @property
    def is_readonly(self) -> bool:
        """This modifies the system by removing images."""
        return False
    
    @property
    def risk_score(self) -> int:
        """Removing images is medium risk."""
        return 50
    
    @property
    def requires_confirmation(self) -> bool:
        """Image removal requires confirmation."""
        return True
    
    def execute(
        self,
        images: Union[List[str], str],
        force: bool = False
    ) -> ToolResult:
        """Execute docker rmi."""
        try:
            # Ensure images is a list
            if isinstance(images, str):
                images = [images]
            
            if not images:
                return ToolResult(
                    success=False,
                    output="",
                    error="No images specified"
                )
            
            cmd = ["docker", "rmi"]
            
            if force:
                cmd.append("--force")
            
            cmd.extend(images)
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                return ToolResult(
                    success=True,
                    output=result.stdout,
                    metadata={"removed_images": images}
                )
            else:
                return ToolResult(
                    success=False,
                    output=result.stdout,
                    error=result.stderr or "Docker rmi command failed"
                )
        
        except Exception as e:
            logger.error(f"Error removing Docker images: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error removing Docker images: {str(e)}"
            )
