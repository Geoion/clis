"""
Unified error handling for CLIS.

Provides consistent error handling, logging, and user feedback across the application.
"""

import sys
import traceback
from functools import wraps
from typing import Callable, Any, Optional, List, Dict

import click

from clis.utils.logger import get_logger

logger = get_logger(__name__)


class CLISError(Exception):
    """Base exception for CLIS errors."""
    
    def __init__(self, message: str, exit_code: int = 1):
        self.message = message
        self.exit_code = exit_code
        super().__init__(message)


class ConfigurationError(CLISError):
    """Configuration-related errors."""
    pass


class ToolExecutionError(CLISError):
    """Tool execution errors."""
    pass


class SkillError(CLISError):
    """Skill-related errors."""
    pass


class ValidationError(CLISError):
    """Validation errors."""
    pass


def handle_cli_error(show_traceback: bool = False):
    """
    Decorator for unified CLI error handling.
    
    Args:
        show_traceback: Whether to show full traceback on error
        
    Usage:
        @handle_cli_error(show_traceback=False)
        def my_command():
            # ... code that might raise errors
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            
            except KeyboardInterrupt:
                click.echo("\n\n⚠️  Interrupted by user", err=True)
                logger.info("Command interrupted by user")
                sys.exit(130)
            
            except CLISError as e:
                # Known CLIS errors - show clean message
                click.echo(f"❌ Error: {e.message}", err=True)
                logger.error(f"{type(e).__name__}: {e.message}")
                sys.exit(e.exit_code)
            
            except FileNotFoundError as e:
                click.echo(f"❌ File not found: {e}", err=True)
                logger.error(f"FileNotFoundError: {e}")
                sys.exit(1)
            
            except PermissionError as e:
                click.echo(f"❌ Permission denied: {e}", err=True)
                logger.error(f"PermissionError: {e}")
                sys.exit(1)
            
            except Exception as e:
                # Unknown errors - show detailed message
                click.echo(f"❌ Unexpected error: {str(e)}", err=True)
                logger.error(f"Unexpected error: {str(e)}")
                
                if show_traceback:
                    click.echo("\nTraceback:", err=True)
                    traceback.print_exc()
                else:
                    click.echo("💡 Run with --debug to see full traceback", err=True)
                
                sys.exit(1)
        
        return wrapper
    return decorator


def safe_execute(
    func: Callable,
    error_message: str = "Operation failed",
    default_return: Any = None,
    log_error: bool = True
) -> Any:
    """
    Safely execute a function with error handling.
    
    Args:
        func: Function to execute
        error_message: Error message to show on failure
        default_return: Value to return on error
        log_error: Whether to log the error
        
    Returns:
        Function result or default_return on error
        
    Usage:
        result = safe_execute(
            lambda: dangerous_operation(),
            error_message="Failed to execute operation",
            default_return=None
        )
    """
    try:
        return func()
    except Exception as e:
        if log_error:
            logger.error(f"{error_message}: {e}")
        return default_return


def validate_config_exists(config_manager) -> None:
    """
    Validate that configuration exists.
    
    Args:
        config_manager: ConfigManager instance
        
    Raises:
        ConfigurationError: If configuration doesn't exist
    """
    if not config_manager.config_exists():
        raise ConfigurationError(
            "Configuration not found. Please run 'clis init' first."
        )


def validate_file_exists(path: str) -> None:
    """
    Validate that a file exists.
    
    Args:
        path: File path to check
        
    Raises:
        FileNotFoundError: If file doesn't exist
    """
    from pathlib import Path
    
    path_obj = Path(path).expanduser()
    if not path_obj.exists():
        raise FileNotFoundError(f"File does not exist: {path}")
    
    if not path_obj.is_file():
        raise FileNotFoundError(f"Path is not a file: {path}")


def validate_directory_exists(path: str) -> None:
    """
    Validate that a directory exists.
    
    Args:
        path: Directory path to check
        
    Raises:
        FileNotFoundError: If directory doesn't exist
    """
    from pathlib import Path
    
    path_obj = Path(path).expanduser()
    if not path_obj.exists():
        raise FileNotFoundError(f"Directory does not exist: {path}")
    
    if not path_obj.is_dir():
        raise FileNotFoundError(f"Path is not a directory: {path}")


def format_error_message(error: Exception, context: Optional[str] = None) -> str:
    """
    Format an error message for display.
    
    Args:
        error: Exception object
        context: Optional context information
        
    Returns:
        Formatted error message
    """
    message = str(error)
    
    if context:
        return f"{context}: {message}"
    
    return message


def handle_tool_error(error: Exception, tool_name: str) -> str:
    """
    Handle tool execution errors.
    
    Args:
        error: Exception raised during tool execution
        tool_name: Name of the tool that failed
        
    Returns:
        User-friendly error message
    """
    logger.error(f"Tool '{tool_name}' failed: {error}")
    
    if isinstance(error, PermissionError):
        return f"Permission denied while executing {tool_name}. Check file permissions."
    elif isinstance(error, FileNotFoundError):
        return f"File not found in {tool_name}: {error}"
    elif isinstance(error, TimeoutError):
        return f"Tool {tool_name} timed out. Try increasing timeout or simplifying the operation."
    else:
        return f"Error in {tool_name}: {str(error)}"


class ErrorMessageBuilder:
    """Build user-friendly error messages."""
    
    # Common error resolution suggestions
    ERROR_SUGGESTIONS = {
        "ModuleNotFoundError": [
            "Check if required dependencies are installed",
            "Run: pip install -e .",
            "Check if Python environment is correct"
        ],
        "FileNotFoundError": [
            "Confirm file path is correct",
            "Check if file exists",
            "Try using absolute path"
        ],
        "PermissionError": [
            "Check file/directory permissions",
            "Try using sudo (if needed)",
            "Confirm current user has access permissions"
        ],
        "ConnectionError": [
            "Check network connection",
            "Confirm API endpoint is accessible",
            "Check firewall settings"
        ],
        "TimeoutError": [
            "Increase timeout duration",
            "Simplify operation",
            "Check network connection"
        ],
        "JSONDecodeError": [
            "Check if JSON format is correct",
            "Confirm file encoding is UTF-8",
            "Use JSON validation tool to check"
        ],
        "KeyError": [
            "Check if configuration file is complete",
            "Run 'clis init' to reinitialize",
            "Check documentation for required configuration items"
        ],
        "ValueError": [
            "Check if parameter values are valid",
            "Check help documentation for parameter format",
            "Try using default values"
        ],
    }
    
    @classmethod
    def build(cls, error: Exception, context: Optional[str] = None) -> str:
        """
        Build detailed error message.
        
        Args:
            error: Exception object
            context: Context information
            
        Returns:
            Formatted error message
        """
        error_type = type(error).__name__
        error_message = str(error)
        
        # Basic error information
        output = f"""
