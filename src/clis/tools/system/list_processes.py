"""
List processes tool - list running processes.
"""

from typing import Any, Dict, Optional

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class ListProcessesTool(Tool):
    """List running processes."""
    
    @property
    def name(self) -> str:
        return "list_processes"
    
    @property
    def description(self) -> str:
        return "List running processes, optionally filtered by name."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "filter": {
                    "type": "string",
                    "description": "Filter processes by name (substring match)"
                },
                "sort_by": {
                    "type": "string",
                    "enum": ["cpu", "memory", "name"],
                    "default": "cpu",
                    "description": "Sort processes by"
                },
                "limit": {
                    "type": "integer",
                    "default": 20,
                    "description": "Maximum number of processes to show"
                }
            }
        }
    
    def execute(self, filter: Optional[str] = None, sort_by: str = "cpu",
                limit: int = 20) -> ToolResult:
        """Execute list processes."""
        try:
            import psutil
            
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    pinfo = proc.info
                    if filter and filter.lower() not in pinfo['name'].lower():
                        continue
                    processes.append(pinfo)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Sort processes
            if sort_by == "cpu":
                processes.sort(key=lambda p: p['cpu_percent'], reverse=True)
            elif sort_by == "memory":
                processes.sort(key=lambda p: p['memory_percent'], reverse=True)
            else:  # name
                processes.sort(key=lambda p: p['name'].lower())
            
            # Limit results
            processes = processes[:limit]
            
            # Format output
            output = f"{'PID':<10} {'Name':<30} {'CPU%':<10} {'Memory%':<10}\n"
            output += "-" * 60 + "\n"
            
            for proc in processes:
                output += f"{proc['pid']:<10} {proc['name']:<30} {proc['cpu_percent']:<10.1f} {proc['memory_percent']:<10.2f}\n"
            
            return ToolResult(
                success=True,
                output=output,
                metadata={"count": len(processes)}
            )
        
        except ImportError:
            return ToolResult(
                success=False,
                output="",
                error="psutil library not installed. Run: pip install psutil"
            )
        except Exception as e:
            logger.error(f"Error listing processes: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error listing processes: {str(e)}"
            )
