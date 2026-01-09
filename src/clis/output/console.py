"""
Console manager for CLIS - manages Rich console output.
"""

from typing import Optional

from rich.console import Console as RichConsole
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from clis.config import ConfigManager
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class Console:
    """Console manager for formatted output."""

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """
        Initialize console.
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config_manager = config_manager or ConfigManager()
        self.config = self.config_manager.load_base_config()
        
        # Initialize Rich console
        self.use_rich = self.config.output.use_rich
        if self.use_rich:
            self.console = RichConsole()
        else:
            self.console = None

    def print(self, text: str, style: Optional[str] = None) -> None:
        """
        Print text.
        
        Args:
            text: Text to print
            style: Rich style (if using Rich)
        """
        if self.use_rich and self.console:
            self.console.print(text, style=style)
        else:
            print(text)

    def info(self, text: str) -> None:
        """Print info message."""
        if self.use_rich and self.console:
            self.console.print(f"ℹ️  {text}", style="blue")
        else:
            print(f"[INFO] {text}")

    def success(self, text: str) -> None:
        """Print success message."""
        if self.use_rich and self.console:
            self.console.print(f"✓ {text}", style="green")
        else:
            print(f"[SUCCESS] {text}")

    def warning(self, text: str) -> None:
        """Print warning message."""
        if self.use_rich and self.console:
            self.console.print(f"⚠️  {text}", style="yellow")
        else:
            print(f"[WARNING] {text}")

    def error(self, text: str) -> None:
        """Print error message."""
        if self.use_rich and self.console:
            self.console.print(f"✗ {text}", style="red")
        else:
            print(f"[ERROR] {text}")

    def code(self, code: str, language: str = "bash") -> None:
        """
        Print code with syntax highlighting.
        
        Args:
            code: Code to print
            language: Programming language
        """
        if self.use_rich and self.console:
            syntax = Syntax(code, language, theme="monokai", line_numbers=False)
            self.console.print(syntax)
        else:
            print(code)

    def panel(self, text: str, title: Optional[str] = None, style: str = "blue") -> None:
        """
        Print text in a panel.
        
        Args:
            text: Text to print
            title: Panel title
            style: Panel style
        """
        if self.use_rich and self.console:
            panel = Panel(text, title=title, border_style=style)
            self.console.print(panel)
        else:
            if title:
                print(f"\n=== {title} ===")
            print(text)
            if title:
                print("=" * (len(title) + 8))

    def table(self, headers: list, rows: list) -> None:
        """
        Print a table.
        
        Args:
            headers: Table headers
            rows: Table rows
        """
        if self.use_rich and self.console:
            table = Table(show_header=True, header_style="bold cyan")
            for header in headers:
                table.add_column(header)
            for row in rows:
                table.add_row(*[str(cell) for cell in row])
            self.console.print(table)
        else:
            # Simple text table
            print("\t".join(headers))
            print("-" * 80)
            for row in rows:
                print("\t".join(str(cell) for cell in row))

    def rule(self, title: Optional[str] = None) -> None:
        """
        Print a horizontal rule.
        
        Args:
            title: Optional title
        """
        if self.use_rich and self.console:
            self.console.rule(title)
        else:
            if title:
                print(f"\n{'=' * 40} {title} {'=' * 40}")
            else:
                print("=" * 80)
