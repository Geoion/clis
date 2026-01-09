"""
Check command tool - verify command availability.
"""

import shutil
import subprocess
from typing import Any, Dict

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class CheckCommandTool(Tool):
    """Check if a command is available."""
    
    @property
    def name(self) -> str:
        return "check_command"
    
    @property
    def description(self) -> str:
        return "Check if a command/tool is installed and available in PATH. Optionally get version."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Command name to check"
                },
                "get_version": {
                    "type": "boolean",
                    "default": True,
                    "description": "Try to get version information"
                }
            },
            "required": ["command"]
        }
    
    def execute(self, command: str, get_version: bool = True) -> ToolResult:
        """Execute command check."""
        try:
            # Check if command exists
            cmd_path = shutil.which(command)
            
            if not cmd_path:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Command '{command}' not found in PATH"
                )
            
            output = f"Command '{command}' found at: {cmd_path}"
            
            # Try to get version
            if get_version:
                version_flags = ["--version", "-version", "-v", "version"]
                version_info = None
                
                for flag in version_flags:
                    try:
                        result = subprocess.run(
                            [command, flag],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        if result.returncode == 0 and result.stdout:
                            version_info = result.stdout.split('\n')[0]
                            break
                    except:
                        continue
                
                if version_info:
                    output += f"\nVersion: {version_info}"
                else:
                    output += "\nVersion: (unable to determine)"
            
            return ToolResult(
                success=True,
                output=output,
                metadata={"path": cmd_path}
            )
        
        except Exception as e:
            logger.error(f"Error checking command: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error checking command: {str(e)}"
            )
