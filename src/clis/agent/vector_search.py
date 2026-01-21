"""
Vector Search Module - Semantic search for historical task memories

Features:
- Use lightweight embedding model
- Build vector index for task memories
- Support "similar task" semantic search
- Optional feature (requires additional dependencies)
"""

from pathlib import Path
from typing import List, Dict, Optional, Tuple
import json
from datetime import datetime

from clis.utils.logger import get_logger

logger = get_logger(__name__)

# Try to import vector search dependencies (optional)
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    logger.debug("numpy not available, vector search will use fallback")

try:
    from sentence_transformers import SentenceTransformer
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logger.debug("sentence-transformers not available, vector search will use fallback")


class VectorSearch:
    """
    Vector Search - Semantic-based task memory search
    
    If dependencies are not installed, falls back to keyword-based search
    """
    
    def __init__(self, memory_dir: str = ".clis_memory"):
        self.memory_dir = Path(memory_dir)
        self.index_file = self.memory_dir / "vector_index.json"
        
        # Initialize embedding model (if available)
        self.model = None
        self.embeddings_available = NUMPY_AVAILABLE and TRANSFORMERS_AVAILABLE
        
        if self.embeddings_available:
            try:
                # Use lightweight model
                self.model = SentenceTransformer('all-MiniLM-L6-v2')
                logger.info("Loaded embedding model: all-MiniLM-L6-v2")
            except Exception as e:
                logger.warning(f"Failed to load embedding model: {e}")
                self.embeddings_available = False
        
        # Load vector index
        self.index = self._load_index()
    
    def search_similar_tasks(
        self,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.3
    ) -> List[Tuple[str, float, str]]:
        """
        Search for similar tasks
        
        Args:
            query: Query text
            top_k: Return top k results
            min_similarity: Minimum similarity threshold
            
        Returns:
            List of (task_id, similarity_score, description)
        """
        if self.embeddings_available and self.model:
            return self._search_with_embeddings(query, top_k, min_similarity)
        else:
            return self._search_with_keywords(query, top_k)
    
    def _search_with_embeddings(
        self,
        query: str,
        top_k: int,
        min_similarity: float
    ) -> List[Tuple[str, float, str]]:
        """Search using embedding model"""
        try:
            # Generate query vector
            query_embedding = self.model.encode([query])[0]
            
            # Calculate similarity
            results = []
            for task_id, data in self.index.items():
                if 'embedding' not in data:
                    continue
                
                task_embedding = np.array(data['embedding'])
                
                # Calculate cosine similarity
                similarity = self._cosine_similarity(query_embedding, task_embedding)
                
                if similarity >= min_similarity:
                    results.append((
                        task_id,
                        float(similarity),
                        data.get('description', '')
                    ))
            
            # Sort and return top_k
            results.sort(key=lambda x: x[1], reverse=True)
            return results[:top_k]
        
        except Exception as e:
            logger.error(f"Error in embedding search: {e}")
            return self._search_with_keywords(query, top_k)
    
    def _search_with_keywords(
        self,
        query: str,
        top_k: int
    ) -> List[Tuple[str, float, str]]:
        """Fallback: use keyword search"""
        query_words = set(query.lower().split())
        
        results = []
        for task_id, data in self.index.items():
            description = data.get('description', '').lower()
            desc_words = set(description.split())
            
            # Calculate word overlap rate
            overlap = len(query_words & desc_words)
            similarity = overlap / max(len(query_words), 1)
            
            if similarity > 0:
                results.append((
                    task_id,
                    similarity,
                    data.get('description', '')
                ))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
    
    @staticmethod
    def _cosine_similarity(vec1, vec2) -> float:
        """Calculate cosine similarity"""
        if not NUMPY_AVAILABLE:
            return 0.0
        
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def index_task(self, task_id: str, description: str, content: Optional[str] = None):
        """
        Index a task
        
        Args:
            task_id: Task ID
            description: Task description
            content: Task content (optional, for better embedding)
        """
        # Prepare index data
        index_data = {
            "description": description,
            "indexed_at": datetime.now().isoformat()
        }
        
        # Generate embedding (if available)
        if self.embeddings_available and self.model:
            try:
                # Use description to generate embedding
                text_to_embed = f"{description}. {content}" if content else description
                embedding = self.model.encode([text_to_embed])[0]
                index_data['embedding'] = embedding.tolist()
                logger.info(f"Generated embedding for task {task_id}")
            except Exception as e:
                logger.warning(f"Failed to generate embedding: {e}")
        
        # Add to index
        self.index[task_id] = index_data
        self._save_index()
    
    def remove_from_index(self, task_id: str):
        """Remove task from index"""
        if task_id in self.index:
            del self.index[task_id]
            self._save_index()
            logger.info(f"Removed task {task_id} from index")
    
    def get_index_stats(self) -> Dict:
        """Get index statistics"""
        total_tasks = len(self.index)
        tasks_with_embeddings = sum(1 for data in self.index.values() if 'embedding' in data)
        
        return {
            "total_tasks": total_tasks,
            "tasks_with_embeddings": tasks_with_embeddings,
            "embeddings_enabled": self.embeddings_available,
            "model": "all-MiniLM-L6-v2" if self.embeddings_available else "keyword-based"
        }
    
    def _load_index(self) -> Dict:
        """Load vector index"""
        if not self.index_file.exists():
            return {}
        
        try:
            with open(self.index_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"Loaded vector index with {len(data)} tasks")
            return data
        except Exception as e:
            logger.error(f"Error loading vector index: {e}")
            return {}
    
    def _save_index(self):
        """Save vector index"""
        try:
            # Ensure directory exists
            self.index_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(self.index, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"Saved vector index with {len(self.index)} tasks")
        except Exception as e:
            logger.error(f"Error saving vector index: {e}")
    
    def rebuild_index(self, memory_manager):
        """
        Rebuild vector index
        
        Args:
            memory_manager: MemoryManager instance
        """
        logger.info("Rebuilding vector index...")
        
        self.index = {}
        tasks = memory_manager.list_tasks(limit=1000)
        
        for task in tasks:
            self.index_task(
                task['id'],
                task.get('description', ''),
                None  # Don't include full content for now
            )
        
        logger.info(f"Rebuilt index with {len(self.index)} tasks")
