"""
Skill commands - Skill management.
"""

from typing import Optional, Tuple

import click


@click.group(name="skill")
def skill_cli():
    """Skill management"""
    pass


@skill_cli.command(name="list")
def list_skills() -> None:
    """List all available skills"""
    from clis.output.formatter import OutputFormatter
    from clis.router import SkillRouter
    
    formatter = OutputFormatter()
    router = SkillRouter()
    
    skills = router.list_skills()
    
    if not skills:
        formatter.show_info("No skills found.")
        return
    
    formatter.show_info(f"\n📋 Available Skills ({len(skills)}):\n")
    for skill in skills:
        formatter.show_info(f"  • {skill}")


@skill_cli.command(name="create")
@click.argument("name")
@click.option("--auto", is_flag=True, help="Use LLM to auto-generate skill based on prompt")
@click.option("--tools", multiple=True, help="Tools to include in the skill")
def create_skill(name: str, auto: bool, tools: Tuple[str, ...]) -> None:
    """Create new skill
    
    Examples:
        clis skill create my-skill
        clis skill create my-skill --auto
        clis skill create my-skill --tools read_file --tools write_file
    """
    from clis.config import ConfigManager
    from clis import cli as cli_module
    
    config_manager = ConfigManager()
    tools_list = list(tools) if tools else None
    
    if auto:
        click.echo(f"Creating skill '{name}' with LLM assistance...")
        prompt = click.prompt("Describe what this skill should do")
        cli_module._create_skill_with_llm(prompt, config_manager, tools_list)
    else:
        click.echo(f"Creating skill template: {name}")
        cli_module._create_skill_template(name, config_manager, tools_list)


@skill_cli.command(name="edit")
@click.argument("name")
@click.option("--editor", help="Editor to use (code, vim, nano, etc.)")
def edit_skill(name: str, editor: Optional[str] = None) -> None:
    """Edit skill file"""
    import subprocess
    import os
    from clis.router import SkillRouter
    
    router = SkillRouter()
    
    try:
        skill = router.load_skill(name)
        skill_path = skill.file_path
        
        if not skill_path or not skill_path.exists():
            click.echo(f"❌ Skill file not found: {name}")
            return
        
        # Determine editor
        if editor is None:
            editor = os.environ.get("EDITOR", "vim")
        
        click.echo(f"Opening {skill_path} in {editor}...")
        subprocess.run([editor, str(skill_path)])
        
    except FileNotFoundError:
        click.echo(f"❌ Skill not found: {name}")
        click.echo(f"Available skills: {', '.join(router.list_skills())}")


@skill_cli.command(name="validate")
@click.argument("name")
def validate_skill(name: str) -> None:
    """Validate skill format"""
    from clis.router import SkillRouter
    from clis.output.formatter import OutputFormatter
    
    router = SkillRouter()
    formatter = OutputFormatter()
    
    try:
        skill = router.load_skill(name)
        formatter.show_info(f"✅ Skill '{name}' is valid")
        formatter.show_info(f"   Name: {skill.name}")
        formatter.show_info(f"   Version: {skill.version}")
        formatter.show_info(f"   Tools: {len(skill.tools)}")
    except Exception as e:
        formatter.show_error(f"❌ Skill validation failed: {e}")


@skill_cli.command(name="test")
@click.argument("name")
@click.argument("query", required=False)
@click.option("--dry-run", is_flag=True, help="Show commands without executing")
def test_skill(name: str, query: Optional[str], dry_run: bool) -> None:
    """Test skill
    
    Examples:
        clis skill test docker-manager
        clis skill test git-helper "commit changes"
    """
    from clis.router import SkillRouter
    from clis.output.formatter import OutputFormatter
    
    router = SkillRouter()
    formatter = OutputFormatter()
    
    try:
        skill = router.load_skill(name)
        
        if query is None:
            # Show skill info
            formatter.show_info(f"Skill: {skill.name}")
            formatter.show_info(f"Description: {skill.description}")
            formatter.show_info("Use: clis skill test <name> <query> to test with a query")
        else:
            # Test with query
            formatter.show_info(f"Testing skill '{name}' with query: {query}")
            if dry_run:
                formatter.show_info("[Dry run mode - no commands will be executed]")
            # TODO: Implement skill testing
            formatter.show_info("[yellow]Testing not yet implemented[/yellow]")
            
    except Exception as e:
        formatter.show_error(f"Error: {e}")


@skill_cli.command(name="install")
@click.argument("source")
@click.option("--with-deps", is_flag=True, help="Download skill dependencies")
def install_skill(source: str, with_deps: bool) -> None:
    """Install skill from GitHub or URL
    
    Examples:
        clis skill install username/repo
        clis skill install https://github.com/user/repo/skill.md
    """
    click.echo(f"Installing skill from: {source}")
    click.echo("[yellow]Skill installation not yet implemented[/yellow]")
