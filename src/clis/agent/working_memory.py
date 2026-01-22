"""
Working memory module - Structured operation records for the last 5-10 steps.

Features:
- Lightweight, pure in-memory
- Structured, easy to query
- Explicit state, reduces inference
"""

from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime
from collections import Counter
import re


@dataclass
class WorkingMemory:
    """
    Working memory - Structured operation records for the last 5-10 steps.
    
    Used to explicitly track Agent's operation history, helping weak models avoid loops.
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
    
    # Deduplication sets (fast queries)
    _files_read_set: Set[str] = field(default_factory=set, init=False, repr=False)
    _files_written_set: Set[str] = field(default_factory=set, init=False, repr=False)
    
    # Command cache - avoid repeating same commands
    _command_cache: Dict[str, Dict] = field(default_factory=dict, init=False, repr=False)  # {cmd: {result, time, count}}
    _max_cache_size: int = field(default=10, init=False, repr=False)
    
    # Known facts - store confirmed state information
    known_facts: List[str] = field(default_factory=list)
    
    def add_file_read(self, path: str) -> bool:
        """
        Record file read.
        
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
            # Even if duplicate, record it (for loop detection)
            self.files_read.append(path)
        return is_new
    
    def add_file_written(self, path: str):
        """Record file write."""
        if path not in self._files_written_set:
            self.files_written.append(path)
            self._files_written_set.add(path)
    
    def add_command(self, cmd: str, success: bool, result: str = ""):
        """
        Record command execution and cache result.
        
        Args:
            cmd: Command string
            success: Whether successful
            result: Command result (first 500 chars)
        """
        self.commands_run.append({
            'cmd': cmd,
            'time': datetime.now().isoformat(),
            'success': success
        })
        
        # Cache successful readonly command results
        is_readonly = self._is_readonly_command(cmd)
        if success and is_readonly:
            # Intelligently normalize command
            normalized_cmd = self._normalize_command(cmd)
            
            if normalized_cmd in self._command_cache:
                self._command_cache[normalized_cmd]['count'] += 1
            else:
                # Limit cache size
                if len(self._command_cache) >= self._max_cache_size:
                    # Delete oldest cache
                    oldest_cmd = min(
                        self._command_cache.keys(),
                        key=lambda k: self._command_cache[k]['time']
                    )
                    del self._command_cache[oldest_cmd]
                
                self._command_cache[normalized_cmd] = {
                    'result': result[:500],  # Only cache first 500 chars
                    'time': datetime.now().isoformat(),
                    'count': 1
                }
    
    def check_command_cache(self, cmd: str) -> Tuple[bool, str]:
        """
        Check if command is in cache.
        
        Args:
            cmd: Command string
            
        Returns:
            (is_cached, message) - Whether cached and prompt message
        """
        normalized_cmd = self._normalize_command(cmd)
        
        if normalized_cmd in self._command_cache:
            cache_entry = self._command_cache[normalized_cmd]
            count = cache_entry['count']
            result = cache_entry['result']
            
            message = f"""⚠️ This command has been executed {count} times recently, result is already in context:
Command: {normalized_cmd}
Result: {result}

💡 Suggestion: Don't repeat the same query command, use the existing result directly to continue!"""
            
            return True, message
        
        return False, ""
    
    def _normalize_command(self, cmd: str) -> str:
        """
        Intelligently normalize command, extract core part.
        
        Normalization rules:
        1. Remove cd directory change commands
        2. Remove pwd directory display commands
        3. Remove echo print commands
        4. Remove extra pipes and redirections (keep main command)
        5. Normalize spaces
        
        Args:
            cmd: Original command string
            
        Returns:
            Normalized command
            
        Examples:
            "cd /tmp && ls -la" -> "ls -la"
            "pwd && ls -la /tmp" -> "ls -la /tmp"
            "ls -la /tmp && echo done" -> "ls -la /tmp"
        """
        # Remove leading/trailing spaces
        cmd = cmd.strip()
        
        # Split command chain by &&
        parts = [p.strip() for p in cmd.split('&&')]
        
        # Filter out auxiliary commands
        filtered = []
        for part in parts:
            part_lower = part.lower()
            # Skip cd, pwd, echo and other auxiliary commands
            if part_lower.startswith('cd '):
                continue
            if part_lower == 'pwd':
                continue
            if part_lower.startswith('echo ') and "'" in part:
                # echo '...' type print commands
                continue
            filtered.append(part)
        
        # If filtered is empty, return original command (avoid losing information)
        if not filtered:
            return ' '.join(cmd.split())
        
        # Take first meaningful command as core
        core_cmd = filtered[0]
        
        # Remove trailing output redirection and error handling
        # Example: "ls -la 2>/dev/null || echo 'not found'"
        core_cmd = re.sub(r'\s*2>/dev/null.*$', '', core_cmd)
        core_cmd = re.sub(r'\s*\|\|.*$', '', core_cmd)
        
        # Normalize spaces
        return ' '.join(core_cmd.split())
    
    def _is_readonly_command(self, cmd: str) -> bool:
        """
        Determine if command is readonly (can be cached).
        
        Strategy:
        1. Extract normalized core command
        2. Check if core command is readonly
        3. Ignore auxiliary commands (cd, pwd, echo)
        
        Args:
            cmd: Command string
            
        Returns:
            True if readonly command
        """
        # Get normalized core command
        normalized = self._normalize_command(cmd)
        cmd_lower = normalized.lower().strip()
        
        # Readonly command keywords (command start)
        readonly_commands = [
            'ls', 'pwd', 'cat', 'head', 'tail', 'find', 'grep',
            'git status', 'git log', 'git diff', 'git branch',
            'which', 'whereis', 'file', 'stat',
            'wc', 'tree', 'du', 'df', 'ps', 'top'
        ]
        
        # Exclude write command keywords
        write_keywords = [
            'mkdir', 'touch', 'rm', 'mv', 'cp', 'chmod', 'chown',
            'git add', 'git commit', 'git push', 'git pull', 'git init',
            'git clone', 'git merge', 'git rebase',
            '>', '>>', 'tee', '|', 'wget', 'curl -X POST'
        ]
        
        # First check if contains write keywords
        for keyword in write_keywords:
            if keyword in cmd_lower:
                return False
        
        # Check if starts with readonly command
        for keyword in readonly_commands:
            if cmd_lower.startswith(keyword):
                return True
            # Also check commands after pipe
            if f'| {keyword}' in cmd_lower:
                return True
        
        return False
    
    def increment_tool(self, tool_name: str):
        """Increment tool usage count."""
        self.tools_used[tool_name] = self.tools_used.get(tool_name, 0) + 1
    
    def update_phase(self, phase: str, progress: str):
        """Update current phase."""
        self.current_phase = phase
        self.phase_progress = progress
    
    def add_known_fact(self, fact: str):
        """
        Add known fact (avoid repeated verification).
        
        Args:
            fact: Confirmed fact, e.g., "Directory /tmp/test exists"
        """
        if fact not in self.known_facts:
            self.known_facts.append(fact)
            # Keep only last 10 facts
            if len(self.known_facts) > 10:
                self.known_facts = self.known_facts[-10:]
    
    def get_known_facts_summary(self) -> str:
        """Get summary of known facts."""
        if not self.known_facts:
            return ""
        
        facts_list = "\n   • ".join(self.known_facts[-5:])  # Last 5
        return f"""
📝 Known Facts (recently confirmed, no need to verify again):
   • {facts_list}
"""
    
    def to_prompt(self, max_items: int = 10) -> str:
        """
        Convert to weak model-friendly prompt text.
        
        Design principles:
        - Use emoji and tree structure (visually clear)
        - Show quantity statistics (give model "progress sense")
        - Highlight recent items (temporal proximity)
        - Explicitly warn about duplicate operations
        - Show current working directory context
        
        Args:
            max_items: Maximum number of items to display
            
        Returns:
            Formatted prompt text
        """
        recent_files = self.files_read[-max_items:] if self.files_read else ["None"]
        files_summary = ", ".join(recent_files) if len(recent_files) <= 5 else \
                       ", ".join(recent_files[:5]) + f" ... (total {len(self.files_read)})"
        
        recent_written = self.files_written[-5:] if self.files_written else ["None"]
        written_summary = ", ".join(recent_written)
        
        # Format recent commands, extract working directory info
        recent_cmds = []
        last_work_dir = None
        if self.commands_run:
            for cmd_entry in self.commands_run[-3:]:
                cmd = cmd_entry['cmd']
                # Extract directory from cd command
                if 'cd ' in cmd:
                    import re
                    match = re.search(r'cd\s+([^\s&|;]+)', cmd)
                    if match:
                        last_work_dir = match.group(1)
                recent_cmds.append(cmd[:50])
        if not recent_cmds:
            recent_cmds = ["None"]
        cmd_summary = "\n   ".join(recent_cmds)
        
        # Add working directory hint
        work_dir_hint = ""
        if last_work_dir:
            work_dir_hint = f"\n💡 Last switched to directory: {last_work_dir}\n   (If you need to perform Git/file operations in that directory, remember to cd there first)"
        
        known_facts_section = self.get_known_facts_summary()
        
        return f"""
╭──────────────────────────────────────────────────────────────╮
│                   📋 Working Memory (WORKING MEMORY)          │
╰──────────────────────────────────────────────────────────────╯

🎯 Current Phase: {self.current_phase} ({self.phase_progress})
{work_dir_hint}{known_facts_section}
📂 Files Read (total {len(self.files_read)}):
   {files_summary}

✏️  Files Written (total {len(self.files_written)}):
   {written_summary}

⚙️  Commands Executed (total {len(self.commands_run)}):
   {cmd_summary}

📊 Tool Usage Statistics:
   {self._format_tool_stats()}

⚠️  Important Reminders:
   • If file you want to read is in "Files Read" list → Don't repeat reading!
   • If files read exceed 10 → Should start analyzing instead of continuing to collect
   • If same tool used >5 times → May be in a loop, change strategy!
   • Git/file operations need to be in correct directory → Use cd to switch or specify full path in command!
   • Known facts are trustworthy → Act directly based on these facts, no need to verify again!
"""
    
    def _format_tool_stats(self) -> str:
        """Format tool statistics."""
        if not self.tools_used:
            return "   (None)"
        
        sorted_tools = sorted(self.tools_used.items(), key=lambda x: x[1], reverse=True)
        stats = []
        for tool, count in sorted_tools[:5]:
            warning = " ⚠️ Overused!" if count > 5 else ""
            stats.append(f"{tool}: {count} times{warning}")
        return "\n   ".join(stats)
    
    def detect_loop(self) -> Tuple[bool, str]:
        """
        Detect if stuck in a loop.
        
        Strategy: Focus on detecting ACTUAL loops (repeated failures),
        not just frequent use of common tools.
        
        Returns:
            (is_loop, reason)
        """
        # Rule 1: Single file read more than 3 times (increased from 2)
        # Reading same file multiple times might be intentional
        file_counts = Counter(self.files_read)
        for file, count in file_counts.items():
            if count > 3:
                return True, f"File '{file}' has been read {count} times!"
        
        # Rule 2: Single tool used excessively (EXCLUDING common tools)
        # Common tools that should NOT be limited:
        # - execute_command: Used for many different commands
        # - write_file: Creating multiple files is normal
        # - edit_file: Editing multiple files is normal
        # - grep: Searching multiple patterns is normal
        common_tools_no_limit = {
            'execute_command',
            'write_file', 
            'edit_file',
            'grep',
            'read_file',  # Reading different files is normal
            'list_files',
            'git_add',
            'git_commit'
        }
        
        for tool, count in self.tools_used.items():
            # Skip common tools
            if tool in common_tools_no_limit:
                continue
            
            # For other tools, limit to 10 times
            if count > 10:
                return True, f"Tool '{tool}' has been used {count} times!"
        
        # Rule 3: Last 5 operations are reading SAME 1-2 files back and forth
        if len(self.files_read) >= 5:
            recent = self.files_read[-5:]
            unique_files = set(recent)
            if len(unique_files) <= 2 and len(recent) == 5:
                # Check if it's actually alternating between same files
                if recent.count(recent[0]) >= 3:  # Same file appears 3+ times in last 5
                    return True, f"Repeatedly reading same files: {unique_files}"
        
        # Rule 4: Detect IDENTICAL commands repeated (not just execute_command usage)
        if len(self.commands_run) >= 5:
            recent_cmds = [c['cmd'] for c in self.commands_run[-5:]]
            # Check if last 5 commands are IDENTICAL
            if len(set(recent_cmds)) == 1:
                return True, f"Executed identical command 5 times: {recent_cmds[0][:100]}"
            
            # Check if last 3 commands are IDENTICAL (stricter for recent)
            if len(self.commands_run) >= 3:
                last_3 = [c['cmd'] for c in self.commands_run[-3:]]
                if len(set(last_3)) == 1:
                    return True, f"Executed identical command 3 times in a row: {last_3[0][:100]}"
        
        return False, ""
    
    def get_stats(self) -> Dict:
        """
        Get statistics.
        
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
        """Clear working memory."""
        self.files_read.clear()
        self.files_written.clear()
        self.commands_run.clear()
        self.tools_used.clear()
        self._files_read_set.clear()
        self._files_written_set.clear()
        self.current_phase = "initialization"
        self.phase_progress = "0/0"
