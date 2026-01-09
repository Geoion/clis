"""
Blacklist checker for dangerous commands.
"""

import re
from typing import List, Optional, Tuple

from clis.config import ConfigManager
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class BlacklistChecker:
    """Checker for blacklisted commands."""

    # Built-in dangerous patterns
    BUILTIN_PATTERNS = [
        r"rm\s+-rf\s+/\s*$",
        r"rm\s+-rf\s+/\*",
        r"rm\s+-rf\s+~/\*",
        r"mkfs",
        r"dd\s+if=/dev/(zero|random)",
        r">\s*/dev/(sda|hda)",
        r"chmod\s+-R\s+777\s+/",
        r":\(\)\{\s*:\|:&\s*\};:",  # Fork bomb
    ]

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """
        Initialize blacklist checker.
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config_manager = config_manager or ConfigManager()
        self.patterns: List[str] = []
        self._load_patterns()

    def _load_patterns(self) -> None:
        """Load blacklist patterns from configuration."""
        safety_config = self.config_manager.load_safety_config()
        
        if not safety_config.blacklist.enabled:
            logger.info("Blacklist checking is disabled")
            return
        
        # Add built-in patterns
        self.patterns.extend(self.BUILTIN_PATTERNS)
        
        # Add configured patterns
        self.patterns.extend(safety_config.blacklist.patterns)
        
        # Add custom patterns
        self.patterns.extend(safety_config.blacklist.custom)
        
        logger.debug(f"Loaded {len(self.patterns)} blacklist patterns")

    def check(self, command: str) -> Tuple[bool, Optional[str]]:
        """
        Check if a command matches blacklist.
        
        Args:
            command: Command to check
            
        Returns:
            Tuple of (is_blocked, matched_pattern)
        """
        for pattern in self.patterns:
            try:
                if re.search(pattern, command, re.IGNORECASE):
                    logger.warning(f"Command blocked by blacklist: {command}")
                    logger.debug(f"Matched pattern: {pattern}")
                    return (True, pattern)
            except re.error as e:
                logger.error(f"Invalid regex pattern '{pattern}': {e}")
        
        return (False, None)

    def is_sudo_command(self, command: str) -> bool:
        """
        Check if a command uses sudo.
        
        Args:
            command: Command to check
            
        Returns:
            True if command uses sudo
        """
        return command.strip().startswith("sudo ")
