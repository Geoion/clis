"""
Edit file tool - precise file editing using diff mode.
"""

import difflib
from pathlib import Path
from typing import Any, Dict

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class EditFileTool(Tool):
    """Edit file using diff mode for precise modifications."""
    
    @property
    def name(self) -> str:
        return "edit_file"
    
    @property
    def description(self) -> str:
        return (
            "Edit file content using diff mode. Replaces old_content with new_content. "
            "The old_content must be unique in the file to ensure precise editing. "
            "This is more efficient than rewriting the entire file."
        )
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to edit"
                },
                "old_content": {
                    "type": "string",
                    "description": "Content to replace (must be unique in the file)"
                },
                "new_content": {
                    "type": "string",
                    "description": "New content to insert"
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "Preview changes without actually modifying the file (default: false)",
                    "default": False
                }
            },
            "required": ["path", "old_content", "new_content"]
        }
    
    @property
    def is_readonly(self) -> bool:
        return False  # This is a write operation
    
    @property
    def risk_score(self) -> int:
        """Edit file is medium risk - modifies files."""
        return 50
    
    @property
    def requires_confirmation(self) -> bool:
        """Edit file requires confirmation as it modifies files."""
        return True
    
    def execute(self, path: str, old_content: str, new_content: str, dry_run: bool = False) -> ToolResult:
        """
        Execute file edit using diff mode.
        
        Args:
            path: Path to the file
            old_content: Content to replace (must be unique)
            new_content: New content to insert
            dry_run: Preview changes without modifying the file
            
        Returns:
            ToolResult with success status and diff output
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
                    original_content = f.read()
            except UnicodeDecodeError:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"File is not a text file or uses unsupported encoding: {path}"
                )
            
            # Check if old_content exists
            if old_content not in original_content:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Old content not found in {path}. Make sure the content matches exactly (including whitespace)."
                )
            
            # Check uniqueness
            occurrences = original_content.count(old_content)
            if occurrences > 1:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Old content appears {occurrences} times in the file. It must be unique for safe editing. Please include more context to make it unique."
                )
            
            # Perform replacement
            new_file_content = original_content.replace(old_content, new_content, 1)
            
            # Check if anything actually changed
            if new_file_content == original_content:
                return ToolResult(
                    success=True,
                    output="No changes made (old_content and new_content are identical)",
                    metadata={"changed": False, "dry_run": dry_run}
                )
            
            # Generate enhanced diff (Cursor-style)
            diff_output = self._generate_enhanced_diff(
                original_content, 
                new_file_content, 
                path
            )
            
            # Count changes
            lines_added = new_file_content.count('\n') - original_content.count('\n')
            if lines_added == 0:
                # Same number of lines, count actual changes
                lines_added = sum(1 for old, new in zip(original_content.splitlines(), new_file_content.splitlines()) if old != new)
                lines_removed = lines_added
            else:
                lines_removed = abs(min(0, lines_added))
                lines_added = max(0, lines_added)
            
            # Build output message
            if dry_run:
                output = f"DRY RUN - Preview of changes to: {path}\n\n"
                output += f"Warning: File will NOT be modified (dry_run=true)\n\n"
            else:
                # Write new content (only if not dry run)
                with open(path_obj, 'w', encoding='utf-8') as f:
                    f.write(new_file_content)
                
                output = f"File edited successfully: {path}\n\n"
            
            output += f"Changes: +{lines_added} -{lines_removed} lines\n\n"
            output += diff_output
            
            return ToolResult(
                success=True,
                output=output,
                metadata={
                    "path": str(path_obj),
                    "lines_added": lines_added,
                    "lines_removed": lines_removed,
                    "changed": True,
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
            logger.error(f"Error editing file: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error editing file: {str(e)}"
            )
    
    def _generate_enhanced_diff(self, original: str, modified: str, filepath: str) -> str:
        """
        Generate enhanced diff output similar to Cursor's style.
        
        Args:
            original: Original file content
            modified: Modified file content
            filepath: File path for display
            
        Returns:
            Formatted diff string
        """
        original_lines = original.splitlines(keepends=True)
        modified_lines = modified.splitlines(keepends=True)
        
        # Generate unified diff
        diff_lines = list(difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile=f"a/{filepath}",
            tofile=f"b/{filepath}",
            lineterm=''
        ))
        
        if not diff_lines:
            return "No line-based differences found"
        
        # Enhanced formatting with colors (using ANSI codes)
        output = []
        output.append("=" * 70)
        
        for line in diff_lines:
            line = line.rstrip('\n')
            
            if line.startswith('---') or line.startswith('+++'):
                # File headers
                output.append(f"{line}")
            elif line.startswith('@@'):
                # Hunk header
                output.append(f"\n{line}")
                output.append("-" * 70)
            elif line.startswith('-') and not line.startswith('---'):
                # Removed line (red)
                output.append(f"- {line[1:]}")
            elif line.startswith('+') and not line.startswith('+++'):
                # Added line (green)
                output.append(f"+ {line[1:]}")
            elif line.startswith(' '):
                # Context line
                output.append(f"  {line[1:]}")
            else:
                output.append(line)
        
        output.append("=" * 70)
        
        return '\n'.join(output)
