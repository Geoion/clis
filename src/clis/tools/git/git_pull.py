"""
Git pull tool.
"""

import subprocess
from typing import Any, Dict

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class GitPullTool(Tool):
    """Pull changes from remote repository."""
    
    @property
    def name(self) -> str:
        return "git_pull"
    
    @property
    def description(self) -> str:
        return (
            "Pull changes from remote repository. Fetches and merges changes from remote branch. "
            "Can specify remote and branch. Supports rebase mode."
        )
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "remote": {
                    "type": "string",
                    "description": "Remote name (default: origin)",
                    "default": "origin"
                },
                "branch": {
                    "type": "string",
                    "description": "Branch name (default: current branch)",
                    "default": ""
                },
                "rebase": {
                    "type": "boolean",
                    "description": "Use rebase instead of merge (default: false)",
                    "default": False
                }
            },
            "required": []
        }
    
    @property
    def is_readonly(self) -> bool:
        return False  # Write operation (modifies working directory)
    
    def execute(
        self,
        remote: str = "origin",
        branch: str = "",
        rebase: bool = False
    ) -> ToolResult:
        """
        Execute git pull.
        
        Args:
            remote: Remote name
            branch: Branch name
            rebase: Use rebase
            
        Returns:
            ToolResult with pull result
        """
        try:
            # Build command
            cmd = ["git", "pull"]
            
            if rebase:
                cmd.append("--rebase")
            
            cmd.append(remote)
            
            if branch:
                cmd.append(branch)
            
            # Execute
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                output = "✓ Pull successful\n\n"
                output += result.stdout or result.stderr
                
                return ToolResult(
                    success=True,
                    output=output.strip(),
                    metadata={"remote": remote, "branch": branch}
                )
            else:
                error_msg = result.stderr or result.stdout
                
                # Check for common errors
                if "conflict" in error_msg.lower():
                    error_msg += "\n\nHint: There are merge conflicts. Resolve them manually and commit."
                elif "uncommitted changes" in error_msg.lower():
                    error_msg += "\n\nHint: You have uncommitted changes. Commit or stash them first."
                
                return ToolResult(
                    success=False,
                    output="",
                    error=error_msg.strip()
                )
        
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                output="",
                error="Pull timed out after 60 seconds"
            )
        except Exception as e:
            logger.error(f"Error pulling: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error pulling: {str(e)}"
            )
