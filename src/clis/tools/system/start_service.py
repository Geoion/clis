"""
Start background service tool - Intelligently start and verify services
"""

import subprocess
import time
import socket
from typing import Any, Dict, Optional

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class StartServiceTool(Tool):
    """Start background service and verify availability"""
    
    @property
    def name(self) -> str:
        return "start_service"
    
    @property
    def description(self) -> str:
        return "Start a background service (e.g., web server) and verify port availability. Automatically checks for port conflicts and waits for service readiness."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Command to start the service (e.g., 'python3 app.py')"
                },
                "port": {
                    "type": "integer",
                    "description": "Port number the service listens on"
                },
                "wait_seconds": {
                    "type": "integer",
                    "default": 5,
                    "description": "Maximum seconds to wait for service startup"
                },
                "working_directory": {
                    "type": "string",
                    "description": "Working directory (optional)"
                },
                "auto_find_port": {
                    "type": "boolean",
                    "default": False,
                    "description": "Automatically find available port if specified port is in use"
                }
            },
            "required": ["command", "port"]
        }
    
    @property
    def is_readonly(self) -> bool:
        return False
    
    @property
    def risk_score(self) -> int:
        return 60  # Medium-high risk (starting process)
    
    @property
    def requires_confirmation(self) -> bool:
        return True
    
    def execute(
        self,
        command: str,
        port: int,
        wait_seconds: int = 5,
        working_directory: Optional[str] = None,
        auto_find_port: bool = False
    ) -> ToolResult:
        """Execute service startup"""
        try:
            # 1. Check if port is already in use
            original_port = port
            if self._is_port_open(port):
                if auto_find_port:
                    # Try to find an available port
                    port = self._find_available_port(port)
                    if port is None:
                        return ToolResult(
                            success=False,
                            output="",
                            error=f"Port {original_port} is in use and no available port found in range {original_port}-{original_port+10}"
                        )
                    logger.info(f"Port {original_port} in use, using {port} instead")
                    # Update command with new port
                    command = command.replace(f":{original_port}", f":{port}").replace(f"={original_port}", f"={port}")
                else:
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"""Port {port} is already in use!

💡 Solutions:
1. Use a different port (recommended): Change the port in the command to {port + 1}
2. Check which process is using it: lsof -i :{port}
3. Stop the process using the port: lsof -ti:{port} | xargs kill
4. Enable auto_find_port parameter to automatically find available port

⚠️ Please choose a solution and try again."""
                    )
            
            # 2. Start the process
            import os
            if working_directory:
                old_dir = os.getcwd()
                os.chdir(working_directory)
            
            try:
                proc = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True
                )
                
                # 3. Wait for port to become available
                start_time = time.time()
                service_ready = False
                
                while time.time() - start_time < wait_seconds:
                    if self._is_port_open(port):
                        service_ready = True
                        break
                    time.sleep(0.5)
                
                if service_ready:
                    return ToolResult(
                        success=True,
                        output=f"""✅ Service started and ready!

PID: {proc.pid}
Port: {port}
Status: Port is open, service is accessible

You can test with:
  curl http://localhost:{port}/
  
To stop the service:
  kill {proc.pid}
""",
                        metadata={
                            "pid": proc.pid,
                            "port": port,
                            "ready": True
                        }
                    )
                else:
                    # Service started but port not ready
                    return ToolResult(
                        success=False,
                        output=f"Service started (PID: {proc.pid}), but port {port} did not become ready within {wait_seconds} seconds",
                        error="Service may have failed to start, please check logs",
                        metadata={"pid": proc.pid, "port": port, "ready": False}
                    )
            
            finally:
                if working_directory:
                    os.chdir(old_dir)
        
        except Exception as e:
            logger.error(f"Failed to start service: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to start service: {str(e)}"
            )
    
    def _find_available_port(self, start_port: int, max_attempts: int = 10) -> Optional[int]:
        """
        Find an available port starting from start_port.
        
        Args:
            start_port: Starting port number
            max_attempts: Maximum number of ports to try
            
        Returns:
            Available port number or None
        """
        for offset in range(1, max_attempts + 1):
            port = start_port + offset
            if not self._is_port_open(port):
                return port
        return None
    
    def _is_port_open(self, port: int) -> bool:
        """Check if port is open"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        try:
            result = sock.connect_ex(('localhost', port))
            return result == 0
        finally:
            sock.close()
