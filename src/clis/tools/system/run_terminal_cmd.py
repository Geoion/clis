"""
Enhanced terminal command tool with background execution support.
"""

import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class RunTerminalCmdTool(Tool):
    """
    Enhanced terminal command execution tool.
    
    Supports both foreground and background execution.
    Background processes are tracked and can be managed.
    """
    
    def __init__(self):
        """Initialize tool with process tracking."""
        self._background_processes = {}
        self._process_lock = threading.Lock()
    
    @property
    def name(self) -> str:
        return "run_terminal_cmd"
    
    @property
    def description(self) -> str:
        return (
            "Execute terminal commands. Supports both foreground and background execution. "
            "Background mode is useful for long-running processes like dev servers. "
            "Can list and manage background processes."
        )
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Command to execute"
                },
                "is_background": {
                    "type": "boolean",
                    "description": "Run in background (default: false)",
                    "default": False
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds for foreground commands (default: 30)",
                    "default": 30
                },
                "working_dir": {
                    "type": "string",
                    "description": "Working directory (default: current directory)",
                    "default": ""
                },
                "action": {
                    "type": "string",
                    "description": "Action: 'run', 'list', 'stop', 'status' (default: run)",
                    "enum": ["run", "list", "stop", "status"],
                    "default": "run"
                },
                "process_id": {
                    "type": "integer",
                    "description": "Process ID for stop/status actions",
                    "default": 0
                }
            },
            "required": []
        }
    
    @property
    def is_readonly(self) -> bool:
        return False  # Executes commands
    
    def execute(
        self,
        command: str = "",
        is_background: bool = False,
        timeout: int = 30,
        working_dir: str = "",
        action: str = "run",
        process_id: int = 0
    ) -> ToolResult:
        """
        Execute terminal command or manage background processes.
        
        Args:
            command: Command to execute
            is_background: Run in background
            timeout: Timeout for foreground commands
            working_dir: Working directory
            action: Action to perform
            process_id: Process ID for management actions
            
        Returns:
            ToolResult with execution result
        """
        try:
            if action == "list":
                return self._list_processes()
            elif action == "stop":
                return self._stop_process(process_id)
            elif action == "status":
                return self._get_status(process_id)
            elif action == "run":
                if not command:
                    return ToolResult(
                        success=False,
                        output="",
                        error="command is required for run action"
                    )
                
                if is_background:
                    return self._run_background(command, working_dir)
                else:
                    return self._run_foreground(command, timeout, working_dir)
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Unknown action: {action}"
                )
        
        except Exception as e:
            logger.error(f"Error in run_terminal_cmd: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error: {str(e)}"
            )
    
    def _run_foreground(
        self,
        command: str,
        timeout: int,
        working_dir: str
    ) -> ToolResult:
        """Run command in foreground."""
        try:
            # Prepare working directory
            cwd = None
            if working_dir:
                cwd = Path(working_dir).expanduser()
                if not cwd.exists():
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"Working directory does not exist: {working_dir}"
                    )
            
            # Execute command
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd
            )
            
            # Format output
            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"
            
            success = result.returncode == 0
            error = None if success else f"Command exited with code {result.returncode}"
            
            return ToolResult(
                success=success,
                output=output.strip() if output else "(no output)",
                error=error,
                metadata={
                    "exit_code": result.returncode,
                    "command": command
                }
            )
        
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                output="",
                error=f"Command timed out after {timeout} seconds"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Error executing command: {str(e)}"
            )
    
    def _run_background(
        self,
        command: str,
        working_dir: str
    ) -> ToolResult:
        """Run command in background."""
        try:
            # Prepare working directory
            cwd = None
            if working_dir:
                cwd = Path(working_dir).expanduser()
                if not cwd.exists():
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"Working directory does not exist: {working_dir}"
                    )
            
            # Start process
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=cwd
            )
            
            # Track process
            with self._process_lock:
                self._background_processes[process.pid] = {
                    'process': process,
                    'command': command,
                    'start_time': time.time(),
                    'working_dir': str(cwd) if cwd else None
                }
            
            output = f"✓ Command started in background\n\n"
            output += f"Process ID: {process.pid}\n"
            output += f"Command: {command}\n"
            if cwd:
                output += f"Working directory: {cwd}\n"
            output += f"\nUse action='status' with process_id={process.pid} to check status\n"
            output += f"Use action='stop' with process_id={process.pid} to stop the process"
            
            return ToolResult(
                success=True,
                output=output,
                metadata={
                    'pid': process.pid,
                    'command': command,
                    'background': True
                }
            )
        
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Error starting background process: {str(e)}"
            )
    
    def _list_processes(self) -> ToolResult:
        """List background processes."""
        with self._process_lock:
            if not self._background_processes:
                return ToolResult(
                    success=True,
                    output="No background processes running"
                )
            
            output = f"Background processes ({len(self._background_processes)}):\n\n"
            
            for pid, info in self._background_processes.items():
                process = info['process']
                command = info['command']
                start_time = info['start_time']
                working_dir = info.get('working_dir')
                
                # Check if still running
                poll_result = process.poll()
                if poll_result is None:
                    status = "🟢 Running"
                else:
                    status = f"🔴 Stopped (exit code: {poll_result})"
                
                # Calculate runtime
                runtime = int(time.time() - start_time)
                runtime_str = f"{runtime}s"
                if runtime >= 60:
                    runtime_str = f"{runtime // 60}m {runtime % 60}s"
                
                output += f"PID {pid}: {status}\n"
                output += f"  Command: {command}\n"
                output += f"  Runtime: {runtime_str}\n"
                if working_dir:
                    output += f"  Working dir: {working_dir}\n"
                output += "\n"
            
            return ToolResult(
                success=True,
                output=output.strip(),
                metadata={
                    'count': len(self._background_processes),
                    'pids': list(self._background_processes.keys())
                }
            )
    
    def _stop_process(self, process_id: int) -> ToolResult:
        """Stop a background process."""
        if not process_id:
            return ToolResult(
                success=False,
                output="",
                error="process_id is required for stop action"
            )
        
        with self._process_lock:
            if process_id not in self._background_processes:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Process {process_id} not found"
                )
            
            info = self._background_processes[process_id]
            process = info['process']
            command = info['command']
            
            # Check if already stopped
            if process.poll() is not None:
                del self._background_processes[process_id]
                return ToolResult(
                    success=True,
                    output=f"Process {process_id} was already stopped"
                )
            
            # Terminate process
            try:
                process.terminate()
                
                # Wait for termination (with timeout)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill if not terminated
                    process.kill()
                    process.wait()
                
                # Remove from tracking
                del self._background_processes[process_id]
                
                output = f"✓ Process {process_id} stopped\n"
                output += f"Command: {command}"
                
                return ToolResult(
                    success=True,
                    output=output,
                    metadata={'pid': process_id}
                )
            
            except Exception as e:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Error stopping process: {str(e)}"
                )
    
    def _get_status(self, process_id: int) -> ToolResult:
        """Get status of a background process."""
        if not process_id:
            return ToolResult(
                success=False,
                output="",
                error="process_id is required for status action"
            )
        
        with self._process_lock:
            if process_id not in self._background_processes:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Process {process_id} not found"
                )
            
            info = self._background_processes[process_id]
            process = info['process']
            command = info['command']
            start_time = info['start_time']
            working_dir = info.get('working_dir')
            
            # Check status
            poll_result = process.poll()
            
            # Calculate runtime
            runtime = int(time.time() - start_time)
            runtime_str = f"{runtime}s"
            if runtime >= 60:
                runtime_str = f"{runtime // 60}m {runtime % 60}s"
            
            output = f"Process {process_id} status:\n\n"
            
            if poll_result is None:
                output += "Status: 🟢 Running\n"
            else:
                output += f"Status: 🔴 Stopped (exit code: {poll_result})\n"
                
                # Try to get output
                try:
                    stdout, stderr = process.communicate(timeout=0.1)
                    if stdout:
                        output += f"\nStdout:\n{stdout}\n"
                    if stderr:
                        output += f"\nStderr:\n{stderr}\n"
                except:
                    pass
            
            output += f"Command: {command}\n"
            output += f"Runtime: {runtime_str}\n"
            if working_dir:
                output += f"Working directory: {working_dir}\n"
            
            return ToolResult(
                success=True,
                output=output.strip(),
                metadata={
                    'pid': process_id,
                    'running': poll_result is None,
                    'exit_code': poll_result,
                    'runtime': runtime
                }
            )
