"""
Unified error handling for CLIS.

Provides consistent error handling, logging, and user feedback across the application.
"""

import sys
import traceback
from functools import wraps
from typing import Callable, Any, Optional

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
