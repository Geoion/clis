"""
Skill Vector Search - Semantic search for relevant skills

Similar to tool vector search, but for skills.
"""

from pathlib import Path
from typing import List, Dict, Optional, Any
import json

from clis.utils.logger import get_logger
from clis.utils.platform import get_cache_dir

logger = get_logger(__name__)

# Try to import vector search dependencies (optional)
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False


class SkillVectorSearch:
    """
    Skill Vector Search - Semantic-based skill selection
    
    If dependencies are not installed, falls back to keyword matching
    """
    
    def __init__(self, skills: List, cache_dir: Optional[Path] = None):
        """
        Initialize skill vector search.
        
        Args:
            skills: List of all available skills
            cache_dir: Directory for caching embeddings
        """
        self.skills = skills
        self.cache_dir = cache_dir or get_cache_dir()
        self.cache_file = self.cache_dir / "skill_embeddings.json"
        
        # Initialize embedding model (if available)
        self.model = None
        self.embeddings_available = NUMPY_AVAILABLE and TRANSFORMERS_AVAILABLE
        
        if self.embeddings_available:
            try:
                self.model = SentenceTransformer('all-MiniLM-L6-v2')
                logger.info("Loaded embedding model for skill search")
            except Exception as e:
                logger.warning(f"Failed to load embedding model: {e}")
                self.embeddings_available = False
        
        # Build or load skill index
        self.skill_index = self._load_or_build_index()
    
    def search_relevant_skills(
        self,
        query: str,
        top_k: int = 3,
        min_similarity: float = 0.30
    ) -> List:
        """
        Search for relevant skills based on task query.
        
        Args:
            query: Task description
            top_k: Maximum number of skills to return
            min_similarity: Minimum similarity threshold
            
        Returns:
            List of relevant skills
        """
        if not self.embeddings_available or not self.model:
            # Fallback to keyword matching
            return self._keyword_fallback(query, top_k)
        
        try:
            # Generate query embedding
            query_embedding = self.model.encode([query])[0]
            query_lower = query.lower()
            
            # Calculate similarities with keyword boosting
            results = []
            for skill_name, data in self.skill_index.items():
                if 'embedding' not in data:
                    continue
                
                skill_embedding = np.array(data['embedding'])
                base_similarity = self._cosine_similarity(query_embedding, skill_embedding)
                
                # Apply keyword boosting
                boosted_similarity = self._apply_keyword_boost(
                    base_similarity,
                    skill_name,
                    query_lower
                )
                
                if boosted_similarity >= min_similarity:
                    results.append({
                        'skill_name': skill_name,
                        'similarity': float(boosted_similarity),
                        'skill': data['skill']
                    })
            
            # Sort by similarity
            results.sort(key=lambda x: x['similarity'], reverse=True)
            
            # Return top_k skills
            selected_skills = [r['skill'] for r in results[:top_k]]
            
            logger.info(f"Selected {len(selected_skills)} relevant skills from {len(self.skills)} total")
            
            return selected_skills
        
        except Exception as e:
            logger.error(f"Error in skill search: {e}")
            return self._keyword_fallback(query, top_k)
    
    def _keyword_fallback(self, query: str, top_k: int) -> List:
        """Fallback to keyword matching when embeddings unavailable."""
        query_lower = query.lower()
        
        skill_keywords = {
            'FAST_MODE': ['flask', 'service', 'server', 'port', 'web', 'api'],
            'EDIT_FILE': ['edit', 'modify', 'change', 'file', 'code'],
            'VERIFIER': ['test', 'verify', 'check', 'validate']
        }
        
        matched = []
        for skill in self.skills:
            skill_name = skill.name.upper().replace(' ', '_').replace('-', '_')
            for pattern, keywords in skill_keywords.items():
                if pattern in skill_name:
                    if any(keyword in query_lower for keyword in keywords):
                        matched.append(skill)
                        break
        
        return matched[:top_k]
    
    def _apply_keyword_boost(self, base_similarity: float, skill_name: str, query_lower: str) -> float:
        """Apply keyword-based boosting to similarity score."""
        boost = 0.0
        
        keyword_boosts = {
            'flask': ['FAST_MODE'],
            'service': ['FAST_MODE'],
            'port': ['FAST_MODE'],
            'edit': ['EDIT_FILE'],
            'file': ['EDIT_FILE'],
            'test': ['VERIFIER'],
            'verify': ['VERIFIER'],
        }
        
        skill_name_upper = skill_name.upper()
        for keyword, boosted_skills in keyword_boosts.items():
            if keyword in query_lower:
                for pattern in boosted_skills:
                    if pattern in skill_name_upper:
                        boost += 0.15
                        break
        
        return min(base_similarity + boost, 1.0)
    
    def _load_or_build_index(self) -> Dict[str, Any]:
        """Load cached index or build new one."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                if self._is_cache_valid(cache_data):
                    logger.debug("Loaded skill embeddings from cache")
                    for skill_name, data in cache_data['skills'].items():
                        skill = self._get_skill_by_name(skill_name)
                        if skill:
                            data['skill'] = skill
                    return cache_data['skills']
            except Exception as e:
                logger.warning(f"Failed to load skill embeddings cache: {e}")
        
        return self._build_index()
    
    def _build_index(self) -> Dict[str, Any]:
        """Build vector index for all skills."""
        if not self.embeddings_available or not self.model:
            return {}
        
        skill_index = {}
        
        for skill in self.skills:
            try:
                # Create search text: name + description
                search_text = f"{skill.name}: {skill.description}"
                
                # Generate embedding
                embedding = self.model.encode([search_text])[0]
                
                skill_index[skill.name] = {
                    'skill': skill,
                    'embedding': embedding.tolist(),
                    'search_text': search_text,
                    'description': skill.description
                }
            except Exception as e:
                logger.warning(f"Failed to generate embedding for skill '{skill.name}': {e}")
        
        self._save_cache(skill_index)
        logger.info(f"Built embeddings for {len(skill_index)} skills")
        return skill_index
    
    def _save_cache(self, skill_index: Dict[str, Any]) -> None:
        """Save skill embeddings to cache."""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            
            cache_data = {
                'version': '1.0',
                'skill_count': len(skill_index),
                'skills': {}
            }
            
            for skill_name, data in skill_index.items():
                cache_data['skills'][skill_name] = {
                    'embedding': data['embedding'],
                    'search_text': data['search_text'],
                    'description': data['description']
                }
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)
            
            logger.debug(f"Saved skill embeddings cache")
        except Exception as e:
            logger.warning(f"Failed to save skill embeddings cache: {e}")
    
    def _is_cache_valid(self, cache_data: Dict) -> bool:
        """Check if cache is valid."""
        if cache_data.get('version') != '1.0':
            return False
        if cache_data.get('skill_count') != len(self.skills):
            return False
        return True
    
    def _get_skill_by_name(self, skill_name: str):
        """Get skill by name."""
        for skill in self.skills:
            if skill.name == skill_name:
                return skill
        return None
    
    @staticmethod
    def _cosine_similarity(vec1, vec2) -> float:
        """Calculate cosine similarity."""
        if not NUMPY_AVAILABLE:
            return 0.0
        
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
