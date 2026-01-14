"""
LSP-based reference finder - find all usages of a symbol with precision.
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


class LSPReferencesTool(Tool):
    """Find all references to a symbol using LSP for precise code intelligence."""
    
    @property
    def name(self) -> str:
        return "lsp_references"
    
    @property
    def description(self) -> str:
        return (
            "Find all references/usages of a symbol using Language Server Protocol. "
            "More accurate than grep-based find_references. "
            "Understands Python imports, scopes, and distinguishes similar names. "
            "Requires: pip install 'clis[lsp]'"
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
                "file": {
                    "type": "string",
                    "description": "File containing the symbol (for context)",
                    "default": None
                },
                "line": {
                    "type": "integer",
                    "description": "Line number where symbol is defined/used",
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
                },
                "include_definition": {
                    "type": "boolean",
                    "description": "Include the definition itself (default: true)",
                    "default": True
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
        project_path: str = ".",
        include_definition: bool = True
    ) -> ToolResult:
        """
        Execute LSP-based reference search.
        
        Args:
            symbol: Symbol name
            file: File containing symbol
            line: Line number
            column: Column number
            project_path: Project root
            include_definition: Include definition in results
            
        Returns:
            ToolResult with reference locations
        """
        if not JEDI_AVAILABLE:
            return ToolResult(
                success=False,
                output="",
                error=(
                    "Jedi not installed. Install with: pip install 'clis[lsp]'\n"
                    "Falling back to find_references tool for grep-based search."
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
            
            references = []
            
            # Method 1: If file, line, column provided - use precise references
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
                        
                        # Get references at cursor position
                        refs = script.get_references(line, column, include_builtins=False)
                        
                        for ref in refs:
                            ref_info = self._format_reference(ref)
                            if ref_info:
                                # Filter definition if needed
                                if not include_definition and ref_info.get('is_definition'):
                                    continue
                                references.append(ref_info)
                    
                    except Exception as e:
                        logger.warning(f"Failed to analyze {file_path}: {e}")
            
            # Method 2: Search for symbol usage across project
            if not references:
                python_files = list(project_root.rglob('*.py'))
                
                for py_file in python_files[:100]:  # Limit
                    # Skip ignored
                    if any(ignore in str(py_file) for ignore in ['__pycache__', '.venv', 'venv']):
                        continue
                    
                    try:
                        with open(py_file, 'r', encoding='utf-8') as f:
                            source = f.read()
                        
                        if symbol not in source:
                            continue
                        
                        script = jedi.Script(
                            code=source,
                            path=str(py_file),
                            project=jedi_project
                        )
                        
                        # Get all names in file
                        names = script.get_names(all_scopes=True, definitions=True, references=True)
                        
                        for name in names:
                            if name.name == symbol:
                                ref_info = self._format_reference(name)
                                if ref_info:
                                    if not include_definition and ref_info.get('is_definition'):
                                        continue
                                    if ref_info not in references:
                                        references.append(ref_info)
                    
                    except (UnicodeDecodeError, PermissionError, OSError):
                        continue
            
            # Group by file
            references_by_file = {}
            for ref in references:
                file_path = ref['file']
                if file_path not in references_by_file:
                    references_by_file[file_path] = []
                references_by_file[file_path].append(ref)
            
            # Sort references within each file by line number
            for file_refs in references_by_file.values():
                file_refs.sort(key=lambda x: x['line'])
            
            # Format output
            if not references:
                output = f"No LSP references found for symbol: '{symbol}'\n\n"
                output += "💡 Tips:\n"
                output += "  - Provide file, line, column for better accuracy\n"
                output += "  - Symbol might not be used in the project\n"
                output += "  - Try find_references for grep-based search\n"
            else:
                output = f"Found {len(references)} reference(s) to '{symbol}' across {len(references_by_file)} file(s)\n"
                output += "(Using Jedi/LSP for accurate analysis)\n\n"
                
                for file_path, file_refs in references_by_file.items():
                    output += "="*70 + "\n"
                    output += f"📄 {file_path} ({len(file_refs)} reference(s))\n"
                    output += "="*70 + "\n\n"
                    
                    for ref in file_refs:
                        prefix = "🔷" if ref.get('is_definition') else "→"
                        type_label = f" [{ref['type']}]" if ref.get('type') else ""
                        def_label = " [DEFINITION]" if ref.get('is_definition') else ""
                        
                        output += f"{prefix} Line {ref['line']:4d}:{ref['column']:3d} "
                        output += f"{type_label}{def_label}\n"
                        
                        # Show context
                        if ref.get('context_line'):
                            output += f"        {ref['context_line']}\n"
                        
                        output += "\n"
            
            return ToolResult(
                success=True,
                output=output,
                metadata={
                    'count': len(references),
                    'files': len(references_by_file),
                    'references_by_file': {k: len(v) for k, v in references_by_file.items()},
                    'method': 'lsp'
                }
            )
        
        except Exception as e:
            logger.error(f"Error during LSP reference search: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error during LSP reference search: {str(e)}"
            )
    
    def _format_reference(self, ref: Any) -> Optional[Dict[str, Any]]:
        """Format Jedi reference object."""
        try:
            module_path = ref.module_path
            if not module_path:
                return None
            
            file_path = Path(module_path)
            
            # Make relative if possible
            try:
                if file_path.is_relative_to(Path.cwd()):
                    file_path_str = str(file_path.relative_to(Path.cwd()))
                else:
                    file_path_str = str(file_path)
            except:
                file_path_str = str(file_path)
            
            # Get context line
            context_line = None
            try:
                if ref.line is not None:
                    with open(module_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        if 0 <= ref.line - 1 < len(lines):
                            context_line = lines[ref.line - 1].strip()
            except:
                pass
            
            # Determine if this is a definition
            is_definition = ref.type in ['class', 'function', 'module']
            
            return {
                'name': ref.name,
                'type': ref.type,
                'file': file_path_str,
                'line': ref.line,
                'column': ref.column,
                'context_line': context_line,
                'is_definition': is_definition,
                'full_name': getattr(ref, 'full_name', None)
            }
        
        except Exception as e:
            logger.warning(f"Failed to format reference: {e}")
            return None
