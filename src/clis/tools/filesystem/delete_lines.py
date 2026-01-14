"""
Delete lines tool - delete specific lines from a file.
"""

from pathlib import Path
from typing import Any, Dict

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class DeleteLinesTool(Tool):
    """Delete specific lines from a file."""
    
    @property
    def name(self) -> str:
        return "delete_lines"
    
    @property
    def description(self) -> str:
        return (
            "Delete specific lines from a file by line number range. "
            "Can delete a single line (start_line = end_line) or a range. "
            "USE WITH CAUTION - permanently removes code!"
        )
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file"
                },
                "start_line": {
                    "type": "integer",
                    "description": "First line to delete (1-indexed)",
                    "minimum": 1
                },
                "end_line": {
                    "type": "integer",
                    "description": "Last line to delete (inclusive, default: same as start_line)",
                    "minimum": 1
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "Preview changes without modifying file (default: false)",
                    "default": False
                }
            },
            "required": ["path", "start_line"]
        }
    
    @property
    def is_readonly(self) -> bool:
        return False
    
    @property
    def risk_score(self) -> int:
        """High risk - deletes code."""
        return 60
    
    @property
    def requires_confirmation(self) -> bool:
        return True
    
    def execute(
        self,
        path: str,
        start_line: int,
        end_line: int = None,
        dry_run: bool = False
    ) -> ToolResult:
        """
        Execute line deletion.
        
        Args:
            path: File path
            start_line: First line to delete
            end_line: Last line to delete (inclusive)
            dry_run: Preview only
            
        Returns:
            ToolResult with deletion result
        """
        try:
            if end_line is None:
                end_line = start_line
            
            path_obj = Path(path).expanduser()
            
            if not path_obj.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"File does not exist: {path}"
                )
            
            if not path_obj.is_file():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Path is not a file: {path}"
                )
            
            # Read current content
            try:
                with open(path_obj, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            except UnicodeDecodeError:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"File is not a text file: {path}"
                )
            
            # Validate line numbers
            if start_line < 1 or start_line > len(lines):
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Invalid start_line: {start_line} (file has {len(lines)} lines)"
                )
            
            if end_line < start_line:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"end_line ({end_line}) must be >= start_line ({start_line})"
                )
            
            if end_line > len(lines):
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Invalid end_line: {end_line} (file has {len(lines)} lines)"
                )
            
            # Store lines to be deleted for preview
            deleted_lines = lines[start_line-1:end_line]
            num_deleted = end_line - start_line + 1
            
            # Delete lines (convert to 0-indexed)
            new_lines = lines[:start_line-1] + lines[end_line:]
            new_content = ''.join(new_lines)
            
            # Generate preview
            preview_start = max(0, start_line - 3)
            preview_end = min(len(lines), end_line + 2)
            preview_lines = []
            
            for i in range(preview_start, preview_end):
                if start_line - 1 <= i < end_line:
                    # Lines to be deleted
                    preview_lines.append(f"- {i+1:4d} | {lines[i].rstrip()}")
                elif i < start_line - 1:
                    # Lines before deletion
                    preview_lines.append(f"  {i+1:4d} | {lines[i].rstrip()}")
                else:
                    # Lines after deletion (adjust line numbers)
                    new_line_num = i - num_deleted + 1
                    preview_lines.append(f"  {new_line_num:4d} | {lines[i].rstrip()}")
            
            # Write back (only if not dry run)
            if not dry_run:
                with open(path_obj, 'w', encoding='utf-8') as f:
                    f.write(new_content)
            
            # Build output
            if dry_run:
                output = f"🔍 DRY RUN - Preview of changes to: {path}\n\n"
                output += f"⚠️  File will NOT be modified (dry_run=true)\n\n"
            else:
                output = f"✓ Lines deleted successfully: {path}\n\n"
            
            output += f"Deleted lines {start_line}-{end_line} ({num_deleted} line(s))\n\n"
            output += "Deleted content:\n"
            output += "="*70 + "\n"
            for i, line in enumerate(deleted_lines, start_line):
                output += f"  {i:4d} | {line.rstrip()}\n"
            output += "="*70 + "\n\n"
            
            output += "Preview:\n"
            output += "="*70 + "\n"
            output += "\n".join(preview_lines) + "\n"
            output += "="*70 + "\n"
            
            return ToolResult(
                success=True,
                output=output,
                metadata={
                    'path': str(path_obj),
                    'start_line': start_line,
                    'end_line': end_line,
                    'lines_deleted': num_deleted,
                    'dry_run': dry_run
                }
            )
        
        except PermissionError:
            return ToolResult(
                success=False,
                output="",
                error=f"Permission denied: {path}"
            )
        except Exception as e:
            logger.error(f"Error deleting lines: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error deleting lines: {str(e)}"
            )
