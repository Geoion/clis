"""
Error display module - User-friendly error message display

Provides beautiful, clear, and helpful error prompts
"""

from typing import Optional, List, Any
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.markdown import Markdown

console = Console()


class ErrorDisplay:
    """Error display class"""
    
    @staticmethod
    def show_error(
        error_type: str,
        message: str,
        context: Optional[str] = None,
        suggestions: Optional[List[str]] = None,
        show_help: bool = True
    ):
        """
        Display formatted error information
        
        Args:
            error_type: Error type
            message: Error message
            context: Context
            suggestions: List of solution suggestions
            show_help: Whether to show help information
        """
        # Build error content
        content = f"[bold red]Error Type:[/bold red] {error_type}\n"
        content += f"[bold]Error Message:[/bold] {message}\n"
        
        if context:
            content += f"\n[dim]Location:[/dim] {context}\n"
        
        if suggestions:
            content += f"\n[bold yellow]💡 Suggestions:[/bold yellow]\n"
            for i, suggestion in enumerate(suggestions, 1):
                content += f"   {i}. {suggestion}\n"
        
        if show_help:
            content += f"\n[dim]📚 Get Help:[/dim]\n"
            content += f"   • Run diagnostics: [cyan]clis doctor[/cyan]\n"
            content += f"   • View documentation: [cyan]https://github.com/eskiyin/clis[/cyan]\n"
            content += f"   • View logs: [dim]~/.clis/logs/clis.log[/dim]\n"
        
        # Display panel
        console.print(Panel(
            content,
            title="[bold red]❌ Error[/bold red]",
            border_style="red"
        ))
    
    @staticmethod
    def show_tool_error(
        tool_name: str,
        error_type: str,
        message: str,
        params: dict,
        suggestions: Optional[List[str]] = None
    ):
        """
        Display tool execution error
        
        Args:
            tool_name: Tool name
            error_type: Error type
            message: Error message
            params: Tool parameters
            suggestions: Solution suggestions
        """
        content = f"[bold]Tool:[/bold] {tool_name}\n"
        content += f"[bold red]Error:[/bold red] {error_type}\n"
        content += f"[bold]Message:[/bold] {message}\n"
        
        # Display parameters
        if params:
            content += f"\n[bold]Call Parameters:[/bold]\n"
            for key, value in params.items():
                # Truncate overly long values
                value_str = str(value)
                if len(value_str) > 100:
                    value_str = value_str[:97] + "..."
                content += f"   • {key}: {value_str}\n"
        
        if suggestions:
            content += f"\n[bold yellow]💡 Suggestions:[/bold yellow]\n"
            for i, suggestion in enumerate(suggestions, 1):
                content += f"   {i}. {suggestion}\n"
        
        console.print(Panel(
            content,
            title=f"[bold red]❌ Tool Execution Failed: {tool_name}[/bold red]",
            border_style="red"
        ))
    
    @staticmethod
    def show_warning(message: str, title: str = "Warning"):
        """Display warning information"""
        console.print(Panel(
            f"[yellow]{message}[/yellow]",
            title=f"[bold yellow]⚠️  {title}[/bold yellow]",
            border_style="yellow"
        ))
    
    @staticmethod
    def show_success(message: str, title: str = "Success"):
        """Display success information"""
        console.print(Panel(
            f"[green]{message}[/green]",
            title=f"[bold green]✅ {title}[/bold green]",
            border_style="green"
        ))
    
    @staticmethod
    def show_tip(message: str):
        """Display tip information"""
        console.print(f"\n[dim]💡 Tip: {message}[/dim]\n")
    
    @staticmethod
    def show_validation_error(field: str, value: Any, expected: str):
        """
        Display parameter validation error
        
        Args:
            field: Field name
            value: Actual value
            expected: Expected format/type
        """
        content = f"[bold]Parameter Validation Failed[/bold]\n\n"
        content += f"Field: [cyan]{field}[/cyan]\n"
        content += f"Actual Value: [red]{value}[/red]\n"
        content += f"Expected: [green]{expected}[/green]\n"
        
        console.print(Panel(
            content,
            title="[bold red]❌ Parameter Error[/bold red]",
            border_style="red"
        ))
    
    @staticmethod
    def show_progress_error(task: str, current: int, total: int, error: str):
        """
        Display progress-related error
        
        Args:
            task: Task name
            current: Current progress
            total: Total
            error: Error message
        """
        content = f"[bold]Task:[/bold] {task}\n"
        content += f"[bold]Progress:[/bold] {current}/{total}\n"
        content += f"[bold red]Error:[/bold red] {error}\n"
        
        console.print(Panel(
            content,
            title="[bold red]❌ Task Execution Failed[/bold red]",
            border_style="red"
        ))


# Export
__all__ = ['ErrorDisplay']
