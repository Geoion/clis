"""
System commands - System info, version, doctor, etc.
"""

import click


@click.command(name="version")
def version() -> None:
    """Show version information"""
    from clis import __version__
    from clis.utils.platform import get_platform, get_clis_dir
    
    click.echo(f"CLIS version {__version__}")
    click.echo(f"Platform: {get_platform()}")
    click.echo(f"Config directory: {get_clis_dir()}")


@click.command(name="doctor")
def doctor() -> None:
    """Check CLIS environment and configuration"""
    import platform
    import sys
    from pathlib import Path
    from rich.console import Console
    from rich.table import Table
    
    from clis import __version__
    from clis.config import ConfigManager
    from clis.utils.platform import get_clis_dir, get_platform
    
    console = Console()
    console.print("\n[bold cyan]🏥 CLIS Doctor - Environment Check[/bold cyan]\n")
    
    # System Info
    console.print("[bold]System Information:[/bold]")
    sys_table = Table(show_header=False)
    sys_table.add_column("Key", style="cyan")
    sys_table.add_column("Value", style="green")
    
    sys_table.add_row("CLIS Version", __version__)
    sys_table.add_row("Python Version", f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    sys_table.add_row("Platform", get_platform())
    sys_table.add_row("OS", f"{platform.system()} {platform.release()}")
    sys_table.add_row("Architecture", platform.machine())
    
    console.print(sys_table)
    
    # Configuration
    console.print("\n[bold]Configuration:[/bold]")
    config_manager = ConfigManager()
    config_dir = get_clis_dir() / "config"
    
    config_table = Table(show_header=False)
    config_table.add_column("Item", style="cyan")
    config_table.add_column("Status", style="green")
    
    # Check config directory
    if config_dir.exists():
        config_table.add_row("Config Directory", f"✅ {config_dir}")
    else:
        config_table.add_row("Config Directory", f"❌ Not found: {config_dir}")
    
    # Check config files
    required_configs = ["llm.yaml", "safety.yaml", "base.yaml"]
    for config_file in required_configs:
        config_path = config_dir / config_file
        if config_path.exists():
            config_table.add_row(f"  {config_file}", "✅ Found")
        else:
            config_table.add_row(f"  {config_file}", "❌ Missing")
    
    console.print(config_table)
    
    # LLM Configuration
    console.print("\n[bold]LLM Configuration:[/bold]")
    try:
        llm_config = config_manager.load_llm_config()
        llm_table = Table(show_header=False)
        llm_table.add_column("Key", style="cyan")
        llm_table.add_column("Value", style="green")
        
        llm_table.add_row("Provider", llm_config.provider)
        llm_table.add_row("Model", llm_config.model.name)
        
        # Check API key
        if llm_config.provider != "ollama":
            import os
            env_key = f"{llm_config.provider.upper()}_API_KEY"
            if os.environ.get(env_key):
                llm_table.add_row("API Key", f"✅ Set (${env_key})")
            else:
                llm_table.add_row("API Key", f"❌ Not set (${env_key})")
        
        console.print(llm_table)
        
    except Exception as e:
        console.print(f"[red]❌ Error loading LLM config: {e}[/red]")
    
    # Skills
    console.print("\n[bold]Skills:[/bold]")
    try:
        from clis.router import SkillRouter
        router = SkillRouter()
        skills = router.list_skills()
        
        console.print(f"  Found {len(skills)} skill(s)")
        if skills:
            for skill in skills[:5]:  # Show first 5
                console.print(f"    • {skill}")
            if len(skills) > 5:
                console.print(f"    ... and {len(skills) - 5} more")
    except Exception as e:
        console.print(f"[red]  Error loading skills: {e}[/red]")
    
    # Dependencies
    console.print("\n[bold]Dependencies:[/bold]")
    deps_table = Table(show_header=False)
    deps_table.add_column("Package", style="cyan")
    deps_table.add_column("Status", style="green")
    
    required_deps = ["click", "rich", "pydantic", "yaml"]
    for dep in required_deps:
        try:
            __import__(dep)
            deps_table.add_row(dep, "✅ Installed")
        except ImportError:
            deps_table.add_row(dep, "❌ Missing")
    
    console.print(deps_table)
    
    # Summary
    console.print("\n[bold green]✅ Environment check complete![/bold green]")
    console.print("\n💡 Tips:")
    console.print("  • Run [cyan]clis init[/cyan] to initialize configuration")
    console.print("  • Run [cyan]clis skill list[/cyan] to see available skills")
    console.print("  • Run [cyan]clis config show[/cyan] to view configuration")


@click.command(name="init")
@click.option(
    "--provider",
    type=click.Choice(["deepseek", "ollama", "openai", "anthropic", "qwen"]),
    help="LLM provider to use",
)
def init(provider: str = None) -> None:
    """Initialize CLIS configuration (interactive wizard)
    
    This will create configuration files in ~/.clis/config/ with
    detailed comments.
    """
    from clis.config import ConfigManager
    
    click.echo("🚀 Welcome to CLIS!")
    click.echo()
    
    config_manager = ConfigManager()
    
    # Check if config already exists
    if config_manager.config_exists():
        if not click.confirm("⚠️  Configuration already exists. Overwrite?", default=False):
            click.echo("Initialization cancelled.")
            return
    
    click.echo("Let's set up your CLIS configuration...")
    click.echo()
    
    # Step 1: Choose LLM provider
    if provider is None:
        click.echo("📋 Step 1: Choose your LLM provider")
        click.echo()
        click.echo("Available providers:")
        click.echo("  1. DeepSeek (Recommended) - Low cost, high quality")
        click.echo("  2. Ollama - Local, completely offline")
        click.echo("  3. OpenAI - GPT-4, GPT-3.5")
        click.echo("  4. Anthropic - Claude")
        click.echo("  5. Qwen - Qwen (Tongyi Qianwen)")
        click.echo()
        
        choice = click.prompt(
            "Select provider",
            type=click.Choice(["1", "2", "3", "4", "5"]),
            default="1",
        )
        
        provider_map = {
            "1": "deepseek",
            "2": "ollama",
            "3": "openai",
            "4": "anthropic",
            "5": "qwen",
        }
        provider = provider_map[choice]
    
    click.echo(f"\n✅ Selected provider: {provider}")
    
    # Step 2: API Key (if needed)
    if provider != "ollama":
        click.echo(f"\n📋 Step 2: Set up API key for {provider}")
        click.echo()
        click.echo(f"You can either:")
        click.echo(f"  1. Set environment variable: export {provider.upper()}_API_KEY='your-key'")
        click.echo(f"  2. Enter it here (will be saved to config)")
        click.echo()
        
        if not click.confirm("Do you want to enter API key now?", default=False):
            click.echo(f"\n⚠️  Remember to set {provider.upper()}_API_KEY environment variable")
    
    # Initialize configuration
    click.echo("\n📝 Creating configuration files...")
    try:
        config_manager.initialize()
        click.echo("✅ Configuration files created successfully!")
        
        from clis.utils.platform import get_clis_dir
        config_dir = get_clis_dir() / "config"
        click.echo(f"\n📁 Configuration directory: {config_dir}")
        click.echo("\nYou can edit these files to customize your settings:")
        click.echo("  • llm.yaml - LLM provider and model settings")
        click.echo("  • safety.yaml - Safety and security settings")
        click.echo("  • base.yaml - General settings")
        
        click.echo("\n🎉 CLIS is ready to use!")
        click.echo("\nNext steps:")
        click.echo("  • Run [cyan]clis doctor[/cyan] to verify installation")
        click.echo("  • Run [cyan]clis skill list[/cyan] to see available skills")
        click.echo("  • Run [cyan]clis run \"your query\"[/cyan] to start using CLIS")
        
    except Exception as e:
        click.echo(f"\n❌ Error: {e}")
        click.echo("Please check the error message and try again.")
