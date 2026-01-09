"""
Platform detection and path handling utilities.
"""

import os
import platform
import sys
from pathlib import Path
from typing import Literal

# Platform types
PlatformType = Literal["windows", "macos", "linux"]
ShellType = Literal["powershell", "cmd", "bash", "zsh", "sh"]


def get_platform() -> PlatformType:
    """
    Detect the current operating system.
    
    Returns:
        Platform type: "windows", "macos", or "linux"
    """
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    elif system == "darwin":
        return "macos"
    else:
        return "linux"


def get_shell() -> ShellType:
    """
    Detect the current shell type.
    
    Returns:
        Shell type: "powershell", "cmd", "bash", "zsh", or "sh"
    """
    # Check SHELL environment variable (Unix-like systems)
    shell_env = os.environ.get("SHELL", "")
    if shell_env:
        shell_name = Path(shell_env).name
        if shell_name in ["bash", "zsh", "sh"]:
            return shell_name  # type: ignore
    
    # Windows detection
    if get_platform() == "windows":
        # Check if running in PowerShell
        if os.environ.get("PSModulePath"):
            return "powershell"
        return "cmd"
    
    # Default to bash for Unix-like systems
    return "bash"


def get_home_dir() -> Path:
    """
    Get the user's home directory.
    
    Returns:
        Path to home directory
    """
    return Path.home()


def get_clis_dir() -> Path:
    """
    Get the CLIS configuration directory (~/.clis).
    
    Returns:
        Path to CLIS directory
    """
    return get_home_dir() / ".clis"


def get_config_dir() -> Path:
    """
    Get the CLIS configuration directory (~/.clis/config).
    
    Returns:
        Path to config directory
    """
    return get_clis_dir() / "config"


def get_skills_dir() -> Path:
    """
    Get the CLIS skills directory (~/.clis/skills).
    
    Returns:
        Path to skills directory
    """
    return get_clis_dir() / "skills"


def get_cache_dir() -> Path:
    """
    Get the CLIS cache directory (~/.clis/cache).
    
    Returns:
        Path to cache directory
    """
    return get_clis_dir() / "cache"


def get_logs_dir() -> Path:
    """
    Get the CLIS logs directory (~/.clis/logs).
    
    Returns:
        Path to logs directory
    """
    return get_clis_dir() / "logs"


def ensure_dir(path: Path) -> None:
    """
    Ensure a directory exists, create it if it doesn't.
    
    Args:
        path: Directory path to ensure
    """
    path.mkdir(parents=True, exist_ok=True)


def normalize_path(path: str) -> str:
    """
    Normalize a path for the current platform.
    
    Args:
        path: Path string to normalize
        
    Returns:
        Normalized path string
    """
    # Expand user home directory
    path = os.path.expanduser(path)
    # Expand environment variables
    path = os.path.expandvars(path)
    # Normalize path separators
    return os.path.normpath(path)


def get_path_separator() -> str:
    """
    Get the path separator for the current platform.
    
    Returns:
        Path separator ("/" or "\\")
    """
    return os.sep


def get_python_executable() -> str:
    """
    Get the path to the current Python executable.
    
    Returns:
        Path to Python executable
    """
    return sys.executable


def is_windows() -> bool:
    """Check if running on Windows."""
    return get_platform() == "windows"


def is_macos() -> bool:
    """Check if running on macOS."""
    return get_platform() == "macos"


def is_linux() -> bool:
    """Check if running on Linux."""
    return get_platform() == "linux"