╭{'─' * 68}╮
│ ❌ Error: {error_type:<60} │
╰{'─' * 68}╯

📝 Error Message:
   {error_message}
"""
        
        # Add context
        if context:
            output += f"""
📍 Location:
   {context}
"""
        
        # Add suggestions
        suggestions = cls.ERROR_SUGGESTIONS.get(error_type, [])
        if suggestions:
            output += f"""
💡 Suggestions:
"""
            for i, suggestion in enumerate(suggestions, 1):
                output += f"   {i}. {suggestion}\n"
        
        # Add help links
        output += f"""
📚 Get Help:
   - View documentation: https://github.com/eskiyin/clis#readme
   - Run diagnostics: clis doctor
   - View detailed logs: ~/.clis/logs/clis.log
"""
        
        return output
    
    @classmethod
    def build_tool_error(cls, tool_name: str, error: Exception, params: dict) -> str:
        """
        Build tool error message.
        
        Args:
            tool_name: Tool name
            error: Exception object
            params: Tool parameters
            
        Returns:
            Formatted error message
        """
        error_type = type(error).__name__
        
        output = f"""
╭{'─' * 68}╮
│ ❌ Tool Execution Failed: {tool_name:<48} │
╰{'─' * 68}╯

📝 Error Type: {error_type}
📝 Error Message: {str(error)}

🔧 Call Parameters:
"""
        for key, value in params.items():
            output += f"   - {key}: {value}\n"
        
        # Tool-specific suggestions
        tool_suggestions = cls._get_tool_suggestions(tool_name, error_type, params)
        if tool_suggestions:
            output += f"""
💡 Suggestions:
"""
            for i, suggestion in enumerate(tool_suggestions, 1):
                output += f"   {i}. {suggestion}\n"
        
        output += f"""
📚 View Tool Documentation:
   clis run "help with {tool_name} tool"
   Or view: docs/TOOL_PARAMETERS_GUIDE.md
"""
        
        return output
    
    @classmethod
    def _get_tool_suggestions(cls, tool_name: str, error_type: str, params: dict) -> List[str]:
        """Get tool-specific suggestions."""
        suggestions = []
        
        # File-related tools
        if 'file' in tool_name or 'edit' in tool_name:
            if error_type == "FileNotFoundError":
                suggestions.append(f"Confirm file path is correct: {params.get('path', params.get('file', 'N/A'))}")
                suggestions.append("Use 'clis run \"list files\"' to see available files")
            elif error_type == "PermissionError":
                suggestions.append("Check file permissions")
                suggestions.append("Confirm file is not read-only")
        
        # Git-related tools
        elif 'git' in tool_name:
            if "not a git repository" in str(params):
                suggestions.append("Confirm current directory is a Git repository")
                suggestions.append("Run 'git init' to initialize repository")
            elif error_type == "subprocess":
                suggestions.append("Confirm git is installed")
                suggestions.append("Check git configuration")
        
        # Docker-related tools
        elif 'docker' in tool_name:
            suggestions.append("Confirm Docker is running")
            suggestions.append("Run 'docker ps' to test Docker connection")
            suggestions.append("Check if Docker Desktop is started")
        
        # General suggestions
        if not suggestions:
            suggestions = cls.ERROR_SUGGESTIONS.get(error_type, [
                "Check if parameters are correct",
                "View tool documentation",
                "Try using --debug to see detailed information"
            ])
        
        return suggestions
