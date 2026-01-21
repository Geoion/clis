"""
Search and replace tool - batch find and replace across multiple files.
"""

import re
from pathlib import Path
from typing import Any, Dict, List

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class SearchReplaceTool(Tool):
    """Batch search and replace across multiple files."""
    
    @property
    def name(self) -> str:
        return "search_replace"
    
    @property
    def description(self) -> str:
        return (
            "Batch search and replace across multiple files. Supports literal and regex patterns. "
            "Useful for refactoring: renaming variables, updating imports, changing patterns. "
            "USE WITH CAUTION - modifies multiple files!"
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
                "replacement": {
                    "type": "string",
                    "description": "Replacement text (can use \\1, \\2 for regex groups)"
                },
                "path": {
                    "type": "string",
                    "description": "Path to search (file or directory, default: current directory)",
                    "default": "."
                },
                "file_pattern": {
                    "type": "string",
                    "description": "File pattern to filter (e.g., '*.py', '*.js', default: '*')",
                    "default": "*"
                },
                "regex": {
                    "type": "boolean",
                    "description": "Use regex pattern matching (default: false)",
                    "default": False
                },
                "ignore_case": {
                    "type": "boolean",
                    "description": "Case insensitive search (default: false)",
                    "default": False
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "Preview changes without modifying files (default: false when auto-approve enabled)",
                    "default": False
                },
                "max_files": {
                    "type": "integer",
                    "description": "Maximum number of files to modify (default: 100)",
                    "default": 100
                }
            },
            "required": ["pattern", "replacement"]
        }
    
    @property
    def is_readonly(self) -> bool:
        return False
    
    @property
    def risk_score(self) -> int:
        """High risk - modifies multiple files."""
        return 70
    
    @property
    def requires_confirmation(self) -> bool:
        """Requires confirmation as it modifies multiple files."""
        return True
    
    def execute(
        self,
        pattern: str,
        replacement: str,
        path: str = ".",
        file_pattern: str = "*",
        regex: bool = False,
        ignore_case: bool = False,
        dry_run: bool = False,
        max_files: int = 100
    ) -> ToolResult:
        """
        Execute batch search and replace.
        
        Args:
            pattern: Search pattern
            replacement: Replacement text
            path: Path to search in
            file_pattern: File pattern filter
            regex: Use regex
            ignore_case: Case insensitive
            dry_run: Preview only
            max_files: Maximum files to modify
            
        Returns:
            ToolResult with replacement results
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
                    compiled_pattern = re.compile(re.escape(pattern), flags)
            except re.error as e:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Invalid regex pattern: {e}"
                )
            
            # Collect files
            if path_obj.is_file():
                files_to_process = [path_obj]
            else:
                files_to_process = list(path_obj.rglob(file_pattern))
            
            # Filter and process files
            modified_files = []
            total_replacements = 0
            skipped_files = 0
            
            for file_path in files_to_process[:max_files + 100]:  # Check more but stop modifying at max_files
                if not file_path.is_file():
                    continue
                
                # Skip hidden files and common ignore patterns
                if any(part.startswith('.') for part in file_path.parts):
                    continue
                if any(ignore in str(file_path) for ignore in ['node_modules', '__pycache__', '.venv', 'venv', 'dist', 'build']):
                    continue
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        original_content = f.read()
                except (UnicodeDecodeError, PermissionError, OSError):
                    skipped_files += 1
                    continue
                
                # Perform replacement
                new_content, count = compiled_pattern.subn(replacement, original_content)
                
                if count > 0:
                    if len(modified_files) >= max_files:
                        skipped_files += 1
                        continue
                    
                    # Write back (only if not dry run)
                    if not dry_run:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                    
                    modified_files.append({
                        'path': str(file_path.relative_to(Path.cwd()) if file_path.is_relative_to(Path.cwd()) else file_path),
                        'replacements': count,
                        'preview': self._generate_preview(original_content, new_content, pattern)
                    })
                    total_replacements += count
            
            # Build output
            if dry_run:
                output = f"🔍 DRY RUN - Preview of changes (files will NOT be modified)\n\n"
            else:
                output = f"✓ Search and replace completed\n\n"
            
            output += f"Pattern: '{pattern}'\n"
            output += f"Replacement: '{replacement}'\n"
            output += f"Files modified: {len(modified_files)}\n"
            output += f"Total replacements: {total_replacements}\n"
            
            if skipped_files > 0:
                output += f"Files skipped: {skipped_files}\n"
            
            if modified_files:
                output += f"\n{'='*70}\n"
                output += "Modified files:\n"
                output += f"{'='*70}\n\n"
                
                for i, file_info in enumerate(modified_files[:10], 1):  # Show first 10
                    output += f"{i}. {file_info['path']} ({file_info['replacements']} replacement(s))\n"
                    if file_info['preview']:
                        output += f"   Preview: {file_info['preview']}\n"
                
                if len(modified_files) > 10:
                    output += f"\n... and {len(modified_files) - 10} more file(s)\n"
                
                if dry_run:
                    output += f"\n⚠️  To apply these changes, run with dry_run=false\n"
            
            return ToolResult(
                success=True,
                output=output,
                metadata={
                    'files_modified': len(modified_files),
                    'total_replacements': total_replacements,
                    'dry_run': dry_run,
                    'modified_files': modified_files
                }
            )
        
        except Exception as e:
            logger.error(f"Error during search and replace: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error during search and replace: {str(e)}"
            )
    
    def _generate_preview(self, original: str, modified: str, pattern: str, max_length: int = 80) -> str:
        """Generate a preview of the first change."""
        # Find first difference
        for i, (orig_line, mod_line) in enumerate(zip(original.splitlines(), modified.splitlines())):
            if orig_line != mod_line:
                preview = f"{orig_line[:max_length]} → {mod_line[:max_length]}"
                if len(orig_line) > max_length or len(mod_line) > max_length:
                    preview += "..."
                return preview
        return ""
