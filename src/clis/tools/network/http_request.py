"""
HTTP request tool - make HTTP requests.
"""

from typing import Any, Dict, Optional

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class HttpRequestTool(Tool):
    """Make HTTP requests."""
    
    @property
    def name(self) -> str:
        return "http_request"
    
    @property
    def description(self) -> str:
        return "Make HTTP requests (GET, POST, etc.). Useful for API testing and health checks."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to request"
                },
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"],
                    "default": "GET",
                    "description": "HTTP method"
                },
                "headers": {
                    "type": "object",
                    "description": "HTTP headers (key-value pairs)"
                },
                "data": {
                    "type": "string",
                    "description": "Request body (for POST/PUT)"
                },
                "timeout": {
                    "type": "integer",
                    "default": 30,
                    "description": "Request timeout in seconds"
                }
            },
            "required": ["url"]
        }
    
    def execute(self, url: str, method: str = "GET", headers: Optional[Dict] = None,
                data: Optional[str] = None, timeout: int = 30) -> ToolResult:
        """Execute HTTP request."""
        try:
            import requests
            
            # Prepare headers
            req_headers = headers or {}
            
            # Make request
            response = requests.request(
                method=method,
                url=url,
                headers=req_headers,
                data=data,
                timeout=timeout
            )
            
            # Format output
            output = f"Status: {response.status_code} {response.reason}\n"
            output += f"\nHeaders:\n"
            for k, v in list(response.headers.items())[:10]:  # Limit headers
                output += f"  {k}: {v}\n"
            
            output += f"\nBody:\n"
            body_text = response.text[:1000]  # Limit body size
            output += body_text
            
            if len(response.text) > 1000:
                output += "\n... (truncated)"
            
            return ToolResult(
                success=response.status_code < 400,
                output=output,
                metadata={
                    "status_code": response.status_code,
                    "size": len(response.text)
                }
            )
            
        except ImportError:
            return ToolResult(
                success=False,
                output="",
                error="requests library not installed. Run: pip install requests"
            )
        except Exception as e:
            logger.error(f"Error making HTTP request: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error making HTTP request: {str(e)}"
            )
