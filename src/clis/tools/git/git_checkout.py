"""
Git checkout tool.
"""

import subprocess
from typing import Any, Dict

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class GitCheckoutTool(Tool):
    """Switch branches or restore files."""
    
    @property
    def name(self) -> str:
        return "git_checkout"
    
    @property
    def description(self) -> str:
        return (
            "Switch to a different branch or restore files. "
            "Can create and switch to new branch in one command. "
            "Can also restore specific files to their last committed state."
        )
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "branch": {
                    "type": "string",
                    "description": "Branch name to switch to",
                    "default": ""
                },
                "create_new": {
                    "type": "boolean",
                    "description": "Create new branch and switch to it (default: false)",
                    "default": False
                },
                "file_path": {
                    "type": "string",
                    "description": "File path to restore (leave empty to switch branches)",
                    "default": ""
                }
            },
            "required": []
        }
    
    @property
    def is_readonly(self) -> bool:
        return False  # Modifies working directory
    
    @property
    def risk_score(self) -> int:
        """Git checkout is high risk - can discard uncommitted changes."""
        return 70
    
    @property
    def requires_confirmation(self) -> bool:
        """Git checkout requires confirmation as it can discard changes."""
        return True
    
    def execute(
        self,
        branch: str = "",
        create_new: bool = False,
        file_path: str = ""
    ) -> ToolResult:
        """
        Execute git checkout.
        
        Args:
            branch: Branch name
            create_new: Create new branch
            file_path: File to restore
            
        Returns:
            ToolResult with checkout result
        """
        try:
            # Check if restoring file or switching branch
            if file_path:
                return self._restore_file(file_path)
            elif branch:
                return self._switch_branch(branch, create_new)
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error="Either branch or file_path must be specified"
                )
        
        except Exception as e:
            logger.error(f"Error in git checkout: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error: {str(e)}"
            )
    
    def _switch_branch(self, branch: str, create_new: bool) -> ToolResult:
        """Switch to branch."""
        try:
            cmd = ["git", "checkout"]
            
            if create_new:
                cmd.append("-b")
            
            cmd.append(branch)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                if create_new:
                    output = f"✓ Created and switched to new branch '{branch}'"
                else:
                    output = f"✓ Switched to branch '{branch}'"
                
                output += "\n\n" + (result.stdout or result.stderr).strip()
                
                return ToolResult(
                    success=True,
                    output=output,
                    metadata={"branch": branch, "created": create_new}
                )
            else:
                error_msg = result.stderr.strip()
                
                # Provide helpful hints
                if "did not match any file" in error_msg.lower():
                    error_msg += f"\n\nHint: Branch '{branch}' does not exist. Use create_new=true to create it."
                elif "uncommitted changes" in error_msg.lower() or "would be overwritten" in error_msg.lower():
                    error_msg += "\n\nHint: You have uncommitted changes. Commit or stash them first."
                
                return ToolResult(
                    success=False,
                    output="",
                    error=error_msg
                )
        
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Error switching branch: {str(e)}"
            )
    
    def _restore_file(self, file_path: str) -> ToolResult:
        """Restore file to last committed state."""
        try:
            result = subprocess.run(
                ["git", "checkout", "--", file_path],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                output = f"✓ Restored '{file_path}' to last committed state\n\n"
                output += "⚠️  Warning: All uncommitted changes to this file have been discarded."
                
                return ToolResult(
                    success=True,
                    output=output,
                    metadata={"file": file_path}
                )
            else:
                error_msg = result.stderr.strip()
                
                if "did not match any file" in error_msg.lower():
                    error_msg += f"\n\nHint: File '{file_path}' not found in repository."
                
                return ToolResult(
                    success=False,
                    output="",
                    error=error_msg
                )
        
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Error restoring file: {str(e)}"
            )
