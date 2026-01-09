"""
Command executor for CLIS.
"""

import subprocess
import time
from typing import List, Optional, Tuple

from clis.config import ConfigManager
from clis.output.console import Console
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class CommandExecutor:
    """Executor for running commands."""

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """
        Initialize command executor.
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config_manager = config_manager or ConfigManager()
        self.config = self.config_manager.load_base_config()
        self.safety_config = self.config_manager.load_safety_config()
        self.console = Console(config_manager)

    def execute(
        self,
        commands: List[str],
        require_confirmation: bool = True,
    ) -> Tuple[bool, str]:
        """
        Execute commands.
        
        Args:
            commands: List of commands to execute
            require_confirmation: Whether to require user confirmation
            
        Returns:
            Tuple of (success, output)
        """
        if not commands:
            return (False, "No commands to execute")
        
        # Ask for confirmation if required
        if require_confirmation:
            if not self._confirm_execution():
                logger.info("Execution cancelled by user")
                return (False, "Execution cancelled")
        
        # Execute commands
        all_output = []
        start_time = time.time()
        
        for i, command in enumerate(commands, 1):
            if len(commands) > 1:
                self.console.info(f"Executing command {i}/{len(commands)}...")
            
            success, output = self._execute_single(command)
            all_output.append(output)
            
            if not success:
                self.console.error(f"Command failed: {command}")
                return (False, "\n".join(all_output))
        
        # Show timing if enabled
        if self.config.output.show_timing:
            elapsed = time.time() - start_time
            self.console.success(f"Completed in {elapsed:.2f}s")
        
        # Log execution
        if self.safety_config.logging.log_commands:
            for command in commands:
                logger.info(f"Executed: {command}")
        
        return (True, "\n".join(all_output))

    def _execute_single(self, command: str) -> Tuple[bool, str]:
        """
        Execute a single command.
        
        Args:
            command: Command to execute
            
        Returns:
            Tuple of (success, output)
        """
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )
            
            output = result.stdout
            if result.stderr:
                output += "\n" + result.stderr
            
            if result.returncode == 0:
                if output.strip():
                    self.console.print(output)
                return (True, output)
            else:
                self.console.error(f"Exit code: {result.returncode}")
                if output.strip():
                    self.console.print(output)
                return (False, output)
        
        except subprocess.TimeoutExpired:
            error = "Command timed out after 5 minutes"
            self.console.error(error)
            return (False, error)
        
        except Exception as e:
            error = f"Execution error: {e}"
            self.console.error(error)
            logger.error(error, exc_info=True)
            return (False, error)

    def _confirm_execution(self) -> bool:
        """
        Ask user to confirm execution.
        
        Returns:
            True if user confirms
        """
        self.console.print("\n")
        
        try:
            response = input("Confirm execution? [y/N]: ").strip().lower()
            return response in ["y", "yes"]
        except (KeyboardInterrupt, EOFError):
            self.console.print("\n")
            return False
