"""
Insert code tool - insert code at specified line position.
"""

from pathlib import Path
from typing import Any, Dict

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class InsertCodeTool(Tool):
    """Insert code at a specified line position in a file."""
    
    @property
    def name(self) -> str:
        return "insert_code"
    
    @property
    def description(self) -> str:
        return (
            "Insert code at a specified line position in a file. "
            "The line number is 1-indexed. Code is inserted BEFORE the specified line. "
            "Automatically handles indentation based on surrounding context."
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
                "line_number": {
                    "type": "integer",
                    "description": "Line number where to insert code (1-indexed). Code is inserted BEFORE this line. Use -1 or line count + 1 to append at end.",
                    "minimum": -1
                },
                "code": {
                    "type": "string",
                    "description": "Code to insert (can be multi-line)"
                },
                "auto_indent": {
                    "type": "boolean",
                    "description": "Automatically match indentation of surrounding lines (default: true)",
                    "default": True
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "Preview changes without modifying the file (default: false)",
                    "default": False
                }
            },
            "required": ["path", "line_number", "code"]
        }
    
    @property
    def is_readonly(self) -> bool:
        return False
    
    @property
    def risk_score(self) -> int:
        """Insert code is medium risk - modifies files."""
        return 50
    
    @property
    def requires_confirmation(self) -> bool:
        """Insert code requires confirmation as it modifies files."""
        return True
    
    def execute(
        self,
        path: str,
        line_number: int,
        code: str,
        auto_indent: bool = True,
        dry_run: bool = False
    ) -> ToolResult:
        """
        Execute code insertion.
        
        Args:
            path: Path to the file
            line_number: Line number where to insert (1-indexed, before this line)
            code: Code to insert
            auto_indent: Automatically match indentation
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
            
            # Validate line number
            if line_number == -1:
                # Insert at end
                insert_position = total_lines
            elif line_number < 1:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Invalid line number: {line_number}. Must be >= 1 or -1 for end of file."
                )
            elif line_number > total_lines + 1:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Line number {line_number} exceeds file length ({total_lines} lines). Use {total_lines + 1} or -1 to append at end."
                )
            else:
                # Insert before this line (1-indexed to 0-indexed)
                insert_position = line_number - 1
            
            # Process code to insert
            code_lines = code.splitlines(keepends=True)
            
            # Add newlines if missing
            code_lines = [line if line.endswith('\n') else line + '\n' for line in code_lines]
            
            # Auto-indent if requested
            if auto_indent and lines:
                indent = self._detect_indentation(lines, insert_position)
                if indent:
                    code_lines = [indent + line if line.strip() else line for line in code_lines]
            
            # Insert code
            new_lines = lines[:insert_position] + code_lines + lines[insert_position:]
            new_content = ''.join(new_lines)
            
            # Generate preview
            preview = self._generate_preview(
                lines,
                code_lines,
                insert_position,
                path
            )
            
            # Build output message
            if dry_run:
                output = f"🔍 DRY RUN - Preview of insertion at line {line_number} in: {path}\n\n"
                output += f"⚠️  File will NOT be modified (dry_run=true)\n\n"
            else:
                # Write new content
                with open(path_obj, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                output = f"✓ Code inserted successfully at line {line_number}: {path}\n\n"
            
            output += f"Inserted: {len(code_lines)} line(s)\n"
            output += f"New total: {len(new_lines)} line(s)\n\n"
            output += preview
            
            return ToolResult(
                success=True,
                output=output,
                metadata={
                    "path": str(path_obj),
                    "insert_position": insert_position,
                    "lines_inserted": len(code_lines),
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
            logger.error(f"Error inserting code: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error inserting code: {str(e)}"
            )
    
    def _detect_indentation(self, lines: list, insert_position: int) -> str:
        """
        Detect indentation from surrounding lines.
        
        Args:
            lines: File lines
            insert_position: Where code will be inserted
            
        Returns:
            Indentation string (spaces or tabs)
        """
        # Try to get indentation from the line at insert position
        if insert_position < len(lines):
            line = lines[insert_position]
            if line.strip():  # Non-empty line
                indent = len(line) - len(line.lstrip())
                return line[:indent]
        
        # Try previous line
        if insert_position > 0:
            line = lines[insert_position - 1]
            if line.strip():
                indent = len(line) - len(line.lstrip())
                return line[:indent]
        
        # Try next few lines
        for i in range(insert_position + 1, min(insert_position + 5, len(lines))):
            line = lines[i]
            if line.strip():
                indent = len(line) - len(line.lstrip())
                return line[:indent]
        
        return ""
    
    def _generate_preview(
        self,
        original_lines: list,
        code_lines: list,
        insert_position: int,
        filepath: str
    ) -> str:
        """
        Generate a preview of the insertion.
        
        Args:
            original_lines: Original file lines
            code_lines: Lines to insert
            insert_position: Insert position
            filepath: File path
            
        Returns:
            Formatted preview string
        """
        output = []
        output.append("=" * 70)
        output.append(f"📄 File: {filepath}")
        output.append(f"📍 Insert position: line {insert_position + 1}")
        output.append("-" * 70)
        
        # Show context: 3 lines before, inserted code, 3 lines after
        start = max(0, insert_position - 3)
        end = min(len(original_lines), insert_position + 3)
        
        line_num = start + 1
        
        # Lines before insertion
        for i in range(start, insert_position):
            output.append(f"  {line_num:4d} | {original_lines[i].rstrip()}")
            line_num += 1
        
        # Inserted code
        output.append("-" * 70)
        for line in code_lines:
            output.append(f"+ {line_num:4d} | {line.rstrip()}")
            line_num += 1
        output.append("-" * 70)
        
        # Lines after insertion
        for i in range(insert_position, end):
            output.append(f"  {line_num:4d} | {original_lines[i].rstrip()}")
            line_num += 1
        
        output.append("=" * 70)
        
        return '\n'.join(output)
