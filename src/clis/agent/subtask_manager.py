"""
Subtask Manager - Support complex task breakdown and management

Features:
- Main task can be split into multiple subtasks
- Each subtask has independent memory and state
- Support task dependencies
- Automatically aggregate subtask results
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
    """Subtask status"""
    PENDING = "pending"       # Pending execution
    IN_PROGRESS = "in_progress"  # In progress
    COMPLETED = "completed"   # Completed
    FAILED = "failed"         # Failed
    BLOCKED = "blocked"       # Blocked (dependencies not completed)


@dataclass
class Subtask:
    """Subtask"""
    id: str
    description: str
    status: SubtaskStatus = SubtaskStatus.PENDING
    parent_id: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)  # Dependent subtask IDs
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
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
        """Create from dictionary"""
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
    Subtask Manager
    
    Responsibilities:
    - Create and manage subtasks
    - Track subtask status
    - Check dependencies
    - Aggregate subtask results
    """
    
    def __init__(self, main_task_id: str, memory_dir: str = ".clis_memory"):
        self.main_task_id = main_task_id
        self.memory_dir = Path(memory_dir)
        self.subtasks_dir = self.memory_dir / "tasks" / "active" / f"subtasks_{main_task_id}"
        self.subtasks_file = self.subtasks_dir / "subtasks.json"
        
        # Subtask list
        self.subtasks: Dict[str, Subtask] = {}
        
        # Ensure directory exists
        self.subtasks_dir.mkdir(parents=True, exist_ok=True)
        
        # Load existing subtasks
        self._load_subtasks()
    
    def create_subtask(
        self,
        description: str,
        dependencies: Optional[List[str]] = None
    ) -> Subtask:
        """
        Create new subtask
        
        Args:
            description: Subtask description
            dependencies: List of dependent subtask IDs
            
        Returns:
            Created subtask object
        """
        # Generate subtask ID
        subtask_id = f"{self.main_task_id}_sub{len(self.subtasks) + 1}"
        
        # Create subtask
        subtask = Subtask(
            id=subtask_id,
            description=description,
            parent_id=self.main_task_id,
            dependencies=dependencies or [],
            status=SubtaskStatus.PENDING
        )
        
        # Add to list
        self.subtasks[subtask_id] = subtask
        
        # Create subtask memory file
        subtask_memory = EpisodicMemory(subtask_id)
        subtask_memory.load_or_create(description)
        
        # Save
        self._save_subtasks()
        
        logger.info(f"Created subtask: {subtask_id} - {description}")
        
        return subtask
    
    def get_next_subtask(self) -> Optional[Subtask]:
        """
        Get next executable subtask
        
        Returns:
            Next pending subtask to execute, or None if none available
        """
        for subtask in self.subtasks.values():
            if subtask.status != SubtaskStatus.PENDING:
                continue
            
            # Check if dependencies are completed
            if self._are_dependencies_met(subtask):
                return subtask
            else:
                # Mark as blocked
                subtask.status = SubtaskStatus.BLOCKED
        
        return None
    
    def _are_dependencies_met(self, subtask: Subtask) -> bool:
        """Check if subtask dependencies are satisfied"""
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
        Start executing subtask
        
        Args:
            subtask_id: Subtask ID
            
        Returns:
            Whether successfully started
        """
        if subtask_id not in self.subtasks:
            logger.error(f"Subtask not found: {subtask_id}")
            return False
        
        subtask = self.subtasks[subtask_id]
        
        # Check dependencies
        if not self._are_dependencies_met(subtask):
            logger.warning(f"Dependencies not met for subtask: {subtask_id}")
            subtask.status = SubtaskStatus.BLOCKED
            return False
        
        # Update status
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
        Complete subtask
        
        Args:
            subtask_id: Subtask ID
            result: Execution result
            success: Whether successfully completed
            
        Returns:
            Whether successfully completed
        """
        if subtask_id not in self.subtasks:
            logger.error(f"Subtask not found: {subtask_id}")
            return False
        
        subtask = self.subtasks[subtask_id]
        
        # Update status
        if success:
            subtask.status = SubtaskStatus.COMPLETED
            subtask.result = result
        else:
            subtask.status = SubtaskStatus.FAILED
            subtask.error = result
        
        subtask.completed_at = datetime.now().isoformat()
        
        # Save
        self._save_subtasks()
        
        # Complete subtask memory
        from clis.agent.memory_manager import MemoryManager
        memory_manager = MemoryManager()
        try:
            memory_manager.complete_task(subtask_id, success=success)
        except:
            # Subtask may not be registered in memory_manager, this is normal
            pass
        
        logger.info(f"Completed subtask: {subtask_id} - success={success}")
        
        # Unblock dependent tasks
        self._unblock_dependent_tasks(subtask_id)
        
        return True
    
    def _unblock_dependent_tasks(self, completed_subtask_id: str):
        """Unblock tasks that depend on the completed subtask"""
        for subtask in self.subtasks.values():
            if subtask.status == SubtaskStatus.BLOCKED:
                if self._are_dependencies_met(subtask):
                    subtask.status = SubtaskStatus.PENDING
                    logger.info(f"Unblocked subtask: {subtask.id}")
        
        self._save_subtasks()
    
    def get_all_subtasks(self) -> List[Subtask]:
        """Get all subtasks"""
        return list(self.subtasks.values())
    
    def get_subtask_by_id(self, subtask_id: str) -> Optional[Subtask]:
        """Get subtask by ID"""
        return self.subtasks.get(subtask_id)
    
    def get_progress_summary(self) -> Dict:
        """Get progress summary"""
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
        """Convert to Markdown format for display"""
        if not self.subtasks:
            return "No subtasks"
        
        progress = self.get_progress_summary()
        
        output = f"""## 🔀 Subtasks (Total: {progress['total']})

**Progress**: {progress['completed']}/{progress['total']} ({progress['completion_rate']:.1f}%)

| # | Description | Status | Dependencies |
|---|-------------|--------|--------------|
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
        """Save subtasks to file"""
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
        """Load subtasks from file"""
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
        """Get subtask file path"""
        return self.subtasks_file
