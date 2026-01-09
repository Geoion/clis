"""
Logging utilities for CLIS.
"""

import logging
from pathlib import Path
from typing import Optional

from clis.utils.platform import ensure_dir, get_logs_dir


def setup_logger(
    name: str = "clis",
    level: int = logging.INFO,
    log_file: Optional[Path] = None,
) -> logging.Logger:
    """
    Set up a logger with file and console handlers.
    
    Args:
        name: Logger name
        level: Logging level
        log_file: Path to log file (default: ~/.clis/logs/clis.log)
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)  # Only warnings and errors to console
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler
    if log_file is None:
        log_file = get_logs_dir() / "clis.log"
    
    ensure_dir(log_file.parent)
    
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str = "clis") -> logging.Logger:
    """
    Get or create a logger.
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logger(name)
    return logger
