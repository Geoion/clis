"""
Delete file tool - safely delete files with confirmation.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class DeleteFileTool(Tool):
    """Delete a file or directory with safety checks."""
    
    @property
    def name(self) -> str:
        return "delete_file"
    
    @property
    def description(self) -> str:
        return "Delete a file or directory. This is a high-risk operation that requires user confirmation."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to file or directory to delete"
                },
                "recursive": {
                    "type": "boolean",
                    "default": False,
                    "description": "Delete directory recursively (required for non-empty directories)"
                },
                "force": {
                    "type": "boolean",
                    "default": False,
                    "description": "Force deletion without additional checks"
                }
            },
            "required": ["path"]
        }
    
    @property
    def is_readonly(self) -> bool:
        """Delete is NOT read-only."""
        return False
    
    @property
    def requires_confirmation(self) -> bool:
        """Delete always requires confirmation."""
        return True
    
    def execute(self, path: str, recursive: bool = False, force: bool = False) -> ToolResult:
        """
        Execute file deletion.
        
        Note: This tool should ALWAYS be called with user confirmation.
        The InteractiveAgent should handle confirmation before calling this.
        """
        try:
            path_obj = Path(path).expanduser().resolve()
            
            # Safety check: file must exist
            if not path_obj.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Path does not exist: {path}"
                )
            
            # Safety check: prevent deleting system directories
            dangerous_paths = [
                Path.home(),
                Path("/"),
                Path("/usr"),
                Path("/etc"),
                Path("/var"),
                Path("/System"),
                Path("C:\\Windows"),
                Path("C:\\Program Files"),
            ]
            
            for dangerous in dangerous_paths:
                try:
                    if path_obj == dangerous or path_obj in dangerous.parents:
                        return ToolResult(
                            success=False,
                            output="",
                            error=f"Cannot delete system directory: {path}"
                        )
                except:
                    pass
            
            # Get file info before deletion
            is_dir = path_obj.is_dir()
            size = 0
            file_count = 0
            
            if is_dir:
                # Count files in directory
                try:
                    file_count = sum(1 for _ in path_obj.rglob("*") if _.is_file())
                    size = sum(f.stat().st_size for f in path_obj.rglob("*") if f.is_file())
                except:
                    pass
            else:
                size = path_obj.stat().st_size
            
            # Perform deletion
            if is_dir:
                if not recursive and any(path_obj.iterdir()):
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"Directory not empty. Use recursive=True to delete: {path}"
                    )
                
                import shutil
                shutil.rmtree(path_obj)
                
                output = f"Deleted directory: {path}\n"
                output += f"Files removed: {file_count}\n"
                output += f"Total size: {size / 1024:.2f} KB"
            else:
                path_obj.unlink()
                output = f"Deleted file: {path}\n"
                output += f"Size: {size / 1024:.2f} KB"
            
            return ToolResult(
                success=True,
                output=output,
                metadata={
                    "path": str(path_obj),
                    "is_dir": is_dir,
                    "size": size,
                    "file_count": file_count if is_dir else 1
                }
            )
        
        except PermissionError:
            return ToolResult(
                success=False,
                output="",
                error=f"Permission denied: {path}"
            )
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error deleting file: {str(e)}"
            )
