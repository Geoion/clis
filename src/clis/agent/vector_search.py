"""
向量检索模块 - 语义搜索历史任务记忆

特点:
- 使用轻量级 embedding 模型
- 为任务记忆建立向量索引
- 支持"类似任务"语义搜索
- 可选功能（需要额外依赖）
"""

from pathlib import Path
from typing import List, Dict, Optional, Tuple
import json
from datetime import datetime

from clis.utils.logger import get_logger

logger = get_logger(__name__)

# 尝试导入向量搜索依赖（可选）
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
    向量检索 - 基于语义的任务记忆搜索
    
    如果没有安装依赖，会降级到基于关键词的搜索
    """
    
    def __init__(self, memory_dir: str = ".clis_memory"):
        self.memory_dir = Path(memory_dir)
        self.index_file = self.memory_dir / "vector_index.json"
        
        # 初始化 embedding 模型（如果可用）
        self.model = None
        self.embeddings_available = NUMPY_AVAILABLE and TRANSFORMERS_AVAILABLE
        
        if self.embeddings_available:
            try:
                # 使用轻量级模型
                self.model = SentenceTransformer('all-MiniLM-L6-v2')
                logger.info("Loaded embedding model: all-MiniLM-L6-v2")
            except Exception as e:
                logger.warning(f"Failed to load embedding model: {e}")
                self.embeddings_available = False
        
        # 加载向量索引
        self.index = self._load_index()
    
    def search_similar_tasks(
        self,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.3
    ) -> List[Tuple[str, float, str]]:
        """
        搜索相似的任务
        
        Args:
            query: 查询文本
            top_k: 返回前 k 个结果
            min_similarity: 最小相似度阈值
            
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
        """使用 embedding 模型搜索"""
        try:
            # 生成查询向量
            query_embedding = self.model.encode([query])[0]
            
            # 计算相似度
            results = []
            for task_id, data in self.index.items():
                if 'embedding' not in data:
                    continue
                
                task_embedding = np.array(data['embedding'])
                
                # 计算余弦相似度
                similarity = self._cosine_similarity(query_embedding, task_embedding)
                
                if similarity >= min_similarity:
                    results.append((
                        task_id,
                        float(similarity),
                        data.get('description', '')
                    ))
            
            # 排序并返回 top_k
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
        """降级方案：使用关键词搜索"""
        query_words = set(query.lower().split())
        
        results = []
        for task_id, data in self.index.items():
            description = data.get('description', '').lower()
            desc_words = set(description.split())
            
            # 计算词重叠率
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
        """计算余弦相似度"""
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
        为任务建立索引
        
        Args:
            task_id: 任务 ID
            description: 任务描述
            content: 任务内容（可选，用于更好的embedding）
        """
        # 准备索引数据
        index_data = {
            "description": description,
            "indexed_at": datetime.now().isoformat()
        }
        
        # 生成 embedding（如果可用）
        if self.embeddings_available and self.model:
            try:
                # 使用描述生成 embedding
                text_to_embed = f"{description}. {content}" if content else description
                embedding = self.model.encode([text_to_embed])[0]
                index_data['embedding'] = embedding.tolist()
                logger.info(f"Generated embedding for task {task_id}")
            except Exception as e:
                logger.warning(f"Failed to generate embedding: {e}")
        
        # 添加到索引
        self.index[task_id] = index_data
        self._save_index()
    
    def remove_from_index(self, task_id: str):
        """从索引中移除任务"""
        if task_id in self.index:
            del self.index[task_id]
            self._save_index()
            logger.info(f"Removed task {task_id} from index")
    
    def get_index_stats(self) -> Dict:
        """获取索引统计信息"""
        total_tasks = len(self.index)
        tasks_with_embeddings = sum(1 for data in self.index.values() if 'embedding' in data)
        
        return {
            "total_tasks": total_tasks,
            "tasks_with_embeddings": tasks_with_embeddings,
            "embeddings_enabled": self.embeddings_available,
            "model": "all-MiniLM-L6-v2" if self.embeddings_available else "keyword-based"
        }
    
    def _load_index(self) -> Dict:
        """加载向量索引"""
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
        """保存向量索引"""
        try:
            # 确保目录存在
            self.index_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(self.index, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"Saved vector index with {len(self.index)} tasks")
        except Exception as e:
            logger.error(f"Error saving vector index: {e}")
    
    def rebuild_index(self, memory_manager):
        """
        重建向量索引
        
        Args:
            memory_manager: MemoryManager 实例
        """
        logger.info("Rebuilding vector index...")
        
        self.index = {}
        tasks = memory_manager.list_tasks(limit=1000)
        
        for task in tasks:
            self.index_task(
                task['id'],
                task.get('description', ''),
                None  # 暂不包含完整内容
            )
        
        logger.info(f"Rebuilt index with {len(self.index)} tasks")
