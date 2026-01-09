"""
Get file info tool - retrieve file metadata.
"""

import datetime
import hashlib
from pathlib import Path
from typing import Any, Dict

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger
from clis.utils.platform import is_windows

logger = get_logger(__name__)


class GetFileInfoTool(Tool):
    """Get file metadata."""
    
    @property
    def name(self) -> str:
        return "get_file_info"
    
    @property
    def description(self) -> str:
        return "Get file metadata including size, modified time, and permissions."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path"
                },
                "include_hash": {
                    "type": "boolean",
                    "default": False,
                    "description": "Calculate file hash (MD5)"
                }
            },
            "required": ["path"]
        }
    
    def execute(self, path: str, include_hash: bool = False) -> ToolResult:
        """Execute get file info."""
        try:
            path_obj = Path(path)
            
            if not path_obj.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"File does not exist: {path}"
                )
            
            stat = path_obj.stat()
            
            info = []
            info.append(f"Path: {path_obj.absolute()}")
            info.append(f"Type: {'Directory' if path_obj.is_dir() else 'File'}")
            info.append(f"Size: {stat.st_size} bytes ({stat.st_size / 1024:.2f} KB)")
            info.append(f"Modified: {datetime.datetime.fromtimestamp(stat.st_mtime)}")
            info.append(f"Created: {datetime.datetime.fromtimestamp(stat.st_ctime)}")
            
            # Permissions (Unix-style)
            if not is_windows():
                import stat as stat_module
                mode = stat.st_mode
                perms = stat_module.filemode(mode)
                info.append(f"Permissions: {perms}")
            
            # Hash
            if include_hash and path_obj.is_file():
                hash_md5 = hashlib.md5()
                with open(path_obj, "rb") as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        hash_md5.update(chunk)
                info.append(f"MD5: {hash_md5.hexdigest()}")
            
            output = "\n".join(info)
            return ToolResult(success=True, output=output)
        
        except Exception as e:
            logger.error(f"Error getting file info: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error getting file info: {str(e)}"
            )
