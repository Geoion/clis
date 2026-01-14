"""
Insert code tool - insert code at a specific line in a file.
"""

from pathlib import Path
from typing import Any, Dict

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class InsertCodeTool(Tool):
    """Insert code at a specific line in a file."""
    
    @property
    def name(self) -> str:
        return "insert_code"
    
    @property
    def description(self) -> str:
        return (
            "Insert code at a specific line number in a file. "
            "Line number can be 0 (beginning of file) or positive integer. "
            "Useful for adding imports, comments, or new functions."
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
                "line": {
                    "type": "integer",
                    "description": "Line number to insert at (0 = beginning, N = after line N)",
                    "minimum": 0
                },
                "content": {
                    "type": "string",
                    "description": "Code content to insert (can be multiple lines)"
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "Preview changes without modifying file (default: false)",
                    "default": False
                }
            },
            "required": ["path", "line", "content"]
        }
    
    @property
    def is_readonly(self) -> bool:
        return False
    
    @property
    def risk_score(self) -> int:
        """Medium risk - modifies files."""
        return 50
    
    @property
    def requires_confirmation(self) -> bool:
        return True
    
    def execute(
        self,
        path: str,
        line: int,
        content: str,
        dry_run: bool = False
    ) -> ToolResult:
        """
        Execute code insertion.
        
        Args:
            path: File path
            line: Line number to insert at
            content: Content to insert
            dry_run: Preview only
            
        Returns:
            ToolResult with insertion result
        """
        try:
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
            
            # Validate line number
            if line < 0 or line > len(lines):
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Invalid line number: {line} (file has {len(lines)} lines)"
                )
            
            # Prepare content to insert (ensure it ends with newline)
            insert_content = content
            if not insert_content.endswith('\n'):
                insert_content += '\n'
            
            # Split insert content into lines for counting
            insert_lines = insert_content.split('\n')
            # Remove empty last element if content ended with \n
            if insert_lines and insert_lines[-1] == '':
                insert_lines.pop()
            
            # Insert content
            if line == 0:
                new_lines = [insert_content] + lines
            else:
                new_lines = lines[:line] + [insert_content] + lines[line:]
            
            new_content = ''.join(new_lines)
            
            # Generate preview
            preview_start = max(0, line - 2)
            preview_end = min(len(new_lines), line + len(insert_lines) + 2)
            preview_lines = []
            for i in range(preview_start, preview_end):
                prefix = "+" if line <= i < line + len(insert_lines) else " "
                preview_lines.append(f"{prefix} {i+1:4d} | {new_lines[i].rstrip()}")
            
            # Write back (only if not dry run)
            if not dry_run:
                with open(path_obj, 'w', encoding='utf-8') as f:
                    f.write(new_content)
            
            # Build output
            if dry_run:
                output = f"🔍 DRY RUN - Preview of changes to: {path}\n\n"
                output += f"⚠️  File will NOT be modified (dry_run=true)\n\n"
            else:
                output = f"✓ Code inserted successfully: {path}\n\n"
            
            output += f"Inserted at line {line} ({len(insert_lines)} line(s))\n\n"
            output += "Preview:\n"
            output += "="*70 + "\n"
            output += "\n".join(preview_lines) + "\n"
            output += "="*70 + "\n"
            
            return ToolResult(
                success=True,
                output=output,
                metadata={
                    'path': str(path_obj),
                    'line': line,
                    'lines_inserted': len(insert_lines),
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
            logger.error(f"Error inserting code: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error inserting code: {str(e)}"
            )
