"""
Episodic memory module - Persistent Markdown documents for current tasks.

Features:
- Persisted to .clis_memory/ directory
- Human-readable and editable
- Structured Markdown (checklist, findings, next steps)
- Persists across sessions
"""

from pathlib import Path
from typing import Optional, TYPE_CHECKING
from datetime import datetime
import re

if TYPE_CHECKING:
    from clis.agent.subtask_manager import SubtaskManager


class EpisodicMemory:
    """
    Episodic memory - Persistent Markdown documents for current tasks.
    
    Each task corresponds to a Markdown file containing:
    - Task objectives
    - Task breakdown (checklist)
    - Key findings
    - Current progress
    - Next actions
    - Execution log
    """
    
    def __init__(self, task_id: str, memory_dir: str = ".clis_memory"):
        self.task_id = task_id
        self.memory_dir = Path(memory_dir)
        self.tasks_dir = self.memory_dir / "tasks" / "active"
        self.task_file = self.tasks_dir / f"task_{task_id}.md"
        
        # Subtask manager (lazy loading)
        self._subtask_manager: Optional['SubtaskManager'] = None
        
        # Ensure directory exists
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
    
    def load_or_create(self, task_description: str) -> str:
        """
        Load existing task document or create a new one.
        
        Args:
            task_description: User's task description
            
        Returns:
            Task document content
        """
        if self.task_file.exists():
            return self.task_file.read_text(encoding='utf-8')
        else:
            return self._create_initial_doc(task_description)
    
    def _create_initial_doc(self, task_description: str) -> str:
        """Create initial task document."""
        doc = f"""# Task: {task_description}

**Task ID**: {self.task_id}  
**Created**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Status**: 🔄 In Progress

---

## 📋 Task Objectives

{task_description}

---

## ✅ Task Breakdown

<!-- Task steps will be automatically updated here -->
- [ ] Steps will be automatically identified during execution

---

## 🔍 Key Findings

*(Will be automatically recorded during execution)*

---

## 📊 Current Progress

**Phase**: Initialization  
**Progress**: 0/0

---

## 🎯 Next Actions

Starting task execution...

---

## 📝 Execution Log

"""
        self.task_file.write_text(doc, encoding='utf-8')
        return doc
    
    def update_step(self, step_description: str, status: str = "done"):
        """
        Update task step status.
        
        Args:
            step_description: Step description
            status: "done" | "in_progress" | "pending"
        """
        if not self.task_file.exists():
            return
        
        content = self.task_file.read_text(encoding='utf-8')
        
        # Find task breakdown section
        checklist_pattern = r'(## ✅ Task Breakdown.*?)(##|\Z)'
        match = re.search(checklist_pattern, content, re.DOTALL)
        
        if match:
            checklist_section = match.group(1)
            
            # Check if step already exists
            step_exists = step_description in checklist_section
            
            if not step_exists:
                # Add new step
                checkbox = {
                    "done": "- [x]",
                    "in_progress": "- [ ] 🔄",
                    "pending": "- [ ]"
                }.get(status, "- [ ]")
                
                new_step = f"{checkbox} {step_description}\n"
                
                # Insert before next ##
                next_section_pos = content.find('##', match.end(1))
                if next_section_pos != -1:
                    # Insert before found position
                    insert_pos = content.rfind('\n', match.start(1), next_section_pos)
                    if insert_pos == -1:
                        insert_pos = match.end(1)
                    content = content[:insert_pos] + '\n' + new_step + content[insert_pos:]
                else:
                    # Insert at end
                    content = content.rstrip() + '\n' + new_step + '\n'
                
                self.task_file.write_text(content, encoding='utf-8')
    
    def add_finding(self, finding: str, category: str = "general"):
        """
        Add key finding.
        
        Args:
            finding: Finding content
            category: Category label
        """
        if not self.task_file.exists():
            return
        
        content = self.task_file.read_text(encoding='utf-8')
        
        # Find key findings section
        findings_pattern = r'(## 🔍 Key Findings.*?)(##|\Z)'
        match = re.search(findings_pattern, content, re.DOTALL)
        
        if match:
            # Add new finding
            timestamp = datetime.now().strftime('%H:%M:%S')
            new_finding = f"- **[{category}]** ({timestamp}): {finding}\n"
            
            # Insert before next ##
            next_section_pos = content.find('##', match.end(1))
            if next_section_pos != -1:
                insert_pos = content.rfind('\n', match.start(1), next_section_pos)
                if insert_pos == -1:
                    insert_pos = match.end(1)
                content = content[:insert_pos] + '\n' + new_finding + content[insert_pos:]
            else:
                content = content.rstrip() + '\n' + new_finding + '\n'
            
            self.task_file.write_text(content, encoding='utf-8')
    
    def update_progress(self, phase: str, progress: str):
        """Update current progress."""
        if not self.task_file.exists():
            return
        
        content = self.task_file.read_text(encoding='utf-8')
        
        # Update phase
        content = re.sub(
            r'\*\*Phase\*\*:.*',
            f'**Phase**: {phase}',
            content
        )
        
        # Update progress
        content = re.sub(
            r'\*\*Progress\*\*:.*',
            f'**Progress**: {progress}',
            content
        )
        
        self.task_file.write_text(content, encoding='utf-8')
    
    def update_next_action(self, action: str):
        """Update next action suggestion."""
        if not self.task_file.exists():
            return
        
        content = self.task_file.read_text(encoding='utf-8')
        
        # Find next actions section
        next_action_pattern = r'(## 🎯 Next Actions.*?)(##|\Z)'
        match = re.search(next_action_pattern, content, re.DOTALL)
        
        if match:
            new_section = f"## 🎯 Next Actions\n\n{action}\n\n"
            content = content[:match.start(1)] + new_section + content[match.end(1):]
            self.task_file.write_text(content, encoding='utf-8')
    
    def append_log(self, log_entry: str):
        """Add execution log entry."""
        if not self.task_file.exists():
            return
        
        content = self.task_file.read_text(encoding='utf-8')
        
        # Append to execution log section
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_line = f"\n[{timestamp}] {log_entry}\n"
        
        content = content.rstrip() + log_line
        self.task_file.write_text(content, encoding='utf-8')
    
    def inject_to_prompt(self, include_log: bool = False) -> str:
        """
        Inject task document into prompt.
        
        Args:
            include_log: Whether to include execution log (longer)
            
        Returns:
            Formatted prompt text
        """
        if not self.task_file.exists():
            return ""
        
        content = self.task_file.read_text(encoding='utf-8')
        
        if not include_log:
            # Remove execution log section (save tokens)
            content = re.sub(r'## 📝 Execution Log.*', '', content, flags=re.DOTALL)
        
        return f"""
╭──────────────────────────────────────────────────────────────╮
│              📖 Task Memory (TASK MEMORY / MEMORY BANK)      │
╰──────────────────────────────────────────────────────────────╯

{content}

⚠️  Important Reminders:
   • Check the ✅ Task Breakdown above to see which steps are completed
   • Review 🔍 Key Findings - collected information is here
   • Refer to 🎯 Next Actions suggestions
   • If task is complete, call {{"type": "done", "summary": "..."}}
"""
    
    def get_file_path(self) -> Path:
        """Get task file path."""
        return self.task_file
    
    def get_subtask_manager(self) -> 'SubtaskManager':
        """
        Get subtask manager (lazy loading).
        
        Returns:
            SubtaskManager instance
        """
        if self._subtask_manager is None:
            from clis.agent.subtask_manager import SubtaskManager
            self._subtask_manager = SubtaskManager(self.task_id, str(self.memory_dir))
        
        return self._subtask_manager
    
    def has_subtasks(self) -> bool:
        """Check if there are subtasks."""
        if self._subtask_manager is None:
            # Check if subtask directory exists
            subtasks_dir = self.memory_dir / "tasks" / "active" / f"subtasks_{self.task_id}"
            return subtasks_dir.exists()
        
        return len(self._subtask_manager.subtasks) > 0
    
    def exists(self) -> bool:
        """Check if task file exists."""
        return self.task_file.exists()
