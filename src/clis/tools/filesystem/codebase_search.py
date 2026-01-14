"""
Codebase search tool - semantic search across codebase.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class CodebaseSearchTool(Tool):
    """Semantic search across codebase using pattern matching and keyword scoring."""
    
    @property
    def name(self) -> str:
        return "codebase_search"
    
    @property
    def description(self) -> str:
        return (
            "Search codebase by meaning using natural language queries. "
            "Finds relevant code by understanding context and semantics. "
            "More powerful than grep for exploratory searches like 'where do we handle authentication?'"
        )
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query (e.g., 'how do we validate user input?')"
                },
                "target_directories": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Directories to search in (default: current directory)",
                    "default": ["."]
                },
                "file_pattern": {
                    "type": "string",
                    "description": "File pattern to filter (e.g., '*.py', '*.js', default: source code files)",
                    "default": None
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 20)",
                    "default": 20
                },
                "context_lines": {
                    "type": "integer",
                    "description": "Number of context lines to show (default: 3)",
                    "default": 3
                }
            },
            "required": ["query"]
        }
    
    @property
    def is_readonly(self) -> bool:
        return True
    
    def execute(
        self,
        query: str,
        target_directories: List[str] = None,
        file_pattern: Optional[str] = None,
        max_results: int = 20,
        context_lines: int = 3
    ) -> ToolResult:
        """
        Execute semantic codebase search.
        
        Args:
            query: Natural language search query
            target_directories: Directories to search
            file_pattern: File pattern filter
            max_results: Maximum results
            context_lines: Context lines to show
            
        Returns:
            ToolResult with search results
        """
        try:
            if target_directories is None:
                target_directories = ["."]
            
            # Extract keywords from query
            keywords = self._extract_keywords(query)
            
            if not keywords:
                return ToolResult(
                    success=False,
                    output="",
                    error="Could not extract meaningful keywords from query"
                )
            
            # Search files
            results = []
            files_searched = 0
            
            # Default source code extensions
            default_patterns = ['*.py', '*.js', '*.ts', '*.jsx', '*.tsx', '*.java', 
                              '*.cpp', '*.c', '*.h', '*.go', '*.rs', '*.rb', '*.php']
            
            for target_dir in target_directories:
                path_obj = Path(target_dir).expanduser()
                
                if not path_obj.exists():
                    continue
                
                # Collect files
                if file_pattern:
                    files_to_search = list(path_obj.rglob(file_pattern))
                else:
                    files_to_search = []
                    for pattern in default_patterns:
                        files_to_search.extend(path_obj.rglob(pattern))
                
                for file_path in files_to_search:
                    if not file_path.is_file():
                        continue
                    
                    # Skip hidden files and common ignore patterns
                    if any(part.startswith('.') for part in file_path.parts):
                        continue
                    if any(ignore in str(file_path) for ignore in ['node_modules', '__pycache__', '.venv', 'venv', 'dist', 'build']):
                        continue
                    
                    files_searched += 1
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                        
                        # Score each block of code
                        file_results = self._score_file(
                            file_path, lines, keywords, context_lines
                        )
                        results.extend(file_results)
                    
                    except (UnicodeDecodeError, PermissionError, OSError):
                        continue
            
            # Sort by relevance score
            results.sort(key=lambda x: x['score'], reverse=True)
            results = results[:max_results]
            
            # Format output
            if not results:
                output = f"No relevant code found for query: '{query}'\n"
                output += f"Searched {files_searched} files in {', '.join(target_directories)}\n"
                output += f"Keywords extracted: {', '.join(keywords)}"
            else:
                output = f"Found {len(results)} relevant code section(s) for: '{query}'\n"
                output += f"Searched {files_searched} files\n\n"
                
                for i, result in enumerate(results, 1):
                    output += f"\n{'='*70}\n"
                    output += f"Result {i}/{len(results)} - Score: {result['score']:.1f}\n"
                    output += f"📄 {result['file']}\n"
                    output += f"{'='*70}\n"
                    
                    # Show matched keywords
                    if result.get('matched_keywords'):
                        output += f"🎯 Matched: {', '.join(result['matched_keywords'])}\n\n"
                    
                    # Show code with context
                    for line_num, line_content in result['lines']:
                        if line_num == result['center_line']:
                            output += f"→ {line_num:4d} | {line_content}\n"
                        else:
                            output += f"  {line_num:4d} | {line_content}\n"
            
            return ToolResult(
                success=True,
                output=output,
                metadata={
                    'count': len(results),
                    'files_searched': files_searched,
                    'keywords': keywords,
                    'results': results
                }
            )
        
        except Exception as e:
            logger.error(f"Error during codebase search: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error during codebase search: {str(e)}"
            )
    
    def _extract_keywords(self, query: str) -> List[str]:
        """Extract meaningful keywords from natural language query."""
        # Remove common words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
            'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'should', 'could', 'may', 'might', 'can', 'we', 'they', 'i', 'you',
            'he', 'she', 'it', 'this', 'that', 'these', 'those', 'where', 'when',
            'how', 'what', 'which', 'who'
        }
        
        # Split and clean
        words = re.findall(r'\b\w+\b', query.lower())
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        
        return keywords
    
    def _score_file(
        self,
        file_path: Path,
        lines: List[str],
        keywords: List[str],
        context_lines: int
    ) -> List[Dict[str, Any]]:
        """Score code sections in a file based on keyword matches."""
        results = []
        
        for i, line in enumerate(lines):
            line_lower = line.lower()
            
            # Score this line
            score = 0
            matched_keywords = []
            
            for keyword in keywords:
                if keyword in line_lower:
                    # Exact word match gets higher score
                    if re.search(rf'\b{keyword}\b', line_lower):
                        score += 10
                    else:
                        score += 5
                    matched_keywords.append(keyword)
            
            # Check context for additional matches
            start_idx = max(0, i - context_lines)
            end_idx = min(len(lines), i + context_lines + 1)
            context = '\n'.join(lines[start_idx:end_idx]).lower()
            
            for keyword in keywords:
                if keyword not in matched_keywords and keyword in context:
                    score += 2
                    matched_keywords.append(keyword)
            
            # Only include if there's a match
            if score > 0:
                # Get context lines
                context_with_nums = []
                for j in range(start_idx, end_idx):
                    context_with_nums.append((j + 1, lines[j].rstrip()))
                
                results.append({
                    'file': str(file_path.relative_to(Path.cwd()) if file_path.is_relative_to(Path.cwd()) else file_path),
                    'center_line': i + 1,
                    'lines': context_with_nums,
                    'score': score,
                    'matched_keywords': matched_keywords
                })
        
        return results
