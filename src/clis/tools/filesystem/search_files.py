"""
Search files tool - search for text patterns in files.
"""

import re
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from clis.tools.base import Tool, ToolResult
from clis.tools.utils import has_command
from clis.utils.logger import get_logger
from clis.utils.platform import is_windows

logger = get_logger(__name__)


class SearchFilesTool(Tool):
    """Search for text patterns in files using grep or ripgrep."""
    
    @property
    def name(self) -> str:
        return "search_files"
    
    @property
    def description(self) -> str:
        return "Search for text patterns in files (basic search, no regex control). Use grep tool for advanced regex features. Cross-platform (uses ripgrep/grep/Python)."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Search pattern (literal text, treated as regex by ripgrep/grep backend but no regex mode control)"
                },
                "path": {
                    "type": "string",
                    "default": ".",
                    "description": "Directory to search in"
                },
                "file_pattern": {
                    "type": "string",
                    "description": "File pattern to search (e.g., '*.py', '*.js')"
                },
                "case_sensitive": {
                    "type": "boolean",
                    "default": True,
                    "description": "Case sensitive search"
                },
                "max_results": {
                    "type": "integer",
                    "default": 100,
                    "description": "Maximum number of results"
                }
            },
            "required": ["pattern"]
        }
    
    def execute(self, pattern: str, path: str = ".", 
                file_pattern: Optional[str] = None, case_sensitive: bool = True,
                max_results: int = 100) -> ToolResult:
        """Execute search."""
        try:
            path_obj = Path(path)
            if not path_obj.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Path does not exist: {path}"
                )
            
            # Choose search tool based on platform and availability
            if has_command("rg"):  # ripgrep (best, cross-platform)
                return self._search_with_ripgrep(pattern, path, file_pattern, case_sensitive, max_results)
            elif not is_windows():  # Unix systems with grep
                return self._search_with_grep(pattern, path, file_pattern, case_sensitive, max_results)
            else:  # Windows fallback
                return self._search_with_python(pattern, path, file_pattern, case_sensitive, max_results)
        
        except Exception as e:
            logger.error(f"Error searching files: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error searching files: {str(e)}"
            )
    
    def _search_with_ripgrep(self, pattern: str, path: str, file_pattern: Optional[str],
                             case_sensitive: bool, max_results: int) -> ToolResult:
        """Search using ripgrep."""
        cmd = ["rg", "-n", "--max-count", str(max_results)]
        
        if not case_sensitive:
            cmd.append("-i")
        
        if file_pattern:
            cmd.extend(["-g", file_pattern])
        
        cmd.extend([pattern, path])
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            return ToolResult(
                success=True,
                output=result.stdout,
                metadata={"matches": len(result.stdout.split('\n')) if result.stdout else 0}
            )
        elif result.returncode == 1:  # No matches
            return ToolResult(
                success=True,
                output="No matches found",
                metadata={"matches": 0}
            )
        else:
            return ToolResult(
                success=False,
                output="",
                error=result.stderr or "Search failed"
            )
    
    def _search_with_grep(self, pattern: str, path: str, file_pattern: Optional[str],
                          case_sensitive: bool, max_results: int) -> ToolResult:
        """Search using grep (Unix)."""
        cmd = ["grep", "-r", "-n"]
        
        if not case_sensitive:
            cmd.append("-i")
        
        if file_pattern:
            cmd.append(f"--include={file_pattern}")
        
        cmd.extend([pattern, path])
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            lines = result.stdout.split('\n')[:max_results]
            output = '\n'.join(lines)
            return ToolResult(
                success=True,
                output=output,
                metadata={"matches": len(lines)}
            )
        elif result.returncode == 1:
            return ToolResult(
                success=True,
                output="No matches found",
                metadata={"matches": 0}
            )
        else:
            return ToolResult(
                success=False,
                output="",
                error=result.stderr or "Search failed"
            )
    
    def _search_with_python(self, pattern: str, path: str, file_pattern: Optional[str],
                            case_sensitive: bool, max_results: int) -> ToolResult:
        """Search using Python (fallback for Windows)."""
        matches = []
        pattern_re = re.compile(pattern, 0 if case_sensitive else re.IGNORECASE)
        
        path_obj = Path(path)
        files = path_obj.rglob(file_pattern if file_pattern else "*")
        
        for file_path in files:
            if not file_path.is_file():
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line_no, line in enumerate(f, 1):
                        if pattern_re.search(line):
                            matches.append(f"{file_path}:{line_no}:{line.rstrip()}")
                            if len(matches) >= max_results:
                                break
            except Exception:
                continue
            
            if len(matches) >= max_results:
                break
        
        if matches:
            return ToolResult(
                success=True,
                output='\n'.join(matches),
                metadata={"matches": len(matches)}
            )
        else:
            return ToolResult(
                success=True,
                output="No matches found",
                metadata={"matches": 0}
            )
