"""
Safety middleware for CLIS - coordinates all safety checks.
"""

from typing import List, Optional, Tuple

from clis.config import ConfigManager
from clis.safety.blacklist import BlacklistChecker
from clis.safety.risk_scorer import RiskLevel, RiskScorer
from clis.skills.parser import Skill
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class SafetyMiddleware:
    """Middleware for safety checks."""

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """
        Initialize safety middleware.
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config_manager = config_manager or ConfigManager()
        self.config = self.config_manager.load_safety_config()
        self.blacklist = BlacklistChecker(config_manager)
        self.risk_scorer = RiskScorer(config_manager)

    def check_commands(
        self,
        commands: List[str],
        skill: Optional[Skill] = None,
    ) -> Tuple[bool, str, Optional[RiskLevel]]:
        """
        Check commands for safety.
        
        Args:
            commands: List of commands to check
            skill: Associated skill (for skill-specific rules)
            
        Returns:
            Tuple of (is_safe, message, risk_level)
        """
        if not commands:
            return (True, "No commands to check", None)
        
        max_risk_score = 0
        max_risk_level: Optional[RiskLevel] = None
        
        for command in commands:
            # Check blacklist
            is_blocked, pattern = self.blacklist.check(command)
            if is_blocked:
                return (
                    False,
                    f"Command blocked by blacklist: {command}\nMatched pattern: {pattern}",
                    "critical",
                )
            
            # Check sudo
            if self.blacklist.is_sudo_command(command):
                if not self.config.sudo.allowed:
                    return (
                        False,
                        f"Sudo commands are not allowed: {command}",
                        "critical",
                    )
                
                if self.config.sudo.require_skill_permission and skill:
                    # Check if skill allows sudo (would need to add this to Skill model)
                    pass
            
            # Calculate risk score
            risk_score = self.risk_scorer.score(command)
            if risk_score > max_risk_score:
                max_risk_score = risk_score
                max_risk_level = self.risk_scorer.get_risk_level(risk_score)
        
        # Check skill-specific safety rules
        if skill and skill.safety_rules:
            for rule in skill.safety_rules:
                if self._check_safety_rule(commands, rule):
                    return (
                        False,
                        f"Command violates skill safety rule: {rule}",
                        "high",
                    )
        
        return (True, "Safety checks passed", max_risk_level)

    def should_dry_run(self, risk_level: Optional[RiskLevel], skill: Optional[Skill] = None) -> bool:
        """
        Determine if dry-run is required.
        
        Args:
            risk_level: Risk level of commands
            skill: Associated skill
            
        Returns:
            True if dry-run is required
        """
        # Check if dry-run is globally enabled
        if not self.config.dry_run.enabled:
            return False
        
        # Check skill-specific dry-run setting
        if skill and skill.dry_run_mode:
            return True
        
        # Check risk level
        if risk_level in ["high", "critical"]:
            return True
        
        return False

    def get_required_action(self, risk_level: Optional[RiskLevel]) -> str:
        """
        Get required action for risk level.
        
        Args:
            risk_level: Risk level
            
        Returns:
            Action (execute, confirm, dry_run, block)
        """
        if risk_level is None:
            return "execute"
        
        return self.risk_scorer.get_action(risk_level)

    def _check_safety_rule(self, commands: List[str], rule: str) -> bool:
        """
        Check if commands violate a safety rule.
        
        Args:
            commands: List of commands
            rule: Safety rule to check
            
        Returns:
            True if rule is violated
        """
        # Parse rule format: "Forbid: pattern" or "Require confirmation: pattern"
        if rule.startswith("Forbid:"):
            pattern = rule.split(":", 1)[1].strip()
            for command in commands:
                if pattern.lower() in command.lower():
                    logger.warning(f"Command violates forbid rule: {command}")
                    return True
        
        return False
