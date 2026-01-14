"""
Read process info tool - get detailed information about a process.
"""

import psutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class ReadTerminalOutputTool(Tool):
    """Get detailed information about a process (shell, terminal, etc.)."""
    
    @property
    def name(self) -> str:
        return "read_terminal_output"
    
    @property
    def description(self) -> str:
        return (
            "Get detailed information about a process by PID. "
            "Shows process details, open files, connections, and resource usage. "
            "Useful for debugging and understanding what a process is doing. "
            "For shell history, use 'history' command or check ~/.bash_history, ~/.zsh_history."
        )
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pid": {
                    "type": "integer",
                    "description": "Process ID to get information about"
                },
                "include_files": {
                    "type": "boolean",
                    "description": "Include open files (default: true)",
                    "default": True
                },
                "include_connections": {
                    "type": "boolean",
                    "description": "Include network connections (default: false)",
                    "default": False
                },
                "show_history": {
                    "type": "boolean",
                    "description": "Show shell history file if it's a shell process (default: true)",
                    "default": True
                }
            },
            "required": ["pid"]
        }
    
    @property
    def is_readonly(self) -> bool:
        return True
    
    def execute(
        self,
        pid: int,
        include_files: bool = True,
        include_connections: bool = False,
        show_history: bool = True
    ) -> ToolResult:
        """
        Execute process information retrieval.
        
        Args:
            pid: Process ID
            include_files: Include open files
            include_connections: Include network connections
            show_history: Show shell history if applicable
            
        Returns:
            ToolResult with process information
        """
        try:
            # Check if process exists
            if not psutil.pid_exists(pid):
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Process with PID {pid} not found. Use list_terminals to see active processes."
                )
            
            try:
                proc = psutil.Process(pid)
            except psutil.NoSuchProcess:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Process {pid} no longer exists."
                )
            
            # Gather process information
            output = f"Process Information (PID: {pid})\n\n"
            output += "="*70 + "\n"
            output += "BASIC INFO\n"
            output += "="*70 + "\n"
            
            try:
                output += f"Name:        {proc.name()}\n"
                output += f"Status:      {proc.status()}\n"
                output += f"Create Time: {proc.create_time()}\n"
                
                cmdline = proc.cmdline()
                if cmdline:
                    output += f"Command:     {' '.join(cmdline[:5])}"
                    if len(cmdline) > 5:
                        output += f" ... ({len(cmdline)} args)"
                    output += "\n"
                
                try:
                    cwd = proc.cwd()
                    output += f"CWD:         {cwd}\n"
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    output += f"CWD:         (access denied)\n"
                
                # Parent process
                try:
                    parent = proc.parent()
                    if parent:
                        output += f"Parent:      {parent.name()} (PID: {parent.pid})\n"
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    pass
                
                # Resource usage
                try:
                    mem_info = proc.memory_info()
                    output += f"Memory:      {mem_info.rss / 1024 / 1024:.1f} MB (RSS)\n"
                    cpu_percent = proc.cpu_percent(interval=0.1)
                    output += f"CPU:         {cpu_percent}%\n"
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    pass
                
            except (psutil.AccessDenied, psutil.NoSuchProcess) as e:
                output += f"(Some info unavailable: {e})\n"
            
            # Open files
            if include_files:
                output += "\n" + "="*70 + "\n"
                output += "OPEN FILES\n"
                output += "="*70 + "\n"
                try:
                    open_files = proc.open_files()
                    if open_files:
                        for f in open_files[:20]:  # Limit to 20
                            output += f"  {f.path} (FD: {f.fd}, mode: {f.mode})\n"
                        if len(open_files) > 20:
                            output += f"  ... and {len(open_files) - 20} more\n"
                    else:
                        output += "  (No open files or access denied)\n"
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    output += "  (Access denied)\n"
            
            # Network connections
            if include_connections:
                output += "\n" + "="*70 + "\n"
                output += "NETWORK CONNECTIONS\n"
                output += "="*70 + "\n"
                try:
                    connections = proc.connections()
                    if connections:
                        for conn in connections[:20]:
                            output += f"  {conn.type.name}: {conn.laddr} -> {conn.raddr} ({conn.status})\n"
                        if len(connections) > 20:
                            output += f"  ... and {len(connections) - 20} more\n"
                    else:
                        output += "  (No connections)\n"
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    output += "  (Access denied)\n"
            
            # Shell history (if it's a shell process)
            if show_history:
                proc_name = proc.name().lower()
                if any(shell in proc_name for shell in ['bash', 'zsh', 'sh', 'fish']):
                    output += "\n" + "="*70 + "\n"
                    output += "SHELL HISTORY (last 20 commands)\n"
                    output += "="*70 + "\n"
                    
                    # Determine history file
                    history_files = {
                        'bash': Path.home() / '.bash_history',
                        'zsh': Path.home() / '.zsh_history',
                        'fish': Path.home() / '.local' / 'share' / 'fish' / 'fish_history',
                    }
                    
                    history_file = None
                    for shell, file_path in history_files.items():
                        if shell in proc_name and file_path.exists():
                            history_file = file_path
                            break
                    
                    if history_file:
                        try:
                            with open(history_file, 'r', encoding='utf-8', errors='ignore') as f:
                                lines = f.readlines()
                                recent = lines[-20:] if len(lines) > 20 else lines
                                for line in recent:
                                    line = line.strip()
                                    # Clean up zsh history format
                                    if line.startswith(':'):
                                        parts = line.split(';', 1)
                                        if len(parts) > 1:
                                            line = parts[1]
                                    output += f"  {line}\n"
                        except Exception as e:
                            output += f"  (Failed to read history: {e})\n"
                    else:
                        output += "  (History file not found)\n"
            
            output += "\n" + "="*70 + "\n"
            output += "💡 Tip: Use 'ps -p {pid} -o args' for full command line\n"
            output += "💡 Tip: Use 'lsof -p {pid}' for all open files\n"
            output += "💡 Tip: Use 'strace -p {pid}' to trace system calls\n"
            
            return ToolResult(
                success=True,
                output=output,
                metadata={
                    'pid': pid,
                    'name': proc.name(),
                    'status': proc.status()
                }
            )
        
        except Exception as e:
            logger.error(f"Error reading process info: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error reading process info: {str(e)}"
            )
