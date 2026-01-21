"""
子任务管理器 - 支持复杂任务拆分和管理

特点:
- 主任务可以拆分为多个子任务
- 每个子任务有独立的记忆和状态
- 支持任务依赖关系
- 自动聚合子任务结果
"""

from pathlib import Path
from typing import List, Optional, Dict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json

from clis.agent.episodic_memory import EpisodicMemory
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class SubtaskStatus(Enum):
    """子任务状态"""
    PENDING = "pending"       # 待执行
    IN_PROGRESS = "in_progress"  # 执行中
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"         # 失败
    BLOCKED = "blocked"       # 被阻塞（依赖未完成）


@dataclass
class Subtask:
    """子任务"""
    id: str
    description: str
    status: SubtaskStatus = SubtaskStatus.PENDING
    parent_id: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)  # 依赖的子任务 ID
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status.value,
            "parent_id": self.parent_id,
            "dependencies": self.dependencies,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "completed_at": self.completed_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Subtask':
        """从字典创建"""
        return cls(
            id=data["id"],
            description=data["description"],
            status=SubtaskStatus(data["status"]),
            parent_id=data.get("parent_id"),
            dependencies=data.get("dependencies", []),
            result=data.get("result"),
            error=data.get("error"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            completed_at=data.get("completed_at")
        )


class SubtaskManager:
    """
    子任务管理器
    
    职责:
    - 创建和管理子任务
    - 跟踪子任务状态
    - 检查依赖关系
    - 聚合子任务结果
    """
    
    def __init__(self, main_task_id: str, memory_dir: str = ".clis_memory"):
        self.main_task_id = main_task_id
        self.memory_dir = Path(memory_dir)
        self.subtasks_dir = self.memory_dir / "tasks" / "active" / f"subtasks_{main_task_id}"
        self.subtasks_file = self.subtasks_dir / "subtasks.json"
        
        # 子任务列表
        self.subtasks: Dict[str, Subtask] = {}
        
        # 确保目录存在
        self.subtasks_dir.mkdir(parents=True, exist_ok=True)
        
        # 加载已有子任务
        self._load_subtasks()
    
    def create_subtask(
        self,
        description: str,
        dependencies: Optional[List[str]] = None
    ) -> Subtask:
        """
        创建新的子任务
        
        Args:
            description: 子任务描述
            dependencies: 依赖的子任务 ID 列表
            
        Returns:
            创建的子任务对象
        """
        # 生成子任务 ID
        subtask_id = f"{self.main_task_id}_sub{len(self.subtasks) + 1}"
        
        # 创建子任务
        subtask = Subtask(
            id=subtask_id,
            description=description,
            parent_id=self.main_task_id,
            dependencies=dependencies or [],
            status=SubtaskStatus.PENDING
        )
        
        # 添加到列表
        self.subtasks[subtask_id] = subtask
        
        # 创建子任务记忆文件
        subtask_memory = EpisodicMemory(subtask_id)
        subtask_memory.load_or_create(description)
        
        # 保存
        self._save_subtasks()
        
        logger.info(f"Created subtask: {subtask_id} - {description}")
        
        return subtask
    
    def get_next_subtask(self) -> Optional[Subtask]:
        """
        获取下一个可执行的子任务
        
        Returns:
            下一个待执行的子任务，如果没有则返回 None
        """
        for subtask in self.subtasks.values():
            if subtask.status != SubtaskStatus.PENDING:
                continue
            
            # 检查依赖是否已完成
            if self._are_dependencies_met(subtask):
                return subtask
            else:
                # 标记为阻塞
                subtask.status = SubtaskStatus.BLOCKED
        
        return None
    
    def _are_dependencies_met(self, subtask: Subtask) -> bool:
        """检查子任务的依赖是否已满足"""
        for dep_id in subtask.dependencies:
            if dep_id not in self.subtasks:
                logger.warning(f"Dependency not found: {dep_id}")
                return False
            
            dep_subtask = self.subtasks[dep_id]
            if dep_subtask.status != SubtaskStatus.COMPLETED:
                return False
        
        return True
    
    def start_subtask(self, subtask_id: str) -> bool:
        """
        开始执行子任务
        
        Args:
            subtask_id: 子任务 ID
            
        Returns:
            是否成功开始
        """
        if subtask_id not in self.subtasks:
            logger.error(f"Subtask not found: {subtask_id}")
            return False
        
        subtask = self.subtasks[subtask_id]
        
        # 检查依赖
        if not self._are_dependencies_met(subtask):
            logger.warning(f"Dependencies not met for subtask: {subtask_id}")
            subtask.status = SubtaskStatus.BLOCKED
            return False
        
        # 更新状态
        subtask.status = SubtaskStatus.IN_PROGRESS
        self._save_subtasks()
        
        logger.info(f"Started subtask: {subtask_id}")
        return True
    
    def complete_subtask(
        self,
        subtask_id: str,
        result: Optional[str] = None,
        success: bool = True
    ) -> bool:
        """
        完成子任务
        
        Args:
            subtask_id: 子任务 ID
            result: 执行结果
            success: 是否成功完成
            
        Returns:
            是否成功完成
        """
        if subtask_id not in self.subtasks:
            logger.error(f"Subtask not found: {subtask_id}")
            return False
        
        subtask = self.subtasks[subtask_id]
        
        # 更新状态
        if success:
            subtask.status = SubtaskStatus.COMPLETED
            subtask.result = result
        else:
            subtask.status = SubtaskStatus.FAILED
            subtask.error = result
        
        subtask.completed_at = datetime.now().isoformat()
        
        # 保存
        self._save_subtasks()
        
        # 完成子任务记忆
        from clis.agent.memory_manager import MemoryManager
        memory_manager = MemoryManager()
        try:
            memory_manager.complete_task(subtask_id, success=success)
        except:
            # 子任务可能没有在 memory_manager 中注册，这是正常的
            pass
        
        logger.info(f"Completed subtask: {subtask_id} - success={success}")
        
        # 解除被阻塞的任务
        self._unblock_dependent_tasks(subtask_id)
        
        return True
    
    def _unblock_dependent_tasks(self, completed_subtask_id: str):
        """解除依赖已完成子任务的被阻塞任务"""
        for subtask in self.subtasks.values():
            if subtask.status == SubtaskStatus.BLOCKED:
                if self._are_dependencies_met(subtask):
                    subtask.status = SubtaskStatus.PENDING
                    logger.info(f"Unblocked subtask: {subtask.id}")
        
        self._save_subtasks()
    
    def get_all_subtasks(self) -> List[Subtask]:
        """获取所有子任务"""
        return list(self.subtasks.values())
    
    def get_subtask_by_id(self, subtask_id: str) -> Optional[Subtask]:
        """根据 ID 获取子任务"""
        return self.subtasks.get(subtask_id)
    
    def get_progress_summary(self) -> Dict:
        """获取进度摘要"""
        total = len(self.subtasks)
        completed = sum(1 for s in self.subtasks.values() if s.status == SubtaskStatus.COMPLETED)
        failed = sum(1 for s in self.subtasks.values() if s.status == SubtaskStatus.FAILED)
        in_progress = sum(1 for s in self.subtasks.values() if s.status == SubtaskStatus.IN_PROGRESS)
        pending = sum(1 for s in self.subtasks.values() if s.status == SubtaskStatus.PENDING)
        blocked = sum(1 for s in self.subtasks.values() if s.status == SubtaskStatus.BLOCKED)
        
        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "in_progress": in_progress,
            "pending": pending,
            "blocked": blocked,
            "completion_rate": (completed / total * 100) if total > 0 else 0
        }
    
    def to_markdown(self) -> str:
        """转换为 Markdown 格式用于显示"""
        if not self.subtasks:
            return "无子任务"
        
        progress = self.get_progress_summary()
        
        output = f"""## 🔀 子任务 (共 {progress['total']} 个)

**进度**: {progress['completed']}/{progress['total']} ({progress['completion_rate']:.1f}%)

| # | 描述 | 状态 | 依赖 |
|---|------|------|------|
"""
        
        for i, subtask in enumerate(self.subtasks.values(), 1):
            status_emoji = {
                SubtaskStatus.PENDING: "⏳",
                SubtaskStatus.IN_PROGRESS: "🔄",
                SubtaskStatus.COMPLETED: "✅",
                SubtaskStatus.FAILED: "❌",
                SubtaskStatus.BLOCKED: "🚫"
            }[subtask.status]
            
            deps = ", ".join(subtask.dependencies) if subtask.dependencies else "-"
            output += f"| {i} | {subtask.description[:50]} | {status_emoji} {subtask.status.value} | {deps} |\n"
        
        return output
    
    def _save_subtasks(self):
        """保存子任务到文件"""
        data = {
            "main_task_id": self.main_task_id,
            "created_at": datetime.now().isoformat(),
            "subtasks": {
                sid: subtask.to_dict()
                for sid, subtask in self.subtasks.items()
            }
        }
        
        with open(self.subtasks_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _load_subtasks(self):
        """从文件加载子任务"""
        if not self.subtasks_file.exists():
            return
        
        try:
            with open(self.subtasks_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for sid, subtask_data in data.get("subtasks", {}).items():
                self.subtasks[sid] = Subtask.from_dict(subtask_data)
            
            logger.info(f"Loaded {len(self.subtasks)} subtasks for task {self.main_task_id}")
        
        except Exception as e:
            logger.error(f"Error loading subtasks: {e}")
    
    def get_file_path(self) -> Path:
        """获取子任务文件路径"""
        return self.subtasks_file
