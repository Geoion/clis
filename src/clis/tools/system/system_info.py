"""
System info tool - get system information.
"""

import platform
import sys
from typing import Any, Dict

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class SystemInfoTool(Tool):
    """Get system information."""
    
    @property
    def name(self) -> str:
        return "system_info"
    
    @property
    def description(self) -> str:
        return "Get system information including OS, CPU, memory, and disk space."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "detailed": {
                    "type": "boolean",
                    "default": False,
                    "description": "Include detailed information"
                }
            }
        }
    
    def execute(self, detailed: bool = False) -> ToolResult:
        """Execute system info."""
        try:
            info = []
            
            # Basic system info
            info.append(f"Operating System: {platform.system()} {platform.release()}")
            info.append(f"Platform: {platform.platform()}")
            info.append(f"Architecture: {platform.machine()}")
            info.append(f"Processor: {platform.processor() or 'N/A'}")
            info.append(f"Python: {sys.version.split()[0]}")
            
            # Memory info (cross-platform using psutil)
            try:
                import psutil
                mem = psutil.virtual_memory()
                info.append(f"\nMemory:")
                info.append(f"  Total: {mem.total / (1024**3):.2f} GB")
                info.append(f"  Available: {mem.available / (1024**3):.2f} GB")
                info.append(f"  Used: {mem.percent}%")
                
                # Disk info
                disk = psutil.disk_usage('/')
                info.append(f"\nDisk (/):")
                info.append(f"  Total: {disk.total / (1024**3):.2f} GB")
                info.append(f"  Free: {disk.free / (1024**3):.2f} GB")
                info.append(f"  Used: {disk.percent}%")
                
                if detailed:
                    # CPU info
                    info.append(f"\nCPU:")
                    info.append(f"  Physical cores: {psutil.cpu_count(logical=False)}")
                    info.append(f"  Logical cores: {psutil.cpu_count(logical=True)}")
                    info.append(f"  Usage: {psutil.cpu_percent(interval=1)}%")
            
            except ImportError:
                info.append("\n(Install psutil for detailed memory/disk info: pip install psutil)")
            
            output = "\n".join(info)
            return ToolResult(success=True, output=output)
            
        except Exception as e:
            logger.error(f"Error getting system info: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error getting system info: {str(e)}"
            )
