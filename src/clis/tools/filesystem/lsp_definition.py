"""
LSP-based definition finder - precise code navigation using language intelligence.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)

# Check if jedi is available
try:
    import jedi
    JEDI_AVAILABLE = True
except ImportError:
    JEDI_AVAILABLE = False


class LSPDefinitionTool(Tool):
    """Find symbol definitions using LSP/Jedi for precise code intelligence."""
    
    @property
    def name(self) -> str:
        return "lsp_definition"
    
    @property
    def description(self) -> str:
        return (
            "Find precise symbol definitions using Language Server Protocol (LSP). "
            "More accurate than regex-based find_definition. "
            "Works with Python code, understands imports, scopes, and context. "
            "Requires: pip install 'clis[lsp]'"
        )
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Symbol name to find (function, class, variable, method)"
                },
                "file": {
                    "type": "string",
                    "description": "File where the symbol is referenced (helps with context)",
                    "default": None
                },
                "line": {
                    "type": "integer",
                    "description": "Line number where symbol appears (for precise context)",
                    "default": None
                },
                "column": {
                    "type": "integer",
                    "description": "Column number (for precise context)",
                    "default": None
                },
                "project_path": {
                    "type": "string",
                    "description": "Project root path (default: current directory)",
                    "default": "."
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
        file: Optional[str] = None,
        line: Optional[int] = None,
        column: Optional[int] = None,
        project_path: str = "."
    ) -> ToolResult:
        """
        Execute LSP-based definition search.
        
        Args:
            symbol: Symbol name to find
            file: File where symbol is referenced
            line: Line number in file
            column: Column number in file
            project_path: Project root path
            
        Returns:
            ToolResult with definition locations
        """
        if not JEDI_AVAILABLE:
            return ToolResult(
                success=False,
                output="",
                error=(
                    "Jedi not installed. Install with: pip install 'clis[lsp]'\n"
                    "Falling back to find_definition tool for regex-based search."
                )
            )
        
        try:
            project_root = Path(project_path).expanduser().resolve()
            
            if not project_root.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Project path does not exist: {project_path}"
                )
            
            # Create Jedi project
            jedi_project = jedi.Project(path=str(project_root))
            
            results = []
            
            # Method 1: If file, line, column provided - use goto definition
            if file and line is not None and column is not None:
                file_path = Path(file).expanduser()
                if not file_path.is_absolute():
                    file_path = project_root / file_path
                
                if file_path.exists():
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            source = f.read()
                        
                        script = jedi.Script(
                            code=source,
                            path=str(file_path),
                            project=jedi_project
                        )
                        
                        # Get definitions at cursor position
                        definitions = script.goto(line, column, follow_imports=True)
                        
                        for definition in definitions:
                            results.append(self._format_definition(definition, 'goto'))
                    
                    except Exception as e:
                        logger.warning(f"Failed to analyze {file_path}: {e}")
            
            # Method 2: Search for symbol in project
            if not results:
                # Search across all Python files
                python_files = list(project_root.rglob('*.py'))
                
                for py_file in python_files[:100]:  # Limit to 100 files
                    # Skip common ignore patterns
                    if any(ignore in str(py_file) for ignore in ['__pycache__', '.venv', 'venv', 'node_modules']):
                        continue
                    
                    try:
                        with open(py_file, 'r', encoding='utf-8') as f:
                            source = f.read()
                        
                        # Check if symbol appears in this file
                        if symbol not in source:
                            continue
                        
                        script = jedi.Script(
                            code=source,
                            path=str(py_file),
                            project=jedi_project
                        )
                        
                        # Search for definitions in this file
                        names = script.get_names(all_scopes=True)
                        
                        for name in names:
                            if name.name == symbol and name.type in ['class', 'function', 'module', 'instance']:
                                # Get the definition
                                try:
                                    definitions = name.goto(follow_imports=True)
                                    for definition in definitions:
                                        if definition.type != 'statement':  # Filter out usages
                                            result = self._format_definition(definition, 'search')
                                            if result and result not in results:
                                                results.append(result)
                                except:
                                    pass
                    
                    except (UnicodeDecodeError, PermissionError, OSError):
                        continue
            
            # Format output
            if not results:
                output = f"No LSP definition found for symbol: '{symbol}'\n\n"
                output += "💡 Tips:\n"
                output += "  - Make sure the symbol name is correct\n"
                output += "  - For better results, provide file, line, and column\n"
                output += "  - Try using find_definition for regex-based search\n"
                
                if file:
                    output += f"\nSearched in context of: {file}\n"
            else:
                # Remove duplicates
                unique_results = []
                seen = set()
                for result in results:
                    key = (result['file'], result['line'])
                    if key not in seen:
                        seen.add(key)
                        unique_results.append(result)
                
                output = f"Found {len(unique_results)} precise definition(s) for: '{symbol}'\n"
                output += "(Using Jedi/LSP for accurate code analysis)\n\n"
                
                for i, result in enumerate(unique_results, 1):
                    output += "="*70 + "\n"
                    output += f"Definition {i}/{len(unique_results)}\n"
                    output += "="*70 + "\n"
                    output += f"Type:        {result['type']}\n"
                    output += f"File:        {result['file']}\n"
                    output += f"Line:        {result['line']}\n"
                    
                    if result.get('full_name'):
                        output += f"Full Name:   {result['full_name']}\n"
                    
                    if result.get('module'):
                        output += f"Module:      {result['module']}\n"
                    
                    if result.get('docstring'):
                        doc_preview = result['docstring'].split('\n')[0][:60]
                        output += f"Docstring:   {doc_preview}...\n"
                    
                    if result.get('signature'):
                        output += f"Signature:   {result['signature']}\n"
                    
                    output += "\nContext:\n"
                    if result.get('context'):
                        for ctx_line in result['context'][:5]:
                            output += f"  {ctx_line}\n"
                    
                    output += "\n"
            
            return ToolResult(
                success=True,
                output=output,
                metadata={
                    'count': len(results),
                    'results': results,
                    'method': 'lsp' if JEDI_AVAILABLE else 'fallback'
                }
            )
        
        except Exception as e:
            logger.error(f"Error during LSP definition search: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error during LSP definition search: {str(e)}"
            )
    
    def _format_definition(self, definition: Any, method: str) -> Optional[Dict[str, Any]]:
        """Format Jedi definition object into a dictionary."""
        try:
            # Get file path
            module_path = definition.module_path
            if not module_path:
                return None
            
            file_path = Path(module_path)
            
            # Make path relative if possible
            try:
                if file_path.is_relative_to(Path.cwd()):
                    file_path_str = str(file_path.relative_to(Path.cwd()))
                else:
                    file_path_str = str(file_path)
            except:
                file_path_str = str(file_path)
            
            # Get context lines
            context = []
            try:
                if definition.line is not None:
                    with open(module_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        start_idx = max(0, definition.line - 3)
                        end_idx = min(len(lines), definition.line + 2)
                        for i in range(start_idx, end_idx):
                            prefix = "→" if i == definition.line - 1 else " "
                            context.append(f"{prefix} {i+1:4d} | {lines[i].rstrip()}")
            except:
                pass
            
            # Get signature
            signature = None
            try:
                if hasattr(definition, 'get_signatures'):
                    sigs = definition.get_signatures()
                    if sigs:
                        signature = str(sigs[0])
            except:
                pass
            
            return {
                'name': definition.name,
                'type': definition.type,
                'file': file_path_str,
                'line': definition.line,
                'column': definition.column,
                'full_name': definition.full_name,
                'module': definition.module_name,
                'docstring': definition.docstring,
                'signature': signature,
                'context': context,
                'method': method
            }
        
        except Exception as e:
            logger.warning(f"Failed to format definition: {e}")
            return None
