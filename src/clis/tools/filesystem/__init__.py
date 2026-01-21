"""
Filesystem tools for CLIS.
"""

from clis.tools.filesystem.delete_file import DeleteFileTool
from clis.tools.filesystem.edit_file import EditFileTool
from clis.tools.filesystem.grep import GrepTool
from clis.tools.filesystem.read_lints import ReadLintsTool
from clis.tools.filesystem.search_files import SearchFilesTool
from clis.tools.filesystem.file_tree import FileTreeTool
from clis.tools.filesystem.write_file import WriteFileTool
from clis.tools.filesystem.get_file_info import GetFileInfoTool
from clis.tools.filesystem.codebase_search import CodebaseSearchTool
from clis.tools.filesystem.search_replace import SearchReplaceTool
from clis.tools.filesystem.find_definition import FindDefinitionTool
from clis.tools.filesystem.find_references import FindReferencesTool
from clis.tools.filesystem.get_symbols import GetSymbolsTool

# Import new tools
from clis.tools.filesystem.insert_code import InsertCodeTool
from clis.tools.filesystem.delete_lines import DeleteLinesTool

# LSP-based tools (optional dependency)
try:
    from clis.tools.filesystem.lsp_definition import LSPDefinitionTool
    from clis.tools.filesystem.lsp_references import LSPReferencesTool
    LSP_TOOLS_AVAILABLE = True
except ImportError:
    LSP_TOOLS_AVAILABLE = False
    LSPDefinitionTool = None
    LSPReferencesTool = None

__all__ = [
    "DeleteFileTool",
    "EditFileTool",
    "GrepTool",
    "ReadLintsTool",
    "SearchFilesTool",
    "FileTreeTool",
    "WriteFileTool",
    "GetFileInfoTool",
    "CodebaseSearchTool",
    "SearchReplaceTool",
    "FindDefinitionTool",
    "FindReferencesTool",
    "GetSymbolsTool",
    "InsertCodeTool",
    "DeleteLinesTool",
]

# Add LSP tools if available
if LSP_TOOLS_AVAILABLE:
    __all__.extend(["LSPDefinitionTool", "LSPReferencesTool"])
