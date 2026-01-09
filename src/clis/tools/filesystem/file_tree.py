"""
File tree tool - display directory structure as a tree.
"""

import subprocess
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Dict, Optional

from clis.tools.base import Tool, ToolResult
from clis.tools.utils import has_command
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class FileTreeTool(Tool):
    """Display directory structure as a tree."""
    
    @property
    def name(self) -> str:
        return "file_tree"
    
    @property
    def description(self) -> str:
        return "Display directory structure as a tree. Useful for understanding project layout."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "default": ".",
                    "description": "Root directory"
                },
                "max_depth": {
                    "type": "integer",
                    "default": 3,
                    "description": "Maximum depth to traverse"
                },
                "show_hidden": {
                    "type": "boolean",
                    "default": False,
                    "description": "Show hidden files"
                },
                "pattern": {
                    "type": "string",
                    "description": "Filter by file pattern (e.g., '*.py')"
                }
            }
        }
    
    def execute(self, path: str = ".", max_depth: int = 3,
                show_hidden: bool = False, pattern: Optional[str] = None) -> ToolResult:
        """Execute file tree."""
        try:
            path_obj = Path(path)
            if not path_obj.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Path does not exist: {path}"
                )
            
            # Try using tree command if available
            if has_command("tree"):
                return self._tree_with_command(path, max_depth, show_hidden, pattern)
            
            # Fallback: custom implementation
            output = self._build_tree(path_obj, max_depth, show_hidden, pattern)
            return ToolResult(success=True, output=output)
            
        except Exception as e:
            logger.error(f"Error building file tree: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error building file tree: {str(e)}"
            )
    
    def _tree_with_command(self, path: str, max_depth: int, show_hidden: bool,
                           pattern: Optional[str]) -> ToolResult:
        """Use tree command if available."""
        cmd = ["tree", "-L", str(max_depth)]
        
        if show_hidden:
            cmd.append("-a")
        
        if pattern:
            cmd.extend(["-P", pattern])
        
        cmd.append(path)
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            return ToolResult(success=True, output=result.stdout)
        else:
            # Fallback to custom implementation
            output = self._build_tree(Path(path), max_depth, show_hidden, pattern)
            return ToolResult(success=True, output=output)
    
    def _build_tree(self, path: Path, max_depth: int, show_hidden: bool,
                    pattern: Optional[str], prefix: str = "", depth: int = 0) -> str:
        """Build tree structure manually."""
        if depth >= max_depth:
            return ""
        
        lines = []
        try:
            items = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name))
            
            visible_items = []
            for item in items:
                if not show_hidden and item.name.startswith('.'):
                    continue
                if pattern and not item.is_dir() and not fnmatch(item.name, pattern):
                    continue
                visible_items.append(item)
            
            for i, item in enumerate(visible_items):
                is_last = i == len(visible_items) - 1
                current_prefix = "└── " if is_last else "├── "
                next_prefix = "    " if is_last else "│   "
                
                lines.append(f"{prefix}{current_prefix}{item.name}")
                
                if item.is_dir() and depth + 1 < max_depth:
                    subtree = self._build_tree(
                        item, max_depth, show_hidden, pattern,
                        prefix + next_prefix, depth + 1
                    )
                    if subtree:
                        lines.append(subtree)
        
        except PermissionError:
            lines.append(f"{prefix}[Permission Denied]")
        
        return "\n".join(lines)
