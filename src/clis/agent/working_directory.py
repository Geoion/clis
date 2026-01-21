"""
Working Directory Manager - Explicitly track and manage working directory state

Solves the core problem of Agent not knowing "which directory we're currently in".
"""

import os
import re
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass, field


@dataclass
class DirectoryContext:
    """Directory context information"""
    path: str
    is_git_repo: bool = False
    git_branch: Optional[str] = None
    has_venv: bool = False
    project_type: Optional[str] = None  # python, node, rust, etc.


class WorkingDirectoryManager:
    """
    Working Directory Manager
    
    Features:
    1. Track current working directory
    2. Record directory change history
    3. Provide directory context information
    4. Execute tools in specified directory
    """
    
    def __init__(self, initial_dir: Optional[str] = None):
        """
        Initialize working directory manager
        
        Args:
            initial_dir: Initial working directory (defaults to current directory)
        """
        self.initial_dir = Path(initial_dir or os.getcwd()).absolute()
        self.current_dir = self.initial_dir
        self.directory_stack: List[Path] = []
        self.directory_history: List[Path] = [self.current_dir]
    
    def change_directory(self, path: str) -> bool:
        """
        Change working directory
        
        Args:
            path: Target directory (supports relative and absolute paths)
            
        Returns:
            True if successful
        """
        try:
            # Parse path
            target = Path(path).expanduser()
            if not target.is_absolute():
                target = self.current_dir / target
            
            target = target.resolve()
            
            if not target.exists():
                return False
            
            if not target.is_dir():
                return False
            
            # Update state
            self.directory_stack.append(self.current_dir)
            self.current_dir = target
            self.directory_history.append(target)
            
            # Keep only the last 10 history entries
            if len(self.directory_history) > 10:
                self.directory_history = self.directory_history[-10:]
            
            return True
        
        except Exception:
            return False
    
    def pop_directory(self) -> bool:
        """
        Return to previous directory (similar to popd)
        
        Returns:
            True if successful
        """
        if self.directory_stack:
            self.current_dir = self.directory_stack.pop()
            self.directory_history.append(self.current_dir)
            return True
        return False
    
    def get_context(self) -> DirectoryContext:
        """
        Get context information for current directory
        
        Returns:
            DirectoryContext with relevant information
        """
        ctx = DirectoryContext(path=str(self.current_dir))
        
        # Check if it's a Git repository
        git_dir = self.current_dir / '.git'
        if git_dir.exists():
            ctx.is_git_repo = True
            # Try to get current branch
            try:
                head_file = git_dir / 'HEAD'
                if head_file.exists():
                    content = head_file.read_text().strip()
                    if content.startswith('ref: refs/heads/'):
                        ctx.git_branch = content.split('/')[-1]
            except Exception:
                pass
        
        # Check for virtual environment
        for venv_name in ['.venv', 'venv', 'env']:
            if (self.current_dir / venv_name).exists():
                ctx.has_venv = True
                break
        
        # Infer project type
        if (self.current_dir / 'setup.py').exists() or (self.current_dir / 'pyproject.toml').exists():
            ctx.project_type = 'python'
        elif (self.current_dir / 'package.json').exists():
            ctx.project_type = 'node'
        elif (self.current_dir / 'Cargo.toml').exists():
            ctx.project_type = 'rust'
        elif (self.current_dir / 'go.mod').exists():
            ctx.project_type = 'go'
        
        return ctx
    
    def to_prompt(self) -> str:
        """
        Generate directory information for Agent prompt
        
        Returns:
            Formatted directory context text
        """
        ctx = self.get_context()
        
        # Basic information
        prompt = f"""
╭──────────────────────────────────────────────────────────────╮
│               📂 Working Directory Context                   │
╰──────────────────────────────────────────────────────────────╯

📍 Current working directory: {ctx.path}
"""
        
        # Git information
        if ctx.is_git_repo:
            branch_info = f" (branch: {ctx.git_branch})" if ctx.git_branch else ""
            prompt += f"📦 Git repository: ✅ Initialized{branch_info}\n"
        else:
            prompt += f"📦 Git repository: ❌ Not initialized\n"
        
        # Project type
        if ctx.project_type:
            prompt += f"🔧 Project type: {ctx.project_type}\n"
        
        # Virtual environment
        if ctx.has_venv:
            prompt += f"🐍 Virtual environment: ✅ Exists\n"
        
        # Directory history
        if len(self.directory_history) > 1:
            recent_dirs = [str(d) for d in self.directory_history[-3:]]
            prompt += f"\n📜 Recently accessed directories:\n   {' → '.join(recent_dirs)}\n"
        
        # Important notes
        prompt += f"""
⚠️  Important notes:
   • Git tools (git_status, git_add, etc.) will execute in this directory
   • Relative paths are resolved relative to this directory
   • To operate in other directories, switch directory first or use absolute paths
   • After switching directories, remember to update working directory state
"""
        
        return prompt
    
    def extract_directory_from_command(self, command: str) -> Optional[str]:
        """
        Extract directory change information from command
        
        Args:
            command: Shell command
            
        Returns:
            Directory path if command contains cd
        """
        # Match cd commands
        patterns = [
            r'cd\s+([^\s&|;]+)',  # cd /path
            r'cd\s+"([^"]+)"',    # cd "/path with spaces"
            r"cd\s+'([^']+)'",    # cd '/path'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, command)
            if match:
                return match.group(1)
        
        return None
    
    def update_from_command(self, command: str) -> bool:
        """
        Update working directory based on command
        
        Args:
            command: Executed command
            
        Returns:
            True if directory changed
        """
        dir_path = self.extract_directory_from_command(command)
        if dir_path:
            return self.change_directory(dir_path)
        return False
    
    def get_absolute_path(self, path: str) -> str:
        """
        Convert relative path to absolute path
        
        Args:
            path: File path (may be relative)
            
        Returns:
            Absolute path
        """
        path_obj = Path(path).expanduser()
        if path_obj.is_absolute():
            return str(path_obj)
        else:
            return str((self.current_dir / path_obj).resolve())
    
    def get_relative_path(self, path: str) -> str:
        """
        Get path relative to current directory
        
        Args:
            path: Absolute path
            
        Returns:
            Relative path (if possible)
        """
        try:
            path_obj = Path(path).expanduser()
            return str(path_obj.relative_to(self.current_dir))
        except ValueError:
            # Not under current directory, return absolute path
            return str(path_obj)
    
    def get_stats(self) -> dict:
        """
        Get statistics
        
        Returns:
            Statistics dictionary
        """
        ctx = self.get_context()
        return {
            'current_dir': str(self.current_dir),
            'is_git_repo': ctx.is_git_repo,
            'git_branch': ctx.git_branch,
            'project_type': ctx.project_type,
            'directory_changes': len(self.directory_history) - 1,
            'stack_depth': len(self.directory_stack)
        }
    
    def clear(self):
        """Reset to initial directory"""
        self.current_dir = self.initial_dir
        self.directory_stack.clear()
        self.directory_history = [self.current_dir]
