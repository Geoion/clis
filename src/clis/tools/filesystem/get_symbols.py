"""
Get symbols tool - extract all symbols (functions, classes, etc.) from a file.
"""

import re
from pathlib import Path
from typing import Any, Dict, List

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class GetSymbolsTool(Tool):
    """Extract all symbols (functions, classes, methods, etc.) from a file."""
    
    @property
    def name(self) -> str:
        return "get_symbols"
    
    @property
    def description(self) -> str:
        return (
            "Extract all symbols (functions, classes, methods, variables) from a file. "
            "Provides an outline/overview of file structure. "
            "Useful for understanding large files and navigating code."
        )
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path to extract symbols from"
                },
                "symbol_types": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["function", "class", "method", "variable", "constant", "all"]
                    },
                    "description": "Types of symbols to extract (default: all)",
                    "default": ["all"]
                },
                "include_private": {
                    "type": "boolean",
                    "description": "Include private symbols (starting with _) (default: true)",
                    "default": True
                }
            },
            "required": ["path"]
        }
    
    @property
    def is_readonly(self) -> bool:
        return True
    
    def execute(
        self,
        path: str,
        symbol_types: List[str] = None,
        include_private: bool = True
    ) -> ToolResult:
        """
        Execute symbol extraction.
        
        Args:
            path: File path
            symbol_types: Types of symbols to extract
            include_private: Include private symbols
            
        Returns:
            ToolResult with extracted symbols
        """
        try:
            if symbol_types is None:
                symbol_types = ["all"]
            
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
            
            # Read file
            try:
                with open(path_obj, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            except UnicodeDecodeError:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"File is not a text file: {path}"
                )
            
            # Extract symbols based on file extension
            file_ext = path_obj.suffix
            symbols = self._extract_symbols(lines, file_ext, symbol_types, include_private)
            
            # Format output
            if not symbols:
                output = f"No symbols found in {path}\n"
                output += f"File might be empty or use unsupported syntax"
            else:
                output = f"Symbols in {path}:\n"
                output += f"Total: {len(symbols)} symbol(s)\n\n"
                
                # Group by type
                by_type = {}
                for symbol in symbols:
                    symbol_type = symbol['type']
                    if symbol_type not in by_type:
                        by_type[symbol_type] = []
                    by_type[symbol_type].append(symbol)
                
                # Display by type
                for symbol_type in ['class', 'function', 'method', 'variable', 'constant']:
                    if symbol_type in by_type:
                        items = by_type[symbol_type]
                        output += f"\n{'='*70}\n"
                        output += f"{symbol_type.upper()}S ({len(items)})\n"
                        output += f"{'='*70}\n"
                        
                        for item in items:
                            indent = "  " * item.get('indent_level', 0)
                            visibility = "🔒" if item['name'].startswith('_') else "🔓"
                            output += f"{visibility} {indent}Line {item['line']:4d}: {item['name']}"
                            if item.get('signature'):
                                output += f"{item['signature']}"
                            output += "\n"
            
            return ToolResult(
                success=True,
                output=output,
                metadata={
                    'count': len(symbols),
                    'symbols': symbols,
                    'by_type': {k: len(v) for k, v in by_type.items()} if symbols else {}
                }
            )
        
        except Exception as e:
            logger.error(f"Error extracting symbols: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error extracting symbols: {str(e)}"
            )
    
    def _extract_symbols(
        self,
        lines: List[str],
        file_ext: str,
        symbol_types: List[str],
        include_private: bool
    ) -> List[Dict[str, Any]]:
        """Extract symbols from file lines."""
        symbols = []
        current_class = None
        
        # Define patterns based on file type
        patterns = {
            'class': [
                (re.compile(r'^\s*class\s+(\w+)\s*(\([^)]*\))?\s*:'), 'Python'),  # Python
                (re.compile(r'^\s*class\s+(\w+)\s*(\{|extends|implements)'), 'Java/JS'),  # Java/JS
                (re.compile(r'^\s*interface\s+(\w+)\s*\{'), 'TypeScript Interface'),  # TS
                (re.compile(r'^\s*type\s+(\w+)\s*='), 'TypeScript Type'),  # TS
            ],
            'function': [
                (re.compile(r'^\s*def\s+(\w+)\s*\(([^)]*)\)'), 'Python'),  # Python
                (re.compile(r'^\s*(function|async\s+function)\s+(\w+)\s*\(([^)]*)\)'), 'JavaScript'),  # JS
                (re.compile(r'^\s*(const|let|var)\s+(\w+)\s*=\s*(async\s*)?\(([^)]*)\)\s*=>'), 'Arrow Function'),  # JS arrow
                (re.compile(r'^\s*func\s+(\w+)\s*\(([^)]*)\)'), 'Go'),  # Go
            ],
            'method': [
                (re.compile(r'^\s+def\s+(\w+)\s*\(([^)]*)\)'), 'Python Method'),  # Python (indented)
                (re.compile(r'^\s+(\w+)\s*\(([^)]*)\)\s*\{'), 'Java/JS Method'),  # Java/JS
            ],
            'variable': [
                (re.compile(r'^\s*(const|let|var)\s+(\w+)\s*='), 'JS Variable'),  # JS
                (re.compile(r'^\s*(\w+)\s*=\s*[^=]'), 'Variable'),  # Generic
            ],
        }
        
        for line_num, line in enumerate(lines, 1):
            indent_level = (len(line) - len(line.lstrip())) // 4
            
            # Check classes
            if "all" in symbol_types or "class" in symbol_types:
                for pattern, lang in patterns['class']:
                    match = pattern.match(line)
                    if match:
                        name = match.group(1)
                        if include_private or not name.startswith('_'):
                            signature = match.group(2) if match.lastindex >= 2 else ""
                            symbols.append({
                                'name': name,
                                'type': 'class',
                                'line': line_num,
                                'signature': signature,
                                'indent_level': indent_level,
                                'language': lang
                            })
                            current_class = name
                        break
            
            # Check functions
            if "all" in symbol_types or "function" in symbol_types:
                for pattern, lang in patterns['function']:
                    match = pattern.match(line)
                    if match:
                        # Extract name (might be in different groups depending on pattern)
                        name = match.group(2) if 'function' in match.group(0) and match.lastindex >= 2 else match.group(1)
                        if include_private or not name.startswith('_'):
                            params = match.group(match.lastindex) if match.lastindex >= 2 else ""
                            symbols.append({
                                'name': name,
                                'type': 'function',
                                'line': line_num,
                                'signature': f"({params})",
                                'indent_level': indent_level,
                                'language': lang
                            })
                        break
            
            # Check methods (indented functions inside classes)
            if "all" in symbol_types or "method" in symbol_types:
                for pattern, lang in patterns['method']:
                    match = pattern.match(line)
                    if match and current_class:
                        name = match.group(1)
                        if include_private or not name.startswith('_'):
                            params = match.group(2) if match.lastindex >= 2 else ""
                            symbols.append({
                                'name': name,
                                'type': 'method',
                                'line': line_num,
                                'signature': f"({params})",
                                'indent_level': indent_level,
                                'class': current_class,
                                'language': lang
                            })
                        break
            
            # Check variables/constants
            if "all" in symbol_types or "variable" in symbol_types or "constant" in symbol_types:
                for pattern, lang in patterns['variable']:
                    match = pattern.match(line)
                    if match:
                        name = match.group(2) if match.lastindex >= 2 else match.group(1)
                        if include_private or not name.startswith('_'):
                            is_constant = name.isupper()
                            symbol_type = 'constant' if is_constant else 'variable'
                            if symbol_type in symbol_types or "all" in symbol_types:
                                symbols.append({
                                    'name': name,
                                    'type': symbol_type,
                                    'line': line_num,
                                    'signature': "",
                                    'indent_level': indent_level,
                                    'language': lang
                                })
                        break
            
            # Reset current_class if we're back at top level
            if indent_level == 0 and line.strip() and not line.strip().startswith('#'):
                if not any(p[0].match(line) for p in patterns['class']):
                    current_class = None
        
        return symbols
