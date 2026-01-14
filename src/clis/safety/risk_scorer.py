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
            r"^git\s+(status|log|diff|show)(\s|$)",
            r"^git\s+branch\s*$",  # List branches only
            r"^docker\s+(ps|images|inspect)\s",
        ]
        
        for pattern in readonly_patterns:
            if re.match(pattern, command, re.IGNORECASE):
                return 10  # Very low risk
        
        # Check for write operations (medium risk)
        write_patterns = [
            r"^(echo|touch|mkdir|cp|mv)\s",
            r"^git\s+(add|commit|stash)(\s|$)",
            r"^docker\s+(run|start|stop)\s",
        ]
        
        for pattern in write_patterns:
            if re.match(pattern, command, re.IGNORECASE):
                score = 50
        
        # Check for high-risk git operations (high risk)
        high_risk_git_patterns = [
            r"^git\s+push(\s|$)",  # Any git push is risky
            r"^git\s+pull(\s|$)",  # Can overwrite local changes
            r"^git\s+checkout\s",  # Can discard changes
            r"^git\s+branch\s.*(-[dD]|--delete)",  # Branch deletion
        ]
        
        for pattern in high_risk_git_patterns:
            if re.match(pattern, command, re.IGNORECASE):
                score = 70
        
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
        if "--force" in command or "-f" in command.split():
            # Force flags significantly increase risk
            score = max(score, 80)  # Ensure at least high risk
            score = min(score + 15, 100)
        
        if "-rf" in command or "-fr" in command:
            # Recursive force deletion is extremely dangerous
            score = max(score, 85)
        
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
    
    def score_tool_operation(self, tool_name: str, parameters: dict) -> int:
        """
        Calculate risk score for a tool operation.
        
        This provides tool-specific risk scoring beyond just command strings.
        
        Args:
            tool_name: Name of the tool being called
            parameters: Tool parameters
            
        Returns:
            Risk score (0-100)
        """
        # Base scores for tools
        tool_base_scores = {
            # Low risk - read-only operations
            "list_files": 10,
            "read_file": 10,
            "file_tree": 10,
            "get_file_info": 10,
            "grep": 10,
            "search_files": 10,
            "read_lints": 10,
            "git_status": 10,
            "git_log": 10,
            "git_diff": 10,
            "docker_ps": 10,
            "docker_logs": 10,
            "docker_inspect": 10,
            "docker_stats": 10,
            "system_info": 10,
            "check_command": 10,
            "get_env": 10,
            "list_processes": 10,
            "check_port": 10,
            
            # Medium risk - write/modify operations
            "write_file": 50,
            "edit_file": 50,
            "git_add": 50,
            "git_commit": 50,
            "http_request": 50,
            
            # High risk - destructive or remote operations
            "delete_file": 75,
            "git_checkout": 70,
            "git_pull": 70,
            "git_push": 70,
            "git_branch": 60,  # Varies by action
            "run_terminal_cmd": 60,  # Varies by command
        }
        
        score = tool_base_scores.get(tool_name, 50)  # Default to medium risk
        
        # Adjust based on parameters
        if tool_name == "git_push" and parameters.get("force"):
            score = 85  # Force push is very dangerous
        
        if tool_name == "git_branch":
            action = parameters.get("action", "list")
            if action == "delete":
                score = 75
            elif action in ["create", "rename"]:
                score = 50
        
        if tool_name == "delete_file":
            if parameters.get("recursive"):
                score = 85  # Recursive delete is more dangerous
            if parameters.get("force"):
                score = min(score + 10, 95)
        
        if tool_name == "run_terminal_cmd":
            command = parameters.get("command", "")
            if command:
                # Use command scoring for terminal commands
                score = self.score(command)
        
        if tool_name == "git_checkout" and parameters.get("file_path"):
            # Restoring files can discard changes
            score = 70
        
        logger.debug(f"Risk score for tool '{tool_name}' with params {parameters}: {score}")
        
        return score
