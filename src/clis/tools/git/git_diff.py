"""
Git diff tool - show git diffs.
"""

import subprocess
from typing import Any, Dict, Optional

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class GitDiffTool(Tool):
    """Show git diff for files or commits."""
    
    @property
    def name(self) -> str:
        return "git_diff"
    
    @property
    def description(self) -> str:
        return "Show git diff to see changes in files. Can show unstaged, staged, or specific file diffs."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file": {
                    "type": "string",
                    "description": "Specific file path to show diff for (relative to git root)"
                },
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Multiple file paths to show diff for (alternative to 'file')"
                },
                "staged": {
                    "type": "boolean",
                    "default": False,
                    "description": "Show staged changes (--cached)"
                },
                "commit": {
                    "type": "string",
                    "description": "Compare with specific commit hash"
                },
                "unified": {
                    "type": "integer",
                    "default": 3,
                    "description": "Number of context lines"
                }
            },
            "required": []
        }
    
    def execute(self, file: Optional[str] = None, files: Optional[list] = None, 
                staged: bool = False, commit: Optional[str] = None, unified: int = 3) -> ToolResult:
        """Execute git diff."""
        try:
            cmd = ["git", "diff", f"-U{unified}"]
            
            if staged:
                cmd.append("--cached")
            
            if commit:
                cmd.append(commit)
            
            # Support both 'file' (singular) and 'files' (plural)
            if files:
                # If 'files' is provided, use the first file
                if isinstance(files, list) and len(files) > 0:
                    file = files[0]
            
            if file:
                cmd.append("--")
                cmd.append(file)
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                output = result.stdout if result.stdout else "No differences found"
                return ToolResult(
                    success=True,
                    output=output
                )
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=result.stderr or "Git diff failed. Are you in a git repository?"
                )
        except Exception as e:
            logger.error(f"Error running git diff: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error running git diff: {str(e)}"
            )
