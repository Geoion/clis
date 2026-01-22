"""
Grep tool - enhanced code search with regex support.
"""

import re
from pathlib import Path
from typing import Any, Dict, List

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class GrepTool(Tool):
    """Enhanced code search tool with regex support."""
    
    @property
    def name(self) -> str:
        return "grep"
    
    @property
    def description(self) -> str:
        return (
            "Search for patterns in files. Supports both literal and regex patterns. "
            "Can search recursively in directories and filter by file patterns. "
            "Returns file paths, line numbers, and matching content."
        )
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Search pattern (literal or regex)"
                },
                "path": {
                    "type": "string",
                    "description": "Path to search in (file or directory, default: current directory)",
                    "default": "."
                },
                "regex": {
                    "type": "boolean",
                    "description": "Whether to use regex pattern matching (default: false)",
                    "default": False
                },
                "ignore_case": {
                    "type": "boolean",
                    "description": "Whether to ignore case (default: false)",
                    "default": False
                },
                "file_pattern": {
                    "type": "string",
                    "description": "File pattern to filter. Supports: single pattern ('*.py'), comma-separated ('*.py,*.js'), or brace expansion ('*.{py,js,ts}'). Default: '*'",
                    "default": "*"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 100)",
                    "default": 100
                },
                "context_lines": {
                    "type": "integer",
                    "description": "Number of context lines to show before and after match (default: 0)",
                    "default": 0
                }
            },
            "required": ["pattern"]
        }
    
    @property
    def is_readonly(self) -> bool:
        return True  # Read-only operation
    
    def execute(
        self,
        pattern: str,
        path: str = ".",
        regex: bool = False,
        ignore_case: bool = False,
        file_pattern: str = "*",
        max_results: int = 100,
        context_lines: int = 0
    ) -> ToolResult:
        """
        Execute grep search.
        
        Args:
            pattern: Search pattern
            path: Path to search in
            regex: Use regex pattern matching
            ignore_case: Ignore case
            file_pattern: File pattern filter
            max_results: Maximum results
            context_lines: Context lines to show
            
        Returns:
            ToolResult with search results
        """
        try:
            path_obj = Path(path).expanduser()
            
            if not path_obj.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Path does not exist: {path}"
                )
            
            # Compile pattern
            flags = re.IGNORECASE if ignore_case else 0
            try:
                if regex:
                    compiled_pattern = re.compile(pattern, flags)
                else:
                    # Escape special regex characters for literal search
                    compiled_pattern = re.compile(re.escape(pattern), flags)
            except re.error as e:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Invalid regex pattern: {e}"
                )
            
            # Search files
            results = []
            files_searched = 0
            
            # Determine files to search
            if path_obj.is_file():
                files_to_search = [path_obj]
            else:
                # Handle multiple file patterns (e.g., "*.py,*.js" or "*.{py,js}")
                if ',' in file_pattern or '{' in file_pattern:
                    # Parse multiple patterns
                    patterns = []
                    if '{' in file_pattern and '}' in file_pattern:
                        # Handle brace expansion: *.{py,js,ts} -> *.py, *.js, *.ts
                        import re as re_module
                        match = re_module.match(r'(.*)\{([^}]+)\}(.*)', file_pattern)
                        if match:
                            prefix, extensions, suffix = match.groups()
                            patterns = [f"{prefix}{ext}{suffix}" for ext in extensions.split(',')]
                        else:
                            patterns = [file_pattern]
                    else:
                        # Handle comma-separated: *.py,*.js
                        patterns = [p.strip() for p in file_pattern.split(',')]
                    
                    # Search with all patterns
                    files_to_search = []
                    for pattern in patterns:
                        files_to_search.extend(path_obj.rglob(pattern))
                else:
                    # Single pattern
                    files_to_search = list(path_obj.rglob(file_pattern))
            
            for file_path in files_to_search:
                if not file_path.is_file():
                    continue
                
                # Skip hidden files and common ignore patterns
                if any(part.startswith('.') for part in file_path.parts):
                    continue
                
                files_searched += 1
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    
                    # Search in file
                    for line_num, line in enumerate(lines, 1):
                        if compiled_pattern.search(line):
                            # Get context lines
                            context_before = []
                            context_after = []
                            
                            if context_lines > 0:
                                start_idx = max(0, line_num - context_lines - 1)
                                end_idx = min(len(lines), line_num + context_lines)
                                
                                context_before = [
                                    (i + 1, lines[i].rstrip())
                                    for i in range(start_idx, line_num - 1)
                                ]
                                context_after = [
                                    (i + 1, lines[i].rstrip())
                                    for i in range(line_num, end_idx)
                                ]
                            
                            results.append({
                                'file': str(file_path.relative_to(Path.cwd()) if file_path.is_relative_to(Path.cwd()) else file_path),
                                'line': line_num,
                                'content': line.rstrip(),
                                'context_before': context_before,
                                'context_after': context_after
                            })
                            
                            if len(results) >= max_results:
                                break
                
                except (UnicodeDecodeError, PermissionError, OSError):
                    # Skip binary files, permission errors, etc.
                    continue
                
                if len(results) >= max_results:
                    break
            
            # Format output
            if not results:
                output = f"No matches found for pattern '{pattern}'\n"
                output += f"Searched {files_searched} files in {path}"
            else:
                output = f"Found {len(results)} match(es) in {files_searched} file(s):\n\n"
                
                current_file = None
                for result in results:
                    # Print file header if changed
                    if result['file'] != current_file:
                        if current_file is not None:
                            output += "\n"
                        output += f"=== {result['file']} ===\n"
                        current_file = result['file']
                    
                    # Print context before
                    for ctx_line_num, ctx_content in result['context_before']:
                        output += f"  {ctx_line_num:4d} | {ctx_content}\n"
                    
                    # Print matching line
                    output += f"→ {result['line']:4d} | {result['content']}\n"
                    
                    # Print context after
                    for ctx_line_num, ctx_content in result['context_after']:
                        output += f"  {ctx_line_num:4d} | {ctx_content}\n"
                
                if len(results) >= max_results:
                    output += f"\n(Results limited to {max_results}. Use max_results parameter to see more.)"
            
            return ToolResult(
                success=True,
                output=output,
                metadata={
                    'count': len(results),
                    'files_searched': files_searched,
                    'results': results
                }
            )
        
        except Exception as e:
            logger.error(f"Error during grep: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error during search: {str(e)}"
            )
