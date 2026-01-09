"""
Risk scorer for commands.
"""

import re
from typing import Literal, Optional

from clis.config import ConfigManager
from clis.utils.logger import get_logger

logger = get_logger(__name__)

RiskLevel = Literal["low", "medium", "high", "critical"]


class RiskScorer:
    """Scorer for command risk assessment."""

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """
        Initialize risk scorer.
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config_manager = config_manager or ConfigManager()
        self.config = self.config_manager.load_safety_config()

    def score(self, command: str) -> int:
        """
        Calculate risk score for a command.
        
        Args:
            command: Command to score
            
        Returns:
            Risk score (0-100)
        """
        score = 0
        
        # Check for read-only operations (low risk)
        readonly_patterns = [
            r"^(ls|cat|less|more|head|tail|grep|find|which|whereis)\s",
            r"^git\s+(status|log|diff|show|branch)\s",
            r"^docker\s+(ps|images|inspect)\s",
        ]
        
        for pattern in readonly_patterns:
            if re.match(pattern, command, re.IGNORECASE):
                return 10  # Very low risk
        
        # Check for write operations (medium risk)
        write_patterns = [
            r"^(echo|touch|mkdir|cp|mv)\s",
            r"^git\s+(add|commit|stash)\s",
            r"^docker\s+(run|start|stop)\s",
        ]
        
        for pattern in write_patterns:
            if re.match(pattern, command, re.IGNORECASE):
                score = 50
        
        # Check for delete/modify operations (high risk)
        delete_patterns = [
            r"\brm\b",
            r"\brmdir\b",
            r"^git\s+(reset|clean)\s",
            r"^docker\s+(rm|rmi|prune)\s",
        ]
        
        for pattern in delete_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                score = 75
        
        # Check for system-level operations (critical risk)
        system_patterns = [
            r"^sudo\s",
            r"\bchmod\b",
            r"\bchown\b",
            r"\bkill\b",
            r"\bpkill\b",
            r"^(apt|yum|dnf|brew|choco)\s+(install|remove|purge)",
        ]
        
        for pattern in system_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                score = 95
        
        # Additional risk factors
        if "-rf" in command or "--force" in command:
            score += 10
        
        if "|" in command or ">" in command or ">>" in command:
            score += 5
        
        # Cap at 100
        score = min(score, 100)
        
        logger.debug(f"Risk score for '{command}': {score}")
        
        return score

    def get_risk_level(self, score: int) -> RiskLevel:
        """
        Get risk level from score.
        
        Args:
            score: Risk score
            
        Returns:
            Risk level
        """
        thresholds = self.config.risk.thresholds
        
        if score <= thresholds.low:
            return "low"
        elif score <= thresholds.medium:
            return "medium"
        elif score <= thresholds.high:
            return "high"
        else:
            return "critical"

    def get_action(self, risk_level: RiskLevel) -> str:
        """
        Get action for risk level.
        
        Args:
            risk_level: Risk level
            
        Returns:
            Action (execute, confirm, dry_run, block)
        """
        actions = self.config.risk.actions
        
        if risk_level == "low":
            return actions.low
        elif risk_level == "medium":
            return actions.medium
        elif risk_level == "high":
            return actions.high
        else:
            return actions.critical
