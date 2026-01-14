"""
List terminals tool - list all active terminal/shell processes.
"""

import psutil
from pathlib import Path
from typing import Any, Dict

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class ListTerminalsTool(Tool):
    """List all active terminal/shell processes."""
    
    @property
    def name(self) -> str:
        return "list_terminals"
    
    @property
    def description(self) -> str:
        return (
            "List all active terminal/shell processes (bash, zsh, sh, etc.). "
            "Shows process IDs, command lines, and working directories. "
            "Useful for understanding what shells are running and where."
        )
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "include_parent_info": {
                    "type": "boolean",
                    "description": "Include parent process information (default: false)",
                    "default": False
                }
            },
            "required": []
        }
    
    @property
    def is_readonly(self) -> bool:
        return True
    
    def execute(self, include_parent_info: bool = False) -> ToolResult:
        """
        Execute list terminals/shells.
        
        Args:
            include_parent_info: Include parent process info
        
        Returns:
            ToolResult with list of shell processes
        """
        try:
            # Common shell process names
            shell_names = {'bash', 'zsh', 'sh', 'fish', 'tcsh', 'csh', 'ksh', 'dash'}
            
            shells = []
            
            # Iterate through all processes
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cwd', 'create_time', 'status']):
                try:
                    proc_info = proc.info
                    proc_name = proc_info.get('name', '').lower()
                    
                    # Check if it's a shell process
                    if any(shell in proc_name for shell in shell_names):
                        # Get command line
                        cmdline = proc_info.get('cmdline', [])
                        cmdline_str = ' '.join(cmdline) if cmdline else proc_name
                        
                        # Get working directory
                        try:
                            cwd = proc_info.get('cwd', None)
                            if cwd:
                                # Make it relative if possible
                                try:
                                    cwd_path = Path(cwd)
                                    if cwd_path.is_relative_to(Path.cwd()):
                                        cwd = f"./{cwd_path.relative_to(Path.cwd())}"
                                except:
                                    pass  # Keep absolute path
                        except (psutil.AccessDenied, psutil.NoSuchProcess):
                            cwd = None
                        
                        # Get parent process info if requested
                        parent_info = None
                        if include_parent_info:
                            try:
                                parent = proc.parent()
                                if parent:
                                    parent_info = {
                                        'pid': parent.pid,
                                        'name': parent.name(),
                                        'cmdline': ' '.join(parent.cmdline()[:3]) if parent.cmdline() else parent.name()
                                    }
                            except (psutil.AccessDenied, psutil.NoSuchProcess):
                                parent_info = None
                        
                        shell_info = {
                            'pid': proc_info['pid'],
                            'name': proc_name,
                            'cmdline': cmdline_str,
                            'cwd': cwd,
                            'status': proc_info.get('status', 'unknown'),
                            'create_time': proc_info.get('create_time'),
                        }
                        
                        if parent_info:
                            shell_info['parent'] = parent_info
                        
                        shells.append(shell_info)
                
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            
            # Sort by creation time (newest first)
            shells.sort(key=lambda x: x.get('create_time', 0), reverse=True)
            
            # Format output
            if not shells:
                output = "No shell processes found.\n"
                output += "This tool finds active bash/zsh/sh processes.\n"
                output += "If you're looking for command history, try using the system's history command instead."
            else:
                output = f"Found {len(shells)} active shell process(es):\n\n"
                
                for i, shell in enumerate(shells, 1):
                    output += "="*70 + "\n"
                    output += f"Shell #{i}\n"
                    output += "="*70 + "\n"
                    output += f"PID:      {shell['pid']}\n"
                    output += f"Name:     {shell['name']}\n"
                    output += f"Status:   {shell['status']}\n"
                    
                    if shell['cwd']:
                        output += f"CWD:      {shell['cwd']}\n"
                    
                    output += f"Command:  {shell['cmdline'][:80]}"
                    if len(shell['cmdline']) > 80:
                        output += "..."
                    output += "\n"
                    
                    if shell.get('parent'):
                        parent = shell['parent']
                        output += f"Parent:   {parent['name']} (PID: {parent['pid']})\n"
                        output += f"          {parent['cmdline'][:60]}\n"
                    
                    output += "\n"
                
                output += "💡 Tip: Use 'ps aux | grep <shell_name>' for more details\n"
                output += "💡 Tip: Use 'lsof -p <pid>' to see open files for a process\n"
            
            return ToolResult(
                success=True,
                output=output,
                metadata={
                    'count': len(shells),
                    'shells': shells
                }
            )
        
        except Exception as e:
            logger.error(f"Error listing shells: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error listing shells: {str(e)}"
            )
