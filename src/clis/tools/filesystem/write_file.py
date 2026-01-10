"""
Write file tool - write or append content to files.
"""

from pathlib import Path
from typing import Any, Dict

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class WriteFileTool(Tool):
    """Write content to a file."""
    
    @property
    def name(self) -> str:
        return "write_file"
    
    @property
    def description(self) -> str:
        return "Write or append content to a file. Creates parent directories if needed. USE WITH CAUTION - modifies files!"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write"
                },
                "mode": {
                    "type": "string",
                    "enum": ["write", "append"],
                    "default": "write",
                    "description": "Write mode: write (overwrite) or append"
                }
            },
            "required": ["path", "content"]
        }
    
    @property
    def is_readonly(self) -> bool:
        """Write operations modify files, so not readonly."""
        return False
    
    def execute(self, path: str, content: str, mode: str = "write") -> ToolResult:
        """Execute write file."""
        try:
            path_obj = Path(path)
            
            # Create parent directories
            path_obj.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            write_mode = 'a' if mode == "append" else 'w'
            with open(path_obj, write_mode, encoding='utf-8') as f:
                f.write(content)
            
            action = "Appended to" if mode == "append" else "Wrote to"
            return ToolResult(
                success=True,
                output=f"{action} file: {path}\nBytes written: {len(content)}",
                metadata={"path": str(path_obj), "size": len(content)}
            )
        
        except Exception as e:
            logger.error(f"Error writing file: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error writing file: {str(e)}"
            )
