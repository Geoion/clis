"""
Delete lines tool - delete specified line range from a file.
"""

from pathlib import Path
from typing import Any, Dict

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class DeleteLinesTool(Tool):
    """Delete specified line range from a file."""
    
    @property
    def name(self) -> str:
        return "delete_lines"
    
    @property
    def description(self) -> str:
        return (
            "Delete a range of lines from a file. "
            "Line numbers are 1-indexed (inclusive). "
            "Use start_line=end_line to delete a single line. "
            "USE WITH CAUTION - permanently deletes lines!"
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
                    "description": "First line to delete (1-indexed, inclusive)",
                    "minimum": 1
                },
                "end_line": {
                    "type": "integer",
                    "description": "Last line to delete (1-indexed, inclusive). Use same as start_line to delete single line.",
                    "minimum": 1
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "Preview changes without modifying the file (default: false)",
                    "default": False
                }
            },
            "required": ["path", "start_line", "end_line"]
        }
    
    @property
    def is_readonly(self) -> bool:
        return False
    
    @property
    def risk_score(self) -> int:
        """Delete lines is medium-high risk - permanently deletes content."""
        return 60
    
    @property
    def requires_confirmation(self) -> bool:
        """Delete lines requires confirmation as it permanently removes content."""
        return True
    
    def execute(
        self,
        path: str,
        start_line: int,
        end_line: int,
        dry_run: bool = False
    ) -> ToolResult:
        """
        Execute line deletion.
        
        Args:
            path: Path to the file
            start_line: First line to delete (1-indexed)
            end_line: Last line to delete (1-indexed)
            dry_run: Preview only
            
        Returns:
            ToolResult with success status and preview
        """
        try:
            path_obj = Path(path).expanduser()
            
            # Check if file exists
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
            
            # Validate line range
            if start_line < 1:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"start_line must be >= 1 (got {start_line})"
                )
            
            if end_line < start_line:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"end_line ({end_line}) must be >= start_line ({start_line})"
                )
            
            # Read current content
            try:
                with open(path_obj, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            except UnicodeDecodeError:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"File is not a text file or uses unsupported encoding: {path}"
                )
            
            total_lines = len(lines)
            
            # Validate against file length
            if start_line > total_lines:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"start_line ({start_line}) exceeds file length ({total_lines} lines)"
                )
            
            if end_line > total_lines:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"end_line ({end_line}) exceeds file length ({total_lines} lines)"
                )
            
            # Store deleted content for preview
            deleted_lines = lines[start_line - 1:end_line]
            
            # Delete lines (convert 1-indexed to 0-indexed)
            new_lines = lines[:start_line - 1] + lines[end_line:]
            new_content = ''.join(new_lines)
            
            # Calculate deleted count
            lines_deleted = end_line - start_line + 1
            
            # Generate preview
            preview = self._generate_preview(
                lines,
                deleted_lines,
                start_line,
                end_line,
                path
            )
            
            # Build output message
            if dry_run:
                output = f"🔍 DRY RUN - Preview of deletion in: {path}\n\n"
                output += f"⚠️  File will NOT be modified (dry_run=true)\n\n"
            else:
                # Write new content
                with open(path_obj, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                output = f"✓ Lines deleted successfully: {path}\n\n"
            
            output += f"Deleted: lines {start_line}-{end_line} ({lines_deleted} line(s))\n"
            output += f"New total: {len(new_lines)} line(s)\n\n"
            output += preview
            
            return ToolResult(
                success=True,
                output=output,
                metadata={
                    "path": str(path_obj),
                    "start_line": start_line,
                    "end_line": end_line,
                    "lines_deleted": lines_deleted,
                    "new_total_lines": len(new_lines),
                    "dry_run": dry_run
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
    
    def _generate_preview(
        self,
        original_lines: list,
        deleted_lines: list,
        start_line: int,
        end_line: int,
        filepath: str
    ) -> str:
        """
        Generate a preview of the deletion.
        
        Args:
            original_lines: Original file lines
            deleted_lines: Lines that will be deleted
            start_line: First deleted line number
            end_line: Last deleted line number
            filepath: File path
            
        Returns:
            Formatted preview string
        """
        output = []
        output.append("=" * 70)
        output.append(f"📄 File: {filepath}")
        output.append(f"📍 Deleting lines: {start_line}-{end_line}")
        output.append("-" * 70)
        
        # Show context: 3 lines before, deleted lines, 3 lines after
        context_before = 3
        context_after = 3
        
        preview_start = max(0, start_line - 1 - context_before)
        preview_end = min(len(original_lines), end_line + context_after)
        
        line_num = preview_start + 1
        
        # Lines before deletion
        for i in range(preview_start, start_line - 1):
            output.append(f"  {line_num:4d} | {original_lines[i].rstrip()}")
            line_num += 1
        
        # Deleted lines
        if deleted_lines:
            output.append("-" * 70)
            for i, line in enumerate(deleted_lines):
                actual_line_num = start_line + i
                output.append(f"- {actual_line_num:4d} | {line.rstrip()}")
            output.append("-" * 70)
            line_num = end_line + 1
        
        # Lines after deletion
        for i in range(end_line, preview_end):
            output.append(f"  {line_num:4d} | {original_lines[i].rstrip()}")
            line_num += 1
        
        output.append("=" * 70)
        
        # Show deleted content summary
        if deleted_lines:
            output.append("")
            output.append("🗑️  Deleted content:")
            output.append("-" * 70)
            for i, line in enumerate(deleted_lines[:10], start_line):  # Show first 10
                output.append(f"  Line {i}: {line.rstrip()}")
            if len(deleted_lines) > 10:
                output.append(f"  ... and {len(deleted_lines) - 10} more line(s)")
            output.append("-" * 70)
        
        return '\n'.join(output)
