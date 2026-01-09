"""
Docker inspect tool - get detailed container information.
"""

import json
import subprocess
from typing import Any, Dict, Optional

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class DockerInspectTool(Tool):
    """Get detailed Docker container information."""
    
    @property
    def name(self) -> str:
        return "docker_inspect"
    
    @property
    def description(self) -> str:
        return "Get detailed information about a Docker container or image."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Container or image name/ID"
                },
                "format": {
                    "type": "string",
                    "description": "Go template format string (optional)"
                }
            },
            "required": ["target"]
        }
    
    def execute(self, target: str, format: Optional[str] = None) -> ToolResult:
        """Execute docker inspect."""
        try:
            cmd = ["docker", "inspect"]
            
            if format:
                cmd.extend(["--format", format])
            
            cmd.append(target)
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                # Try to pretty-print JSON
                try:
                    data = json.loads(result.stdout)
                    output = json.dumps(data, indent=2)
                except:
                    output = result.stdout
                
                return ToolResult(success=True, output=output)
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=result.stderr or f"Target not found: {target}"
                )
        
        except Exception as e:
            logger.error(f"Error inspecting Docker target: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error inspecting Docker target: {str(e)}"
            )
