"""
Tool Vector Search - Semantic search for relevant tools

Features:
- Use lightweight embedding model (same as task memory search)
- Build vector index for all tools
- Support semantic tool selection based on task description
- Cache embeddings for fast startup
"""

from pathlib import Path
from typing import List, Dict, Optional, Any
import json

from clis.tools.base import Tool
from clis.utils.logger import get_logger
from clis.utils.platform import get_cache_dir

logger = get_logger(__name__)

# Try to import vector search dependencies (optional)
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    logger.debug("numpy not available, tool search will use fallback")

try:
    from sentence_transformers import SentenceTransformer
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logger.debug("sentence-transformers not available, tool search will use fallback")


class ToolVectorSearch:
    """
    Tool Vector Search - Semantic-based tool selection
    
    If dependencies are not installed, falls back to returning all tools
    """
    
    def __init__(self, tools: List[Tool], cache_dir: Optional[Path] = None):
        """
        Initialize tool vector search.
        
        Args:
            tools: List of all available tools
            cache_dir: Directory for caching embeddings (default: ~/.clis/cache)
        """
        self.tools = tools
        self.cache_dir = cache_dir or get_cache_dir()
        self.cache_file = self.cache_dir / "tool_embeddings.json"
        
        # Initialize embedding model (if available)
        self.model = None
        self.embeddings_available = NUMPY_AVAILABLE and TRANSFORMERS_AVAILABLE
        
        if self.embeddings_available:
            try:
                # Use same lightweight model as task search
                self.model = SentenceTransformer('all-MiniLM-L6-v2')
                logger.info("Loaded embedding model for tool search: all-MiniLM-L6-v2")
            except Exception as e:
                logger.warning(f"Failed to load embedding model: {e}")
                self.embeddings_available = False
        
        # Build or load tool index
        self.tool_index = self._load_or_build_index()
    
    def search_relevant_tools(
        self,
        query: str,
        top_k: int = 15,
        min_similarity: float = 0.25,
        always_include: Optional[List[str]] = None
    ) -> List[Tool]:
        """
        Search for relevant tools based on task query.
        Uses hybrid strategy: vector search + keyword boosting.
        
        Args:
            query: Task description
            top_k: Maximum number of tools to return
            min_similarity: Minimum similarity threshold
            always_include: Tool names to always include (e.g., ['read_file', 'write_file'])
            
        Returns:
            List of relevant tools
        """
        if not self.embeddings_available or not self.model:
            logger.warning("Embeddings not available, returning all tools")
            return self.tools
        
        try:
            # Generate query embedding
            query_embedding = self.model.encode([query])[0]
            query_lower = query.lower()
            
            # Calculate similarities with keyword boosting
            results = []
            for tool_name, data in self.tool_index.items():
                if 'embedding' not in data:
                    continue
                
                tool_embedding = np.array(data['embedding'])
                base_similarity = self._cosine_similarity(query_embedding, tool_embedding)
                
                # Apply keyword boosting
                boosted_similarity = self._apply_keyword_boost(
                    base_similarity,
                    tool_name,
                    query_lower
                )
                
                if boosted_similarity >= min_similarity:
                    results.append({
                        'tool_name': tool_name,
                        'similarity': float(boosted_similarity),
                        'base_similarity': float(base_similarity),
                        'tool': data['tool']
                    })
            
            # Sort by boosted similarity
            results.sort(key=lambda x: x['similarity'], reverse=True)
            
            # Get top_k tools
            selected_tools = [r['tool'] for r in results[:top_k]]
            
            # Add always_include tools if not already present
            if always_include:
                selected_names = {t.name for t in selected_tools}
                for tool_name in always_include:
                    if tool_name not in selected_names:
                        tool = self._get_tool_by_name(tool_name)
                        if tool:
                            selected_tools.append(tool)
            
            logger.info(f"Selected {len(selected_tools)} relevant tools from {len(self.tools)} total")
            
            return selected_tools
        
        except Exception as e:
            logger.error(f"Error in tool search: {e}")
            return self.tools  # Fallback to all tools
    
    def _apply_keyword_boost(self, base_similarity: float, tool_name: str, query_lower: str) -> float:
        """
        Apply keyword-based boosting to similarity score.
        
        Args:
            base_similarity: Base similarity from vector search
            tool_name: Name of the tool
            query_lower: Lowercase query string
            
        Returns:
            Boosted similarity score
        """
        boost = 0.0
        
        # Define keyword patterns and their boost values
        keyword_boosts = {
            # Docker keywords
            'docker': ['docker_ps', 'docker_logs', 'docker_inspect', 'docker_stats', 'docker_images', 'docker_rmi'],
            'dockerfile': ['docker_ps', 'docker_logs', 'docker_inspect', 'docker_images'],
            'container': ['docker_ps', 'docker_logs', 'docker_inspect', 'docker_stats'],
            
            # Git keywords
            'git': ['git_status', 'git_diff', 'git_add', 'git_commit', 'git_push', 'git_pull', 'git_log', 'git_branch', 'git_checkout'],
            'commit': ['git_commit', 'git_add', 'git_status', 'git_diff'],
            'push': ['git_push', 'git_status'],
            'branch': ['git_branch', 'git_checkout'],
            
            # Search keywords
            'search': ['grep', 'search_files', 'codebase_search', 'find_definition', 'find_references'],
            'find': ['grep', 'search_files', 'find_definition', 'find_references', 'get_symbols'],
            'grep': ['grep', 'search_files'],
            'pattern': ['grep', 'search_files'],
            
            # File operation keywords
            'edit': ['edit_file', 'search_replace', 'insert_code'],
            'modify': ['edit_file', 'search_replace'],
            'replace': ['search_replace', 'edit_file'],
            'create': ['write_file', 'edit_file'],
            'delete': ['delete_file', 'delete_lines'],
            
            # Service keywords
            'service': ['start_service', 'check_port', 'list_processes'],
            'server': ['start_service', 'check_port', 'http_request'],
            'port': ['check_port', 'start_service'],
            'flask': ['start_service', 'check_port', 'http_request'],
            'api': ['http_request', 'start_service'],
        }
        
        # Check for keyword matches
        for keyword, boosted_tools in keyword_boosts.items():
            if keyword in query_lower and tool_name in boosted_tools:
                # Boost by 0.15 for each keyword match
                boost += 0.15
        
        # Tool name prefix matching (e.g., "git" in query matches "git_*" tools)
        tool_prefix = tool_name.split('_')[0]
        if tool_prefix in query_lower and len(tool_prefix) > 3:
            boost += 0.20
        
        # Cap boost at 0.30 to avoid over-boosting
        boost = min(boost, 0.30)
        
        return base_similarity + boost
    
    def _load_or_build_index(self) -> Dict[str, Any]:
        """Load cached index or build new one."""
        # Try to load from cache
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                # Validate cache
                if self._is_cache_valid(cache_data):
                    logger.debug("Loaded tool embeddings from cache")
                    # Restore tool references
                    for tool_name, data in cache_data['tools'].items():
                        tool = self._get_tool_by_name(tool_name)
                        if tool:
                            data['tool'] = tool
                    return cache_data['tools']
            except Exception as e:
                logger.warning(f"Failed to load tool embeddings cache: {e}")
        
        # Build new index
        logger.info("Building tool embeddings index...")
        return self._build_index()
    
    def _build_index(self) -> Dict[str, Any]:
        """Build vector index for all tools."""
        if not self.embeddings_available or not self.model:
            return {}
        
        tool_index = {}
        
        # Define use cases and keywords for better matching
        tool_use_cases = self._get_tool_use_cases()
        
        for tool in self.tools:
            try:
                # Create enhanced search text: name + description + use cases
                search_text = f"{tool.name}: {tool.description}"
                
                # Add use cases if available
                if tool.name in tool_use_cases:
                    use_case = tool_use_cases[tool.name]
                    search_text += f". Use for: {use_case}"
                
                # Generate embedding
                embedding = self.model.encode([search_text])[0]
                
                tool_index[tool.name] = {
                    'tool': tool,
                    'embedding': embedding.tolist(),  # Convert to list for JSON
                    'search_text': search_text,
                    'description': tool.description
                }
            except Exception as e:
                logger.warning(f"Failed to generate embedding for tool '{tool.name}': {e}")
        
        # Save to cache
        self._save_cache(tool_index)
        
        logger.info(f"Built embeddings for {len(tool_index)} tools")
        return tool_index
    
    def _get_tool_use_cases(self) -> Dict[str, str]:
        """Define use cases for tools to improve search accuracy."""
        return {
            # Filesystem - Search tools
            'grep': 'finding text patterns, searching code, locating strings in files',
            'search_files': 'basic text search, finding files with content',
            'codebase_search': 'semantic code search, understanding code structure, finding functions or classes',
            'find_definition': 'locating function or class definitions, jumping to implementation',
            'find_references': 'finding where a function or variable is used',
            'get_symbols': 'listing functions, classes, variables in a file',
            
            # Filesystem - File operations
            'read_file': 'reading file contents, viewing code, examining files',
            'write_file': 'creating new files, writing content, generating code',
            'edit_file': 'modifying existing files, changing code, updating content',
            'search_replace': 'replacing text, renaming variables, bulk changes',
            'delete_file': 'removing files, cleaning up',
            'insert_code': 'adding code to files, inserting functions',
            'delete_lines': 'removing lines from files',
            
            # Git tools
            'git_status': 'checking repository status, seeing changes',
            'git_diff': 'viewing changes, comparing versions',
            'git_add': 'staging files, preparing commit',
            'git_commit': 'creating commits, saving changes',
            'git_push': 'pushing to remote, uploading changes',
            'git_pull': 'pulling from remote, updating local',
            'git_log': 'viewing commit history, checking past changes',
            'git_branch': 'managing branches, listing branches',
            'git_checkout': 'switching branches, checking out files',
            
            # Docker tools
            'docker_ps': 'listing containers, checking running containers',
            'docker_logs': 'viewing container logs, debugging containers',
            'docker_inspect': 'examining container details, checking configuration',
            'docker_stats': 'monitoring container resources, checking performance',
            'docker_images': 'listing images, checking available images',
            'docker_rmi': 'removing images, cleaning up',
            
            # System tools
            'execute_command': 'running shell commands, executing scripts, system operations',
            'start_service': 'starting web servers, launching services, running daemons',
            'check_command': 'verifying command availability, checking if tool is installed',
            'check_port': 'checking port availability, verifying network ports',
            'system_info': 'getting system information, checking OS details',
            'list_processes': 'viewing running processes, checking what is running',
            
            # Network tools
            'http_request': 'making HTTP requests, testing APIs, calling web services',
        }
    
    def _save_cache(self, tool_index: Dict[str, Any]) -> None:
        """Save tool embeddings to cache."""
        try:
            # Ensure cache directory exists
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            
            # Prepare cache data (exclude tool objects)
            cache_data = {
                'version': '1.0',
                'tool_count': len(tool_index),
                'tools': {}
            }
            
            for tool_name, data in tool_index.items():
                cache_data['tools'][tool_name] = {
                    'embedding': data['embedding'],
                    'search_text': data['search_text'],
                    'description': data['description']
                }
            
            # Save to file
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)
            
            logger.debug(f"Saved tool embeddings cache to {self.cache_file}")
        except Exception as e:
            logger.warning(f"Failed to save tool embeddings cache: {e}")
    
    def _is_cache_valid(self, cache_data: Dict) -> bool:
        """Check if cache is valid."""
        # Check version
        if cache_data.get('version') != '1.0':
            return False
        
        # Check tool count
        if cache_data.get('tool_count') != len(self.tools):
            logger.debug("Cache invalid: tool count mismatch")
            return False
        
        # Check if all tools exist
        cached_tools = set(cache_data.get('tools', {}).keys())
        current_tools = {t.name for t in self.tools}
        
        if cached_tools != current_tools:
            logger.debug("Cache invalid: tool names mismatch")
            return False
        
        return True
    
    def _get_tool_by_name(self, tool_name: str) -> Optional[Tool]:
        """Get tool by name."""
        for tool in self.tools:
            if tool.name == tool_name:
                return tool
        return None
    
    @staticmethod
    def _cosine_similarity(vec1, vec2) -> float:
        """Calculate cosine similarity between two vectors."""
        if not NUMPY_AVAILABLE:
            return 0.0
        
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def get_tool_stats(self) -> Dict[str, Any]:
        """Get statistics about tool index."""
        return {
            'total_tools': len(self.tools),
            'indexed_tools': len(self.tool_index),
            'embeddings_available': self.embeddings_available,
            'cache_exists': self.cache_file.exists()
        }
