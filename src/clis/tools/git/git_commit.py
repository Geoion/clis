"""
Git commit tool - commit staged changes.
"""

import subprocess
from typing import Any, Dict, Optional

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class GitCommitTool(Tool):
    """Commit staged changes to git repository."""
    
    @property
    def name(self) -> str:
        return "git_commit"
    
    @property
    def description(self) -> str:
        return "Commit staged changes with a commit message. Use after git_add to commit changes."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Commit message describing the changes"
                },
                "amend": {
                    "type": "boolean",
                    "default": False,
                    "description": "Amend the previous commit"
                }
            },
            "required": ["message"]
        }
    
    @property
    def is_readonly(self) -> bool:
        """Git commit modifies repository history, so not read-only."""
        return False
    
    @property
    def risk_score(self) -> int:
        """Git commit is medium risk - creates permanent history."""
        return 50
    
    def execute(self, message: str, amend: bool = False) -> ToolResult:
        """Execute git commit."""
        try:
            if not message:
                return ToolResult(
                    success=False,
                    output="",
                    error="Commit message is required"
                )
            
            cmd = ["git", "commit", "-m", message]
            
            if amend:
                cmd.append("--amend")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                output = result.stdout if result.stdout else "Commit successful"
                return ToolResult(
                    success=True,
                    output=output
                )
            else:
                error_msg = result.stderr or "Git commit failed"
                # Check for common errors
                if "nothing to commit" in error_msg.lower():
                    error_msg = "Nothing to commit. Use git_add to stage changes first."
                
                return ToolResult(
                    success=False,
                    output="",
                    error=error_msg
                )
        except Exception as e:
            logger.error(f"Error running git commit: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error running git commit: {str(e)}"
            )
