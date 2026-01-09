"""
Utility functions for tools.
"""

import shutil


def has_command(command: str) -> bool:
    """
    Check if a command is available in PATH.
    
    Args:
        command: Command name to check
        
    Returns:
        True if command is available, False otherwise
    """
    return shutil.which(command) is not None
