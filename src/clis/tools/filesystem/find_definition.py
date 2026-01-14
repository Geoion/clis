"""
Find definition tool - locate where a symbol is defined.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class FindDefinitionTool(Tool):
    """Find where a symbol (function, class, variable) is defined."""
    
    @property
    def name(self) -> str:
        return "find_definition"
    
    @property
    def description(self) -> str:
        return (
            "Find where a symbol (function, class, variable) is defined. "
            "Searches for definition patterns like 'def function_name', 'class ClassName', etc. "
            "Helps understand code structure and navigate to implementations."
        )
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Symbol name to find (function, class, or variable name)"
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
                "symbol_type": {
                    "type": "string",
                    "enum": ["auto", "function", "class", "variable", "constant"],
                    "description": "Type of symbol to find (default: auto-detect)",
                    "default": "auto"
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
        symbol_type: str = "auto"
    ) -> ToolResult:
        """
        Execute find definition search.
        
        Args:
            symbol: Symbol name to find
            path: Path to search in
            file_pattern: File pattern filter
            symbol_type: Type of symbol
            
        Returns:
            ToolResult with definition locations
        """
        try:
            path_obj = Path(path).expanduser()
            
            if not path_obj.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Path does not exist: {path}"
                )
            
            # Build definition patterns based on language
            patterns = self._build_definition_patterns(symbol, symbol_type)
            
            # Search files
            results = []
            files_searched = 0
            
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
                    
                    # Search for definition patterns
                    for line_num, line in enumerate(lines, 1):
                        for pattern_info in patterns:
                            if pattern_info['regex'].search(line):
                                # Get context
                                start_idx = max(0, line_num - 3)
                                end_idx = min(len(lines), line_num + 3)
                                context_lines = [
                                    (i + 1, lines[i].rstrip())
                                    for i in range(start_idx, end_idx)
                                ]
                                
                                results.append({
                                    'file': str(file_path.relative_to(Path.cwd()) if file_path.is_relative_to(Path.cwd()) else file_path),
                                    'line': line_num,
                                    'type': pattern_info['type'],
                                    'content': line.strip(),
                                    'context': context_lines
                                })
                                break  # Found in this line, move to next line
                
                except (UnicodeDecodeError, PermissionError, OSError):
                    continue
            
            # Format output
            if not results:
                output = f"No definition found for symbol: '{symbol}'\n"
                output += f"Searched {files_searched} files in {path}\n"
                output += f"Tip: Check spelling or try searching in a different directory"
            else:
                output = f"Found {len(results)} definition(s) for: '{symbol}'\n\n"
                
                for i, result in enumerate(results, 1):
                    output += f"\n{'='*70}\n"
                    output += f"Definition {i}/{len(results)} - {result['type']}\n"
                    output += f"📄 {result['file']}:{result['line']}\n"
                    output += f"{'='*70}\n\n"
                    
                    for ctx_line_num, ctx_content in result['context']:
                        if ctx_line_num == result['line']:
                            output += f"→ {ctx_line_num:4d} | {ctx_content}\n"
                        else:
                            output += f"  {ctx_line_num:4d} | {ctx_content}\n"
            
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
            logger.error(f"Error finding definition: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error finding definition: {str(e)}"
            )
    
    def _build_definition_patterns(self, symbol: str, symbol_type: str) -> List[Dict[str, Any]]:
        """Build regex patterns for finding definitions."""
        patterns = []
        
        if symbol_type in ["auto", "function"]:
            # Python: def function_name
            patterns.append({
                'type': 'function',
                'regex': re.compile(rf'^\s*def\s+{re.escape(symbol)}\s*\(')
            })
            # JavaScript/TypeScript: function functionName / const func = 
            patterns.append({
                'type': 'function',
                'regex': re.compile(rf'^\s*(function|const|let|var)\s+{re.escape(symbol)}\s*[=\(]')
            })
            # Go: func functionName
            patterns.append({
                'type': 'function',
                'regex': re.compile(rf'^\s*func\s+{re.escape(symbol)}\s*\(')
            })
        
        if symbol_type in ["auto", "class"]:
            # Python/Java/C++: class ClassName
            patterns.append({
                'type': 'class',
                'regex': re.compile(rf'^\s*class\s+{re.escape(symbol)}\s*[:\(\{{]')
            })
            # TypeScript: interface InterfaceName
            patterns.append({
                'type': 'interface',
                'regex': re.compile(rf'^\s*interface\s+{re.escape(symbol)}\s*\{{')
            })
            # TypeScript: type TypeName
            patterns.append({
                'type': 'type',
                'regex': re.compile(rf'^\s*type\s+{re.escape(symbol)}\s*=')
            })
        
        if symbol_type in ["auto", "variable", "constant"]:
            # Python: CONSTANT = or variable =
            patterns.append({
                'type': 'variable',
                'regex': re.compile(rf'^\s*{re.escape(symbol)}\s*=')
            })
            # JavaScript: const/let/var
            patterns.append({
                'type': 'variable',
                'regex': re.compile(rf'^\s*(const|let|var)\s+{re.escape(symbol)}\s*=')
            })
        
        return patterns
