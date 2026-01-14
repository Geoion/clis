"""
Git add tool - stage files for commit.
"""

import subprocess
from typing import Any, Dict, List, Optional, Union

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class GitAddTool(Tool):
    """Stage files for git commit."""
    
    @property
    def name(self) -> str:
        return "git_add"
    
    @property
    def description(self) -> str:
        return "Stage files for git commit. Can add single file, multiple files, or all changes."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of file paths to stage (relative to git root)"
                },
                "all": {
                    "type": "boolean",
                    "default": False,
                    "description": "Stage all changes (git add -A)"
                }
            },
            "required": []
        }
    
    @property
    def is_readonly(self) -> bool:
        """Git add modifies the index, so not read-only."""
        return False
    
    @property
    def risk_score(self) -> int:
        """Git add is medium risk - stages changes."""
        return 50
    
    def execute(self, files: Optional[List[str]] = None, all: bool = False) -> ToolResult:
        """Execute git add."""
        try:
            if all:
                cmd = ["git", "add", "-A"]
            elif files:
                cmd = ["git", "add"] + files
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error="Must specify either 'files' or 'all=True'"
                )
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                if all:
                    output = "Successfully staged all changes"
                else:
                    output = f"Successfully staged: {', '.join(files)}"
                
                return ToolResult(
                    success=True,
                    output=output
                )
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=result.stderr or "Git add failed"
                )
        except Exception as e:
            logger.error(f"Error running git add: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error running git add: {str(e)}"
            )
