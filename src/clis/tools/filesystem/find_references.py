"""
Find references tool - locate all references to a symbol.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class FindReferencesTool(Tool):
    """Find all references to a symbol in the codebase."""
    
    @property
    def name(self) -> str:
        return "find_references"
    
    @property
    def description(self) -> str:
        return (
            "Find all references/usages of a symbol (function, class, variable) in the codebase. "
            "Shows where the symbol is used/called/imported. "
            "Essential for refactoring to understand impact of changes."
        )
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Symbol name to find references for"
                },
                "path": {
                    "type": "string",
                    "description": "Path to search in (file or directory, default: current directory)",
                    "default": "."
                },
                "file_pattern": {
                    "type": "string",
                    "description": "File pattern to filter (e.g., '*.py', '*.js', default: source code files)",
                    "default": None
                },
                "include_definition": {
                    "type": "boolean",
                    "description": "Include the definition line in results (default: false)",
                    "default": False
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 100)",
                    "default": 100
                }
            },
            "required": ["symbol"]
        }
    
    @property
    def is_readonly(self) -> bool:
        return True
    
    def execute(
        self,
        symbol: str,
        path: str = ".",
        file_pattern: Optional[str] = None,
        include_definition: bool = False,
        max_results: int = 100
    ) -> ToolResult:
        """
        Execute find references search.
        
        Args:
            symbol: Symbol name to find references for
            path: Path to search in
            file_pattern: File pattern filter
            include_definition: Include definition line
            max_results: Maximum results
            
        Returns:
            ToolResult with reference locations
        """
        try:
            path_obj = Path(path).expanduser()
            
            if not path_obj.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Path does not exist: {path}"
                )
            
            # Build reference pattern (word boundary for exact matches)
            reference_pattern = re.compile(rf'\b{re.escape(symbol)}\b')
            
            # Definition patterns to exclude (unless include_definition=True)
            definition_patterns = [
                re.compile(rf'^\s*def\s+{re.escape(symbol)}\s*\('),  # Python function
                re.compile(rf'^\s*class\s+{re.escape(symbol)}\s*[:\(]'),  # Python/Java class
                re.compile(rf'^\s*(function|const|let|var)\s+{re.escape(symbol)}\s*[=\(]'),  # JS function
                re.compile(rf'^\s*interface\s+{re.escape(symbol)}\s*\{{'),  # TS interface
                re.compile(rf'^\s*type\s+{re.escape(symbol)}\s*='),  # TS type
            ]
            
            # Search files
            results = []
            files_searched = 0
            references_by_file = {}
            
            # Default source code extensions
            default_patterns = ['*.py', '*.js', '*.ts', '*.jsx', '*.tsx', '*.java', 
                              '*.cpp', '*.c', '*.h', '*.go', '*.rs', '*.rb', '*.php']
            
            if path_obj.is_file():
                files_to_search = [path_obj]
            else:
                if file_pattern:
                    files_to_search = list(path_obj.rglob(file_pattern))
                else:
                    files_to_search = []
                    for pattern in default_patterns:
                        files_to_search.extend(path_obj.rglob(pattern))
            
            for file_path in files_to_search:
                if not file_path.is_file():
                    continue
                
                # Skip hidden and ignored
                if any(part.startswith('.') for part in file_path.parts):
                    continue
                if any(ignore in str(file_path) for ignore in ['node_modules', '__pycache__', '.venv', 'venv']):
                    continue
                
                files_searched += 1
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    
                    file_refs = []
                    
                    for line_num, line in enumerate(lines, 1):
                        # Check if this is a reference
                        if reference_pattern.search(line):
                            # Skip if it's a definition (unless include_definition=True)
                            is_definition = any(pattern.match(line) for pattern in definition_patterns)
                            if is_definition and not include_definition:
                                continue
                            
                            file_refs.append({
                                'line': line_num,
                                'content': line.strip(),
                                'is_definition': is_definition
                            })
                            
                            if len(results) >= max_results:
                                break
                    
                    if file_refs:
                        file_path_str = str(file_path.relative_to(Path.cwd()) if file_path.is_relative_to(Path.cwd()) else file_path)
                        references_by_file[file_path_str] = file_refs
                        results.extend(file_refs)
                
                except (UnicodeDecodeError, PermissionError, OSError):
                    continue
                
                if len(results) >= max_results:
                    break
            
            # Format output
            if not results:
                output = f"No references found for symbol: '{symbol}'\n"
                output += f"Searched {files_searched} files in {path}\n"
                output += f"Tip: Symbol might not be used, or check spelling"
            else:
                output = f"Found {len(results)} reference(s) to: '{symbol}'\n"
                output += f"Across {len(references_by_file)} file(s)\n\n"
                
                for file_path_str, file_refs in references_by_file.items():
                    output += f"\n{'='*70}\n"
                    output += f"📄 {file_path_str} ({len(file_refs)} reference(s))\n"
                    output += f"{'='*70}\n\n"
                    
                    for ref in file_refs:
                        prefix = "🔷" if ref['is_definition'] else "→"
                        type_label = " [DEFINITION]" if ref['is_definition'] else ""
                        output += f"{prefix} {ref['line']:4d} | {ref['content']}{type_label}\n"
                
                if len(results) >= max_results:
                    output += f"\n⚠️  Results limited to {max_results}. Use max_results parameter to see more.\n"
            
            return ToolResult(
                success=True,
                output=output,
                metadata={
                    'count': len(results),
                    'files': len(references_by_file),
                    'files_searched': files_searched,
                    'references_by_file': references_by_file
                }
            )
        
        except Exception as e:
            logger.error(f"Error finding references: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error finding references: {str(e)}"
            )
