"""
Git push tool.
"""

import subprocess
from typing import Any, Dict

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class GitPushTool(Tool):
    """Push commits to remote repository."""
    
    @property
    def name(self) -> str:
        return "git_push"
    
    @property
    def description(self) -> str:
        return (
            "Push commits to remote repository. Can push to specific branch and remote. "
            "Supports setting upstream branch for first push. "
            "WARNING: Use --force with extreme caution!"
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
                "set_upstream": {
                    "type": "boolean",
                    "description": "Set upstream branch (use for first push, default: false)",
                    "default": False
                },
                "force": {
                    "type": "boolean",
                    "description": "Force push (DANGEROUS! default: false)",
                    "default": False
                }
            },
            "required": []
        }
    
    @property
    def is_readonly(self) -> bool:
        return False  # Write operation
    
    @property
    def risk_score(self) -> int:
        """Git push is high risk - affects remote repository."""
        return 70
    
    @property
    def requires_confirmation(self) -> bool:
        """Git push always requires confirmation."""
        return True
    
    def execute(
        self,
        remote: str = "origin",
        branch: str = "",
        set_upstream: bool = False,
        force: bool = False
    ) -> ToolResult:
        """
        Execute git push.
        
        Args:
            remote: Remote name
            branch: Branch name
            set_upstream: Set upstream branch
            force: Force push
            
        Returns:
            ToolResult with push result
        """
        try:
            # Build command
            cmd = ["git", "push"]
            
            if set_upstream:
                cmd.append("--set-upstream")
            
            if force:
                cmd.append("--force")
            
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
                output = "✓ Push successful\n\n"
                output += result.stdout or result.stderr
                
                return ToolResult(
                    success=True,
                    output=output.strip(),
                    metadata={"remote": remote, "branch": branch}
                )
            else:
                error_msg = result.stderr or result.stdout
                
                # Check for common errors
                if "rejected" in error_msg.lower():
                    error_msg += "\n\nHint: The remote contains work that you don't have locally. "
                    error_msg += "Try 'git pull' first, or use 'force=true' to force push (not recommended)."
                elif "no upstream branch" in error_msg.lower():
                    error_msg += "\n\nHint: Use 'set_upstream=true' to set the upstream branch."
                
                return ToolResult(
                    success=False,
                    output="",
                    error=error_msg.strip()
                )
        
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                output="",
                error="Push timed out after 60 seconds"
            )
        except Exception as e:
            logger.error(f"Error pushing: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error pushing: {str(e)}"
            )
