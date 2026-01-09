"""
Output formatter for CLIS - handles different output levels.
"""

from typing import Any, Dict, List, Optional

from clis.config import ConfigManager
from clis.output.console import Console
from clis.safety.risk_scorer import RiskLevel
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class OutputFormatter:
    """Formatter for different output levels."""

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """
        Initialize output formatter.
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config_manager = config_manager or ConfigManager()
        self.config = self.config_manager.load_base_config()
        self.console = Console(config_manager)
        self.output_level = self.config.output.level

    def show_commands(
        self,
        commands: List[str],
        explanation: str,
        risk_level: Optional[RiskLevel] = None,
    ) -> None:
        """
        Show commands to user.
        
        Args:
            commands: List of commands
            explanation: Explanation of commands
            risk_level: Risk level
        """
        if self.output_level == "minimal":
            # Just show commands
            for cmd in commands:
                print(cmd)
            return
        
        # Normal, verbose, or debug mode
        self.console.rule("Generated Commands")
        
        # Show commands with syntax highlighting
        for i, cmd in enumerate(commands, 1):
            if len(commands) > 1:
                self.console.print(f"\nCommand {i}:")
            self.console.code(cmd)
        
        # Show explanation
        if explanation:
            self.console.print(f"\n💡 {explanation}")
        
        # Show risk level
        if risk_level:
            risk_emoji = {
                "low": "🟢",
                "medium": "🟡",
                "high": "🔴",
                "critical": "⛔",
            }
            emoji = risk_emoji.get(risk_level, "")
            self.console.print(f"\n🔒 Risk Level: {emoji} {risk_level.upper()}")

    def show_skill_match(self, skill_name: str, confidence: float) -> None:
        """
        Show skill matching result.
        
        Args:
            skill_name: Matched skill name
            confidence: Confidence score
        """
        if self.output_level in ["verbose", "debug"]:
            self.console.success(f"Matched Skill: {skill_name} (confidence: {confidence:.2f})")

    def show_api_call(self, provider: str, model: str, tokens: Dict[str, int], cost: float) -> None:
        """
        Show API call information.
        
        Args:
            provider: LLM provider
            model: Model name
            tokens: Token usage dict
            cost: Estimated cost
        """
        if self.output_level in ["verbose", "debug"]:
            self.console.print("\n🤖 LLM API Call:")
            self.console.print(f"  Provider: {provider}")
            self.console.print(f"  Model: {model}")
            
            if self.config.output.show_tokens:
                input_tokens = tokens.get("input", 0)
                output_tokens = tokens.get("output", 0)
                self.console.print(f"  Tokens: {input_tokens} (input) + {output_tokens} (output)")
            
            if self.config.output.show_tokens and cost > 0:
                self.console.print(f"  Cost: ¥{cost:.4f}")

    def show_error(self, error: str) -> None:
        """
        Show error message.
        
        Args:
            error: Error message
        """
        self.console.error(error)

    def show_warning(self, warning: str) -> None:
        """
        Show warning message.
        
        Args:
            warning: Warning message
        """
        self.console.warning(warning)

    def show_info(self, info: str) -> None:
        """
        Show info message.
        
        Args:
            info: Info message
        """
        if self.output_level != "minimal":
            self.console.info(info)

    def show_debug(self, debug: str) -> None:
        """
        Show debug message.
        
        Args:
            debug: Debug message
        """
        if self.output_level == "debug":
            self.console.print(f"[DEBUG] {debug}", style="dim")

    def show_skill_list(self, skills: List[Dict[str, Any]]) -> None:
        """
        Show list of skills.
        
        Args:
            skills: List of skill dicts
        """
        if not skills:
            self.console.warning("No skills found")
            return
        
        headers = ["Name", "Description"]
        rows = [[skill["name"], skill["description"][:60] + "..."] for skill in skills]
        
        self.console.table(headers, rows)
        self.console.print(f"\nTotal: {len(skills)} skills")
