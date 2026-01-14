"""
Git branch tool.
"""

import subprocess
from typing import Any, Dict

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class GitBranchTool(Tool):
    """Manage git branches (list, create, delete)."""
    
    @property
    def name(self) -> str:
        return "git_branch"
    
    @property
    def description(self) -> str:
        return (
            "Manage git branches. Can list all branches, create new branch, "
            "delete branch, or rename branch. Use action parameter to specify operation."
        )
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action to perform: 'list', 'create', 'delete', 'rename'",
                    "enum": ["list", "create", "delete", "rename"],
                    "default": "list"
                },
                "branch_name": {
                    "type": "string",
                    "description": "Branch name (required for create/delete/rename)",
                    "default": ""
                },
                "new_name": {
                    "type": "string",
                    "description": "New branch name (required for rename)",
                    "default": ""
                },
                "force": {
                    "type": "boolean",
                    "description": "Force delete (for delete action, default: false)",
                    "default": False
                },
                "show_remote": {
                    "type": "boolean",
                    "description": "Show remote branches (for list action, default: false)",
                    "default": False
                }
            },
            "required": []
        }
    
    @property
    def is_readonly(self) -> bool:
        return False  # Can modify branches
    
    @property
    def risk_score(self) -> int:
        """
        Git branch varies in risk by action.
        Default to medium risk, but delete operations are high risk.
        """
        return 60
    
    @property
    def requires_confirmation(self) -> bool:
        """
        Branch operations that modify state require confirmation.
        The actual risk is evaluated per-action in the interactive agent.
        """
        return False  # Will be dynamically evaluated based on action
    
    def execute(
        self,
        action: str = "list",
        branch_name: str = "",
        new_name: str = "",
        force: bool = False,
        show_remote: bool = False
    ) -> ToolResult:
        """
        Execute git branch operation.
        
        Args:
            action: Action to perform
            branch_name: Branch name
            new_name: New branch name (for rename)
            force: Force delete
            show_remote: Show remote branches
            
        Returns:
            ToolResult with operation result
        """
        try:
            if action == "list":
                return self._list_branches(show_remote)
            elif action == "create":
                return self._create_branch(branch_name)
            elif action == "delete":
                return self._delete_branch(branch_name, force)
            elif action == "rename":
                return self._rename_branch(branch_name, new_name)
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Unknown action: {action}"
                )
        
        except Exception as e:
            logger.error(f"Error in git branch: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error: {str(e)}"
            )
    
    def _list_branches(self, show_remote: bool) -> ToolResult:
        """List branches."""
        try:
            cmd = ["git", "branch"]
            if show_remote:
                cmd.append("-a")  # Show all branches including remote
            else:
                cmd.append("-v")  # Show with commit info
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                output = "Git branches:\n\n"
                output += result.stdout
                
                # Add legend
                output += "\n(* indicates current branch)"
                
                return ToolResult(
                    success=True,
                    output=output.strip()
                )
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=result.stderr.strip()
                )
        
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Error listing branches: {str(e)}"
            )
    
    def _create_branch(self, branch_name: str) -> ToolResult:
        """Create new branch."""
        if not branch_name:
            return ToolResult(
                success=False,
                output="",
                error="branch_name is required for create action"
            )
        
        try:
            result = subprocess.run(
                ["git", "branch", branch_name],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                output = f"✓ Branch '{branch_name}' created successfully\n\n"
                output += f"To switch to this branch, use: git checkout {branch_name}"
                
                return ToolResult(
                    success=True,
                    output=output,
                    metadata={"branch": branch_name}
                )
            else:
                error_msg = result.stderr.strip()
                if "already exists" in error_msg.lower():
                    error_msg += f"\n\nHint: Branch '{branch_name}' already exists. Use a different name."
                
                return ToolResult(
                    success=False,
                    output="",
                    error=error_msg
                )
        
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Error creating branch: {str(e)}"
            )
    
    def _delete_branch(self, branch_name: str, force: bool) -> ToolResult:
        """Delete branch."""
        if not branch_name:
            return ToolResult(
                success=False,
                output="",
                error="branch_name is required for delete action"
            )
        
        try:
            cmd = ["git", "branch"]
            cmd.append("-D" if force else "-d")
            cmd.append(branch_name)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                output = f"✓ Branch '{branch_name}' deleted successfully"
                
                return ToolResult(
                    success=True,
                    output=output,
                    metadata={"branch": branch_name}
                )
            else:
                error_msg = result.stderr.strip()
                if "not fully merged" in error_msg.lower():
                    error_msg += "\n\nHint: Branch has unmerged changes. Use force=true to force delete."
                
                return ToolResult(
                    success=False,
                    output="",
                    error=error_msg
                )
        
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Error deleting branch: {str(e)}"
            )
    
    def _rename_branch(self, branch_name: str, new_name: str) -> ToolResult:
        """Rename branch."""
        if not branch_name or not new_name:
            return ToolResult(
                success=False,
                output="",
                error="Both branch_name and new_name are required for rename action"
            )
        
        try:
            result = subprocess.run(
                ["git", "branch", "-m", branch_name, new_name],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                output = f"✓ Branch '{branch_name}' renamed to '{new_name}'"
                
                return ToolResult(
                    success=True,
                    output=output,
                    metadata={"old_name": branch_name, "new_name": new_name}
                )
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=result.stderr.strip()
                )
        
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Error renaming branch: {str(e)}"
            )
