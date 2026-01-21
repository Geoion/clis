"""
Working memory module - Structured operation records for recent 5-10 steps

Features:
- Lightweight, pure in-memory
- Structured, easy to query
- Explicit state, less reasoning
"""

from typing import List, Dict, Set
from dataclasses import dataclass, field
from datetime import datetime
from collections import Counter


@dataclass
class WorkingMemory:
    """
    Working memory - Structured operation records for recent 5-10 steps
    
    Used to explicitly track Agent's operation history, helping weak models avoid loops
    """
    
    # Operation records (preserve order)
    files_read: List[str] = field(default_factory=list)
    files_written: List[str] = field(default_factory=list)
    commands_run: List[Dict] = field(default_factory=list)  # {cmd, time, success}
    
    # Tool usage statistics
    tools_used: Dict[str, int] = field(default_factory=dict)
    
    # Explicit state
    current_phase: str = "initialization"
    phase_progress: str = "0/0"
    
    # Deduplication sets (fast lookup)
    _files_read_set: Set[str] = field(default_factory=set, init=False, repr=False)
    _files_written_set: Set[str] = field(default_factory=set, init=False, repr=False)
    
    def add_file_read(self, path: str) -> bool:
        """
        Record file read
        
        Args:
            path: File path
            
        Returns:
            True if new, False if duplicate
        """
        is_new = path not in self._files_read_set
        if is_new:
            self.files_read.append(path)
            self._files_read_set.add(path)
        else:
            # Even if duplicate, record (for loop detection)
            self.files_read.append(path)
        return is_new
    
    def add_file_written(self, path: str):
        """Record file write"""
        if path not in self._files_written_set:
            self.files_written.append(path)
            self._files_written_set.add(path)
    
    def add_command(self, cmd: str, success: bool):
        """Record command execution"""
        self.commands_run.append({
            'cmd': cmd,
            'time': datetime.now().isoformat(),
            'success': success
        })
    
    def increment_tool(self, tool_name: str):
        """Increment tool usage count"""
        self.tools_used[tool_name] = self.tools_used.get(tool_name, 0) + 1
    
    def update_phase(self, phase: str, progress: str):
        """Update current phase"""
        self.current_phase = phase
        self.phase_progress = progress
    
    def to_prompt(self, max_items: int = 10) -> str:
        """
        Convert to weak-model-friendly prompt text
        
        Design principles:
        - Use emoji and tree structure (visual clarity)
        - Show quantity statistics (give model "progress sense")
        - Highlight recent items (temporal proximity)
        - Clearly warn about repeated operations
        
        Args:
            max_items: Maximum items to display
            
        Returns:
            Formatted prompt text
        """
        recent_files = self.files_read[-max_items:] if self.files_read else ["None"]
        files_summary = ", ".join(recent_files) if len(recent_files) <= 5 else \
                       ", ".join(recent_files[:5]) + f" ... ({len(self.files_read)} total)"
        
        recent_written = self.files_written[-5:] if self.files_written else ["None"]
        written_summary = ", ".join(recent_written)
        
        recent_cmds = [c['cmd'][:50] for c in self.commands_run[-3:]] if self.commands_run else ["None"]
        cmd_summary = "\n   ".join(recent_cmds)
        
        return f"""
╭──────────────────────────────────────────────────────────────╮
│                   📋 WORKING MEMORY                           │
╰──────────────────────────────────────────────────────────────╯

🎯 Current Phase: {self.current_phase} ({self.phase_progress})

📂 Files Read ({len(self.files_read)} total):
   {files_summary}

✏️  Files Written ({len(self.files_written)} total):
   {written_summary}

⚙️  Commands Executed ({len(self.commands_run)} total):
   {cmd_summary}

📊 Tool Usage Statistics:
   {self._format_tool_stats()}

⚠️  Important Reminders:
   • If file you want to read is in "Files Read" list → Don't repeat reading!
   • If files read exceeds 10 → Should start analysis instead of continuing collection
   • If same tool used more than 5 times → May be stuck in loop, change strategy!
"""
    
    def _format_tool_stats(self) -> str:
        """Format tool statistics"""
        if not self.tools_used:
            return "   (None yet)"
        
        sorted_tools = sorted(self.tools_used.items(), key=lambda x: x[1], reverse=True)
        stats = []
        for tool, count in sorted_tools[:5]:
            warning = " ⚠️ Overused!" if count > 5 else ""
            stats.append(f"{tool}: {count} times{warning}")
        return "\n   ".join(stats)
    
    def detect_loop(self) -> tuple[bool, str]:
        """
        Detect if stuck in loop
        
        Returns:
            (is_loop, reason)
        """
        # Rule 1: Single file read more than 2 times
        file_counts = Counter(self.files_read)
        for file, count in file_counts.items():
            if count > 2:
                return True, f"File '{file}' read {count} times!"
        
        # Rule 2: Single tool used more than 10 times
        for tool, count in self.tools_used.items():
            if count > 10:
                return True, f"Tool '{tool}' used {count} times!"
        
        # Rule 3: Last 5 operations all read_file
        if len(self.files_read) >= 5:
            recent = self.files_read[-5:]
            if len(set(recent)) <= 2:  # Only switching between reading 2 files
                return True, f"Last 5 operations all reading files: {set(recent)}"
        
        return False, ""
    
    def get_stats(self) -> Dict:
        """
        Get statistics
        
        Returns:
            Statistics dictionary
        """
        return {
            'files_read_count': len(self.files_read),
            'files_written_count': len(self.files_written),
            'commands_run_count': len(self.commands_run),
            'unique_files_read': len(self._files_read_set),
            'unique_files_written': len(self._files_written_set),
            'tools_used': dict(self.tools_used),
            'current_phase': self.current_phase,
            'phase_progress': self.phase_progress,
        }
    
    def clear(self):
        """Clear working memory"""
        self.files_read.clear()
        self.files_written.clear()
        self.commands_run.clear()
        self.tools_used.clear()
        self._files_read_set.clear()
        self._files_written_set.clear()
        self.current_phase = "initialization"
        self.phase_progress = "0/0"
