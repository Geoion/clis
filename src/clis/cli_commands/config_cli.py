"""
Config commands - Configuration management.
"""

from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from clis.config import ConfigManager


@click.group(name="config")
def config_cli():
    """Configuration management"""
    pass


@config_cli.command(name="show")
def show_config() -> None:
    """Show all configuration values"""
    console = Console()
    config_manager = ConfigManager()
    
    # Load all configs
    try:
        llm_config = config_manager.load_llm_config()
        safety_config = config_manager.load_safety_config()
        
        # LLM Configuration
        console.print("\n[bold cyan]🤖 LLM Configuration[/bold cyan]")
        llm_table = Table(show_header=True, header_style="bold magenta")
        llm_table.add_column("Key", style="cyan")
        llm_table.add_column("Value", style="green")
        
        llm_table.add_row("Provider", llm_config.provider)
        llm_table.add_row("Model", llm_config.model.name)
        llm_table.add_row("Temperature", str(llm_config.model.temperature))
        llm_table.add_row("Max Tokens", str(llm_config.model.max_tokens))
        llm_table.add_row("Context Window", str(llm_config.model.context.window_size))
        
        console.print(llm_table)
        
        # Safety Configuration
        console.print("\n[bold cyan]🛡️  Safety Configuration[/bold cyan]")
        safety_table = Table(show_header=True, header_style="bold magenta")
        safety_table.add_column("Key", style="cyan")
        safety_table.add_column("Value", style="green")
        
        safety_table.add_row("Blacklist Enabled", str(safety_config.blacklist.enabled))
        safety_table.add_row("Dry Run", str(safety_config.dry_run.enabled))
        safety_table.add_row("Risk Scoring", str(safety_config.risk.enabled))
        safety_table.add_row("Max Iterations", str(safety_config.agent.max_iterations))
        
        console.print(safety_table)
        
    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")


@config_cli.command(name="get")
@click.argument("key")
def get_config(key: str) -> None:
    """Get a configuration value
    
    Examples:
        clis config get llm.provider
        clis config get safety.max_iterations
    """
    config_manager = ConfigManager()
    
    try:
        # Parse key (e.g., "llm.provider" -> config="llm", key="provider")
        parts = key.split(".", 1)
        
        if len(parts) == 1:
            click.echo(f"Error: Key must be in format 'config.key' (e.g., 'llm.provider')")
            return
        
        config_name, config_key = parts
        
        if config_name == "llm":
            config = config_manager.load_llm_config()
            value = getattr(config, config_key, None)
        elif config_name == "safety":
            config = config_manager.load_safety_config()
            value = getattr(config, config_key, None)
        else:
            click.echo(f"Unknown config: {config_name}")
            return
        
        if value is not None:
            click.echo(f"{key} = {value}")
        else:
            click.echo(f"Key not found: {key}")
            
    except Exception as e:
        click.echo(f"Error: {e}")


@config_cli.command(name="set")
@click.argument("key")
@click.argument("value")
def set_config(key: str, value: str) -> None:
    """Set a configuration value
    
    Examples:
        clis config set llm.temperature 0.7
        clis config set safety.max_iterations 50
    """
    click.echo(f"Setting {key} = {value}")
    click.echo("[yellow]Note: Config modification is not yet implemented.[/yellow]")
    click.echo("[dim]Please edit config files directly in ~/.clis/config/[/dim]")


@config_cli.command(name="reset")
@click.option("--confirm", is_flag=True, help="Skip confirmation")
def reset_config(confirm: bool) -> None:
    """Reset configuration to default values"""
    if not confirm:
        if not click.confirm("Are you sure you want to reset all configuration?"):
            click.echo("Cancelled.")
            return
    
    config_manager = ConfigManager()
    
    try:
        # Recreate default configs
        config_manager.initialize()
        click.echo("[green]✅ Configuration reset to defaults[/green]")
    except Exception as e:
        click.echo(f"[red]Error: {e}[/red]")


@config_cli.command(name="path")
def show_config_path() -> None:
    """Show configuration directory path"""
    from clis.utils.platform import get_clis_dir
    
    config_dir = get_clis_dir() / "config"
    click.echo(f"Configuration directory: {config_dir}")
    
    # List config files
    if config_dir.exists():
        click.echo("\nConfig files:")
        for config_file in sorted(config_dir.glob("*.yaml")):
            click.echo(f"  • {config_file.name}")
