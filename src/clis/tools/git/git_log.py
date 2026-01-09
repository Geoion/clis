"""
Git log tool - show commit history.
"""

import subprocess
from typing import Any, Dict, Optional

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class GitLogTool(Tool):
    """Get git commit history."""
    
    @property
    def name(self) -> str:
        return "git_log"
    
    @property
    def description(self) -> str:
        return "Get git commit history with various filters."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "max_count": {
                    "type": "integer",
                    "default": 10,
                    "description": "Maximum number of commits to show"
                },
                "author": {
                    "type": "string",
                    "description": "Filter by author"
                },
                "since": {
                    "type": "string",
                    "description": "Show commits since date (e.g., '1 week ago', '2023-01-01')"
                },
                "file": {
                    "type": "string",
                    "description": "Show commits that modified this file"
                },
                "oneline": {
                    "type": "boolean",
                    "default": True,
                    "description": "Show one line per commit"
                }
            }
        }
    
    def execute(self, max_count: int = 10, author: Optional[str] = None,
                since: Optional[str] = None, file: Optional[str] = None,
                oneline: bool = True) -> ToolResult:
        """Execute git log."""
        try:
            cmd = ["git", "log", f"-{max_count}"]
            
            if oneline:
                cmd.append("--oneline")
            
            if author:
                cmd.append(f"--author={author}")
            
            if since:
                cmd.append(f"--since={since}")
            
            if file:
                cmd.append("--")
                cmd.append(file)
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                output = result.stdout if result.stdout else "No commits found"
                return ToolResult(success=True, output=output)
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=result.stderr or "Git log failed"
                )
        
        except Exception as e:
            logger.error(f"Error running git log: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error running git log: {str(e)}"
            )
