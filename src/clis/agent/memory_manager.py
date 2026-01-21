"""
Memory lifecycle manager

Responsibilities:
- Create and organize memory files
- Auto cleanup expired memories
- Archive long-term memories
- Provide query interface
"""

from pathlib import Path
from datetime import datetime, timedelta
import json
import shutil
from typing import Optional, List, Dict
from enum import Enum


class TaskStatus(Enum):
    """Task status"""
    ACTIVE = "active"           # In progress
    COMPLETED = "completed"     # Completed
    ARCHIVED = "archived"       # Archived
    FAILED = "failed"           # Failed


class MemoryManager:
    """
    Memory lifecycle manager
    
    Manages complete lifecycle of task memories:
    create → active/ → completed/ → archived/
    """
    
    def __init__(self, memory_dir: str = ".clis_memory"):
        self.memory_dir = Path(memory_dir)
        self.tasks_dir = self.memory_dir / "tasks"
        self.active_dir = self.tasks_dir / "active"
        self.completed_dir = self.tasks_dir / "completed"
        self.archived_dir = self.tasks_dir / "archived"
        self.knowledge_dir = self.memory_dir / "knowledge"
        self.metadata_file = self.memory_dir / ".metadata.json"
        
        # Create directory structure
        self._ensure_dirs()
        
        # Load metadata
        self.metadata = self._load_metadata()
    
    def _ensure_dirs(self):
        """Ensure directory structure exists"""
        for dir_path in [self.active_dir, self.completed_dir, 
                         self.archived_dir, self.knowledge_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def _load_metadata(self) -> Dict:
        """Load memory metadata"""
        if self.metadata_file.exists():
            try:
                return json.loads(self.metadata_file.read_text(encoding='utf-8'))
            except (json.JSONDecodeError, Exception):
                # Metadata corrupted, return default
                return {"tasks": {}, "config": self._default_config()}
        return {"tasks": {}, "config": self._default_config()}
    
    def _save_metadata(self):
        """Save metadata"""
        self.metadata_file.write_text(
            json.dumps(self.metadata, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )
    
    def _default_config(self) -> Dict:
        """Default configuration"""
        return {
            "retention_days": 7,      # Days to keep completed tasks
            "auto_archive": True,     # Auto archive
            "auto_cleanup": True,     # Auto cleanup
            "max_active_tasks": 10,   # Max concurrent tasks
        }
    
    def create_task_memory(
        self, 
        task_description: str,
        task_id: Optional[str] = None
    ) -> tuple[str, Path]:
        """
        Create new task memory
        
        Args:
            task_description: Task description
            task_id: Task ID (optional, auto-generated if not provided)
            
        Returns:
            (task_id, file_path)
        """
        if task_id is None:
            task_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        task_file = self.active_dir / f"task_{task_id}.md"
        
        # Record metadata
        self.metadata["tasks"][task_id] = {
            "status": TaskStatus.ACTIVE.value,
            "description": task_description[:100],  # Save only first 100 chars
            "created_at": datetime.now().isoformat(),
            "file_path": str(task_file.relative_to(self.memory_dir)),
        }
        self._save_metadata()
        
        return task_id, task_file
    
    def complete_task(
        self, 
        task_id: str,
        success: bool = True,
        extract_knowledge: bool = True
    ):
        """
        Mark task as complete
        
        Args:
            task_id: Task ID
            success: Whether completed successfully
            extract_knowledge: Whether to extract knowledge to knowledge base
        """
        if task_id not in self.metadata["tasks"]:
            # Task doesn't exist, may be directly created file, add metadata
            self.metadata["tasks"][task_id] = {
                "status": TaskStatus.ACTIVE.value,
                "description": "Unknown task",
                "created_at": datetime.now().isoformat(),
            }
        
        # Move file: active → completed
        active_file = self.active_dir / f"task_{task_id}.md"
        completed_file = self.completed_dir / f"task_{task_id}.md"
        
        if active_file.exists():
            shutil.move(str(active_file), str(completed_file))
            
            # Add completion marker at file header
            content = completed_file.read_text(encoding='utf-8')
            header = f"""<!-- COMPLETED: {datetime.now().isoformat()} -->
<!-- SUCCESS: {success} -->

"""
            completed_file.write_text(header + content, encoding='utf-8')
        
        # Update metadata
        self.metadata["tasks"][task_id].update({
            "status": TaskStatus.COMPLETED.value if success else TaskStatus.FAILED.value,
            "completed_at": datetime.now().isoformat(),
            "file_path": str(completed_file.relative_to(self.memory_dir)),
        })
        self._save_metadata()
        
        # Extract knowledge
        if extract_knowledge and success:
            self._extract_knowledge(task_id, completed_file)
    
    def _extract_knowledge(self, task_id: str, task_file: Path):
        """
        Extract knowledge from task to knowledge base
        
        Strategy:
        - Extract "Key Findings" section
        - Identify general patterns
        - Update project knowledge base
        """
        # TODO: Implement intelligent knowledge extraction
        # Can call LLM to summarize reusable knowledge from task
        pass
    
    def archive_old_tasks(self, days: Optional[int] = None):
        """
        归档旧任务
        
        Args:
            days: 保留天数 (None = 使用配置)
        """
        if days is None:
            days = self.metadata["config"]["retention_days"]
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        for task_id, task_info in list(self.metadata["tasks"].items()):
            if task_info["status"] != TaskStatus.COMPLETED.value:
                continue
            
            completed_at_str = task_info.get("completed_at")
            if not completed_at_str:
                continue
            
            try:
                completed_at = datetime.fromisoformat(completed_at_str)
                if completed_at < cutoff_date:
                    self._archive_task(task_id)
            except (ValueError, Exception):
                continue
    
    def _archive_task(self, task_id: str):
        """归档单个任务"""
        if task_id not in self.metadata["tasks"]:
            return
        
        task_info = self.metadata["tasks"][task_id]
        completed_file = self.completed_dir / f"task_{task_id}.md"
        
        if not completed_file.exists():
            return
        
        # 按月归档
        completed_at_str = task_info.get("completed_at")
        if not completed_at_str:
            completed_at = datetime.now()
        else:
            try:
                completed_at = datetime.fromisoformat(completed_at_str)
            except ValueError:
                completed_at = datetime.now()
        
        archive_month_dir = self.archived_dir / completed_at.strftime('%Y-%m')
        archive_month_dir.mkdir(exist_ok=True)
        
        archive_file = archive_month_dir / f"task_{task_id}.md"
        shutil.move(str(completed_file), str(archive_file))
        
        # 更新元数据
        task_info.update({
            "status": TaskStatus.ARCHIVED.value,
            "archived_at": datetime.now().isoformat(),
            "file_path": str(archive_file.relative_to(self.memory_dir)),
        })
        self._save_metadata()
    
    def cleanup(self):
        """执行清理任务"""
        if self.metadata["config"]["auto_archive"]:
            self.archive_old_tasks()
        
        if self.metadata["config"]["auto_cleanup"]:
            self._cleanup_failed_tasks()
    
    def _cleanup_failed_tasks(self):
        """清理失败的任务 (保留 1 天)"""
        cutoff = datetime.now() - timedelta(days=1)
        
        for task_id, task_info in list(self.metadata["tasks"].items()):
            if task_info["status"] == TaskStatus.FAILED.value:
                completed_at_str = task_info.get("completed_at")
                if not completed_at_str:
                    continue
                
                try:
                    completed_at = datetime.fromisoformat(completed_at_str)
                    if completed_at < cutoff:
                        # 删除文件
                        task_file = self.memory_dir / task_info["file_path"]
                        if task_file.exists():
                            task_file.unlink()
                        
                        # 删除元数据
                        del self.metadata["tasks"][task_id]
                except (ValueError, Exception):
                    continue
        
        self._save_metadata()
    
    def list_tasks(
        self, 
        status: Optional[TaskStatus] = None,
        limit: int = 20
    ) -> List[Dict]:
        """
        列出任务
        
        Args:
            status: 过滤状态 (None = 全部)
            limit: 最大返回数量
            
        Returns:
            任务列表 (按创建时间倒序)
        """
        tasks = []
        for task_id, task_info in self.metadata["tasks"].items():
            if status is None or task_info["status"] == status.value:
                tasks.append({
                    "id": task_id,
                    **task_info
                })
        
        # 按创建时间倒序
        tasks.sort(key=lambda t: t.get("created_at", ""), reverse=True)
        return tasks[:limit]
    
    def get_task_file(self, task_id: str) -> Optional[Path]:
        """获取任务文件路径"""
        if task_id not in self.metadata["tasks"]:
            return None
        
        rel_path = self.metadata["tasks"][task_id]["file_path"]
        return self.memory_dir / rel_path
    
    def search_tasks(self, query: str) -> List[Dict]:
        """
        搜索任务 (简单文本匹配)
        
        Args:
            query: 搜索关键词
            
        Returns:
            匹配的任务列表
        """
        results = []
        for task_id, task_info in self.metadata["tasks"].items():
            description = task_info.get("description", "")
            if query.lower() in description.lower():
                results.append({
                    "id": task_id,
                    **task_info
                })
        return results
    
    def get_stats(self) -> Dict:
        """
        获取记忆统计信息
        
        Returns:
            统计信息字典
        """
        stats = {
            "total": len(self.metadata["tasks"]),
            "active": 0,
            "completed": 0,
            "archived": 0,
            "failed": 0,
        }
        
        for task_info in self.metadata["tasks"].values():
            status = task_info.get("status", "")
            if status == TaskStatus.ACTIVE.value:
                stats["active"] += 1
            elif status == TaskStatus.COMPLETED.value:
                stats["completed"] += 1
            elif status == TaskStatus.ARCHIVED.value:
                stats["archived"] += 1
            elif status == TaskStatus.FAILED.value:
                stats["failed"] += 1
        
        return stats
    
    def delete_task(self, task_id: str):
        """
        删除任务
        
        Args:
            task_id: 任务ID
        """
        if task_id not in self.metadata["tasks"]:
            return
        
        # 删除文件
        task_info = self.metadata["tasks"][task_id]
        task_file = self.memory_dir / task_info["file_path"]
        if task_file.exists():
            task_file.unlink()
        
        # 删除元数据
        del self.metadata["tasks"][task_id]
        self._save_metadata()
