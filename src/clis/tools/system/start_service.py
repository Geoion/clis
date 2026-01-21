"""
启动后台服务工具 - 智能启动并验证服务
"""

import subprocess
import time
import socket
from typing import Any, Dict, Optional

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class StartServiceTool(Tool):
    """启动后台服务并验证可用性"""
    
    @property
    def name(self) -> str:
        return "start_service"
    
    @property
    def description(self) -> str:
        return "启动后台服务（如 web server）并验证端口可用。自动检查端口冲突，等待服务就绪。"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "启动服务的命令（如 'python3 app.py'）"
                },
                "port": {
                    "type": "integer",
                    "description": "服务监听的端口号"
                },
                "wait_seconds": {
                    "type": "integer",
                    "default": 5,
                    "description": "等待服务启动的最大秒数"
                },
                "working_directory": {
                    "type": "string",
                    "description": "工作目录（可选）"
                }
            },
            "required": ["command", "port"]
        }
    
    @property
    def is_readonly(self) -> bool:
        return False
    
    @property
    def risk_score(self) -> int:
        return 60  # 中高风险（启动进程）
    
    @property
    def requires_confirmation(self) -> bool:
        return True
    
    def execute(
        self,
        command: str,
        port: int,
        wait_seconds: int = 5,
        working_directory: Optional[str] = None
    ) -> ToolResult:
        """执行服务启动"""
        try:
            # 1. 检查端口是否被占用
            if self._is_port_open(port):
                return ToolResult(
                    success=False,
                    output="",
                    error=f"""端口 {port} 已被占用！

💡 解决方案:
1. 使用其他端口（推荐）: 修改命令中的端口为 {port + 1}
2. 查看占用进程: lsof -i :{port}
3. 停止占用进程: lsof -ti:{port} | xargs kill

⚠️ 请选择一个方案后重试。"""
                )
            
            # 2. 启动进程
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
                
                # 3. 等待端口可用
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
                        output=f"""✅ 服务已启动并就绪！

PID: {proc.pid}
端口: {port}
状态: 端口已打开，服务可访问

可以使用以下命令测试:
  curl http://localhost:{port}/
  
停止服务:
  kill {proc.pid}
""",
                        metadata={
                            "pid": proc.pid,
                            "port": port,
                            "ready": True
                        }
                    )
                else:
                    # 服务启动但端口未就绪
                    return ToolResult(
                        success=False,
                        output=f"服务已启动 (PID: {proc.pid})，但端口 {port} 未在 {wait_seconds} 秒内就绪",
                        error="服务可能启动失败，请检查日志",
                        metadata={"pid": proc.pid, "port": port, "ready": False}
                    )
            
            finally:
                if working_directory:
                    os.chdir(old_dir)
        
        except Exception as e:
            logger.error(f"启动服务失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"启动服务失败: {str(e)}"
            )
    
    def _is_port_open(self, port: int) -> bool:
        """检查端口是否已打开"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        try:
            result = sock.connect_ex(('localhost', port))
            return result == 0
        finally:
            sock.close()
