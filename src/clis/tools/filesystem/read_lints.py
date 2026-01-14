"""
Read lints tool - read linter errors from various linters.
"""

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class ReadLintsTool(Tool):
    """Read linter errors from various linters (flake8, pylint, eslint, etc.)."""
    
    @property
    def name(self) -> str:
        return "read_lints"
    
    @property
    def description(self) -> str:
        return (
            "Read linter errors from code files. Supports Python (flake8, pylint, ruff), "
            "JavaScript/TypeScript (eslint), and auto-detection based on file type. "
            "Returns formatted error messages with file paths, line numbers, and descriptions."
        )
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File or directory path to check (default: current directory)",
                    "default": "."
                },
                "linter": {
                    "type": "string",
                    "description": "Linter to use: 'auto', 'flake8', 'pylint', 'ruff', 'eslint' (default: auto)",
                    "default": "auto",
                    "enum": ["auto", "flake8", "pylint", "ruff", "eslint"]
                },
                "max_errors": {
                    "type": "integer",
                    "description": "Maximum number of errors to return (default: 50)",
                    "default": 50
                }
            },
            "required": []
        }
    
    @property
    def is_readonly(self) -> bool:
        return True  # Read-only operation
    
    def execute(
        self,
        path: str = ".",
        linter: str = "auto",
        max_errors: int = 50
    ) -> ToolResult:
        """
        Execute linter and read errors.
        
        Args:
            path: Path to check
            linter: Linter to use
            max_errors: Maximum errors to return
            
        Returns:
            ToolResult with linter errors
        """
        try:
            path_obj = Path(path).expanduser()
            
            if not path_obj.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Path does not exist: {path}"
                )
            
            # Auto-detect linter if needed
            if linter == "auto":
                linter = self._detect_linter(path_obj)
                if not linter:
                    return ToolResult(
                        success=False,
                        output="",
                        error="Could not auto-detect linter. Please specify linter explicitly."
                    )
            
            # Check if linter is available
            if not self._is_linter_available(linter):
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Linter '{linter}' is not installed. Please install it first."
                )
            
            # Run linter
            errors = self._run_linter(linter, path_obj)
            
            # Limit errors
            if len(errors) > max_errors:
                errors = errors[:max_errors]
                truncated = True
            else:
                truncated = False
            
            # Format output
            if not errors:
                output = f"✓ No linter errors found using {linter}\n"
                output += f"Checked: {path}"
            else:
                output = f"Found {len(errors)} linter error(s) using {linter}:\n\n"
                output += self._format_errors(errors)
                
                if truncated:
                    output += f"\n\n(Results limited to {max_errors} errors. Use max_errors parameter to see more.)"
            
            return ToolResult(
                success=True,
                output=output,
                metadata={
                    "linter": linter,
                    "error_count": len(errors),
                    "errors": errors,
                    "truncated": truncated
                }
            )
        
        except Exception as e:
            logger.error(f"Error reading lints: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error reading lints: {str(e)}"
            )
    
    def _detect_linter(self, path: Path) -> Optional[str]:
        """
        Auto-detect appropriate linter based on file type.
        
        Args:
            path: Path to check
            
        Returns:
            Linter name or None
        """
        # Check if it's a file
        if path.is_file():
            suffix = path.suffix.lower()
            if suffix == ".py":
                # Prefer ruff > flake8 > pylint
                if self._is_linter_available("ruff"):
                    return "ruff"
                elif self._is_linter_available("flake8"):
                    return "flake8"
                elif self._is_linter_available("pylint"):
                    return "pylint"
            elif suffix in [".js", ".jsx", ".ts", ".tsx"]:
                if self._is_linter_available("eslint"):
                    return "eslint"
        else:
            # For directories, check for config files
            if (path / "setup.py").exists() or (path / "pyproject.toml").exists():
                if self._is_linter_available("ruff"):
                    return "ruff"
                elif self._is_linter_available("flake8"):
                    return "flake8"
            elif (path / "package.json").exists():
                if self._is_linter_available("eslint"):
                    return "eslint"
        
        return None
    
    def _is_linter_available(self, linter: str) -> bool:
        """
        Check if linter is available.
        
        Args:
            linter: Linter name
            
        Returns:
            True if available
        """
        try:
            result = subprocess.run(
                [linter, "--version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError):
            return False
    
    def _run_linter(self, linter: str, path: Path) -> List[Dict[str, Any]]:
        """
        Run linter and parse errors.
        
        Args:
            linter: Linter name
            path: Path to check
            
        Returns:
            List of error dictionaries
        """
        if linter == "flake8":
            return self._run_flake8(path)
        elif linter == "pylint":
            return self._run_pylint(path)
        elif linter == "ruff":
            return self._run_ruff(path)
        elif linter == "eslint":
            return self._run_eslint(path)
        else:
            return []
    
    def _run_flake8(self, path: Path) -> List[Dict[str, Any]]:
        """Run flake8 and parse output."""
        try:
            result = subprocess.run(
                ["flake8", "--format=json", str(path)],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # flake8 with json format (requires flake8-json plugin)
            # If not available, fall back to default format
            if result.stdout and result.stdout.startswith('['):
                try:
                    data = json.loads(result.stdout)
                    errors = []
                    for item in data:
                        errors.append({
                            "file": item.get("filename", ""),
                            "line": item.get("line_number", 0),
                            "column": item.get("column_number", 0),
                            "code": item.get("code", ""),
                            "message": item.get("text", ""),
                            "severity": "error"
                        })
                    return errors
                except json.JSONDecodeError:
                    pass
            
            # Fall back to parsing default format
            # Format: path:line:column: code message
            errors = []
            for line in result.stdout.splitlines():
                if not line.strip():
                    continue
                parts = line.split(":", 3)
                if len(parts) >= 4:
                    errors.append({
                        "file": parts[0].strip(),
                        "line": int(parts[1].strip()) if parts[1].strip().isdigit() else 0,
                        "column": int(parts[2].strip()) if parts[2].strip().isdigit() else 0,
                        "code": "",
                        "message": parts[3].strip(),
                        "severity": "error"
                    })
            return errors
        
        except Exception as e:
            logger.error(f"Error running flake8: {e}")
            return []
    
    def _run_pylint(self, path: Path) -> List[Dict[str, Any]]:
        """Run pylint and parse output."""
        try:
            result = subprocess.run(
                ["pylint", "--output-format=json", str(path)],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.stdout:
                try:
                    data = json.loads(result.stdout)
                    errors = []
                    for item in data:
                        errors.append({
                            "file": item.get("path", ""),
                            "line": item.get("line", 0),
                            "column": item.get("column", 0),
                            "code": item.get("message-id", ""),
                            "message": item.get("message", ""),
                            "severity": item.get("type", "error")
                        })
                    return errors
                except json.JSONDecodeError:
                    pass
            
            return []
        
        except Exception as e:
            logger.error(f"Error running pylint: {e}")
            return []
    
    def _run_ruff(self, path: Path) -> List[Dict[str, Any]]:
        """Run ruff and parse output."""
        try:
            result = subprocess.run(
                ["ruff", "check", "--output-format=json", str(path)],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.stdout:
                try:
                    data = json.loads(result.stdout)
                    errors = []
                    for item in data:
                        errors.append({
                            "file": item.get("filename", ""),
                            "line": item.get("location", {}).get("row", 0),
                            "column": item.get("location", {}).get("column", 0),
                            "code": item.get("code", ""),
                            "message": item.get("message", ""),
                            "severity": "error"
                        })
                    return errors
                except json.JSONDecodeError:
                    pass
            
            return []
        
        except Exception as e:
            logger.error(f"Error running ruff: {e}")
            return []
    
    def _run_eslint(self, path: Path) -> List[Dict[str, Any]]:
        """Run eslint and parse output."""
        try:
            result = subprocess.run(
                ["eslint", "--format=json", str(path)],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.stdout:
                try:
                    data = json.loads(result.stdout)
                    errors = []
                    for file_result in data:
                        for message in file_result.get("messages", []):
                            errors.append({
                                "file": file_result.get("filePath", ""),
                                "line": message.get("line", 0),
                                "column": message.get("column", 0),
                                "code": message.get("ruleId", ""),
                                "message": message.get("message", ""),
                                "severity": "error" if message.get("severity") == 2 else "warning"
                            })
                    return errors
                except json.JSONDecodeError:
                    pass
            
            return []
        
        except Exception as e:
            logger.error(f"Error running eslint: {e}")
            return []
    
    def _format_errors(self, errors: List[Dict[str, Any]]) -> str:
        """
        Format errors for display.
        
        Args:
            errors: List of error dictionaries
            
        Returns:
            Formatted string
        """
        output = []
        current_file = None
        
        for error in errors:
            file_path = error.get("file", "")
            
            # Print file header if changed
            if file_path != current_file:
                if current_file is not None:
                    output.append("")
                output.append(f"=== {file_path} ===")
                current_file = file_path
            
            # Format error line
            line = error.get("line", 0)
            column = error.get("column", 0)
            code = error.get("code", "")
            message = error.get("message", "")
            severity = error.get("severity", "error")
            
            # Severity icon
            icon = "❌" if severity == "error" else "⚠️"
            
            # Build error line
            error_line = f"{icon} Line {line}"
            if column:
                error_line += f":{column}"
            if code:
                error_line += f" [{code}]"
            error_line += f" {message}"
            
            output.append(error_line)
        
        return "\n".join(output)
