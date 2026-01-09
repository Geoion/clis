"""
CLI command definitions using Click.
"""

import sys
from typing import Optional

import click
import requests

from clis import __version__
from clis.agent import Agent
from clis.config import ConfigManager
from clis.config.models import APIConfig, LLMConfig, ModelConfig
from clis.executor import CommandExecutor
from clis.output.formatter import OutputFormatter
from clis.router import SkillMatcher, SkillRouter
from clis.safety import SafetyMiddleware
from clis.utils.platform import get_clis_dir, get_platform


def execute_query(query: str, verbose: bool = False, minimal: bool = False, debug: bool = False) -> None:
    """
    Execute a natural language query.
    
    Args:
        query: User's natural language query
        verbose: Enable verbose output
        minimal: Enable minimal output
        debug: Enable debug output
    """
    try:
        # Initialize components
        config_manager = ConfigManager()
        
        # Check if config exists
        if not config_manager.config_exists():
            click.echo("⚠️  Configuration not found. Please run 'clis init' first.", err=True)
            sys.exit(1)
        
        # Set output level based on flags
        if debug:
            config_manager.set_config_value("output.level", "debug")
        elif verbose:
            config_manager.set_config_value("output.level", "verbose")
        elif minimal:
            config_manager.set_config_value("output.level", "minimal")
        
        formatter = OutputFormatter(config_manager)
        router = SkillRouter()
        agent = Agent(config_manager)
        matcher = SkillMatcher(agent)
        safety = SafetyMiddleware(config_manager)
        executor = CommandExecutor(config_manager)
        
        # Step 1: Load skills
        formatter.show_info("🔍 Analyzing your request...")
        skills = router.scan_skills()
        
        if not skills:
            formatter.show_error("No skills found. Please add skills to ~/.clis/skills/")
            sys.exit(1)
        
        # Step 2: Match skill
        match_result = matcher.match(query, skills)
        
        if not match_result:
            formatter.show_error("Could not find a suitable skill for your request.")
            formatter.show_info("Try: clis list  # to see available skills")
            sys.exit(1)
        
        skill, confidence = match_result
        formatter.show_skill_match(skill.name, confidence)
        
        # Step 3: Generate commands using LLM
        formatter.show_info("🤖 Generating commands...")
        
        system_prompt = f"""
You are executing the "{skill.name}" skill.

{skill.instructions}

Generate commands based on the user's request.
You MUST respond in JSON format:
{{
    "commands": ["command1", "command2"],
    "explanation": "Brief explanation of what these commands do"
}}
"""
        
        response = agent.generate_json(query, system_prompt)
        
        commands = response.get("commands", [])
        explanation = response.get("explanation", "")
        
        if not commands:
            formatter.show_error("No commands generated")
            sys.exit(1)
        
        # Step 4: Safety check
        is_safe, safety_msg, risk_level = safety.check_commands(commands, skill)
        
        if not is_safe:
            formatter.show_error(f"Safety check failed: {safety_msg}")
            sys.exit(1)
        
        # Step 5: Show commands
        formatter.show_commands(commands, explanation, risk_level)
        
        # Step 6: Execute
        action = safety.get_required_action(risk_level)
        
        if action == "block":
            formatter.show_error("Command blocked due to high risk")
            sys.exit(1)
        
        require_confirmation = action in ["confirm", "dry_run"]
        success, output = executor.execute(commands, require_confirmation)
        
        if not success:
            sys.exit(1)
        
        # Show API usage info
        if verbose or debug:
            prompt_text = system_prompt + "\n\n" + query
            cost = agent.estimate_cost(prompt_text, str(response))
            formatter.show_api_call(
                provider=config_manager.load_llm_config().provider,
                model=config_manager.load_llm_config().model.name,
                tokens={"input": agent.provider.count_tokens(prompt_text), "output": agent.provider.count_tokens(str(response))},
                cost=cost,
            )
    
    except KeyboardInterrupt:
        click.echo("\n\n⚠️  Interrupted by user")
        sys.exit(130)
    except Exception as e:
        click.echo(f"\n❌ Error: {e}", err=True)
        if debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="clis")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--minimal", is_flag=True, help="Minimal output")
@click.option("--debug", is_flag=True, help="Enable debug output")
@click.pass_context
def main(ctx: click.Context, verbose: bool, minimal: bool, debug: bool) -> None:
    """
    CLIS - A programmable terminal assistant with Skill-based SOP execution.
    
    Use natural language to execute terminal commands safely and efficiently.
    
    Examples:
        clis run "show system information"
        clis run "commit code with message: fix bug"
        clis run "find all Python files"
    """
    # Store global options in context
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["minimal"] = minimal
    ctx.obj["debug"] = debug
    
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command()
@click.argument("query")
@click.pass_context
def run(ctx: click.Context, query: str) -> None:
    """
    Execute a natural language query.
    
    Examples:
        clis run "show system information"
        clis run "commit code with message: fix bug"
    """
    verbose = ctx.obj.get("verbose", False)
    minimal = ctx.obj.get("minimal", False)
    debug = ctx.obj.get("debug", False)
    
    execute_query(query, verbose, minimal, debug)


@main.command()
def version() -> None:
    """Show version information."""
    click.echo(f"CLIS version {__version__}")
    click.echo(f"Platform: {get_platform()}")
    click.echo(f"Config directory: {get_clis_dir()}")


@main.command()
@click.option(
    "--provider",
    type=click.Choice(["deepseek", "ollama", "openai", "anthropic", "qwen"]),
    help="LLM provider to use",
)
def init(provider: Optional[str]) -> None:
    """
    Initialize CLIS configuration with interactive wizard.
    
    This will create configuration files in ~/.clis/config/ with
    detailed comments in both English and Chinese.
    """
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
        click.echo("  1. DeepSeek (推荐) - Low cost, high quality")
        click.echo("  2. Ollama - Local, completely offline")
        click.echo("  3. OpenAI - GPT-4, GPT-3.5")
        click.echo("  4. Anthropic - Claude")
        click.echo("  5. Qwen - 通义千问")
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
    
    click.echo()
    click.echo(f"✓ Selected provider: {provider}")
    click.echo()
    
    # Step 2: Configure provider-specific settings
    llm_config = LLMConfig(provider=provider)  # type: ignore
    
    if provider == "ollama":
        click.echo("📋 Step 2: Configure Ollama")
        click.echo()
        
        # Check if Ollama is running
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            if response.status_code == 200:
                models = response.json().get("models", [])
                if models:
                    click.echo("✓ Ollama is running")
                    click.echo()
                    click.echo("Available models:")
                    for model in models:
                        click.echo(f"  - {model['name']}")
                    click.echo()
                    
                    model_name = click.prompt(
                        "Select model",
                        default=models[0]["name"] if models else "llama3",
                    )
                else:
                    click.echo("⚠️  No models found. Please run: ollama pull llama3")
                    model_name = "llama3"
            else:
                click.echo("⚠️  Ollama is not responding correctly")
                model_name = "llama3"
        except Exception:
            click.echo("⚠️  Ollama is not running")
            click.echo()
            click.echo("To install Ollama:")
            click.echo("  1. Visit: https://ollama.ai/download")
            click.echo("  2. Install Ollama")
            click.echo("  3. Run: ollama pull llama3")
            click.echo()
            model_name = "llama3"
        
        llm_config.api = APIConfig(base_url="http://localhost:11434")
        llm_config.model = ModelConfig(name=model_name)
    
    else:
        # For cloud providers, ask for API key
        click.echo(f"📋 Step 2: Configure {provider}")
        click.echo()
        
        # Provider-specific defaults
        provider_defaults = {
            "deepseek": {
                "base_url": "https://api.deepseek.com/v1",
                "model": "deepseek-chat",
                "env_var": "DEEPSEEK_API_KEY",
            },
            "openai": {
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4",
                "env_var": "OPENAI_API_KEY",
            },
            "anthropic": {
                "base_url": "https://api.anthropic.com",
                "model": "claude-3-sonnet-20240229",
                "env_var": "ANTHROPIC_API_KEY",
            },
            "qwen": {
                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "model": "qwen-plus",
                "env_var": "QWEN_API_KEY",
            },
        }
        
        defaults = provider_defaults[provider]
        
        click.echo(f"API Key will be read from environment variable: ${{{defaults['env_var']}}}")
        click.echo()
        click.echo("To set your API key, add this to your shell configuration:")
        click.echo(f"  export {defaults['env_var']}=\"your-api-key-here\"")
        click.echo()
        
        if not click.confirm("Have you set the API key?", default=False):
            click.echo()
            click.echo("⚠️  You can continue setup and add the API key later.")
            click.echo()
        
        llm_config.api = APIConfig(
            key=f"${{{defaults['env_var']}}}",
            base_url=defaults["base_url"],
        )
        llm_config.model = ModelConfig(name=defaults["model"])
    
    # Step 3: Create configuration files
    click.echo()
    click.echo("📋 Step 3: Creating configuration files...")
    click.echo()
    
    # Create default configs
    config_manager.create_default_configs()
    
    # Update LLM config
    config_manager.save_llm_config(llm_config)
    
    click.echo("✓ Configuration files created:")
    click.echo(f"  - {config_manager.base_config_path}")
    click.echo(f"  - {config_manager.llm_config_path}")
    click.echo(f"  - {config_manager.safety_config_path}")
    click.echo()
    
    # Step 4: Next steps
    click.echo("🎉 CLIS is ready to use!")
    click.echo()
    click.echo("Next steps:")
    click.echo("  1. Run 'clis doctor' to verify your setup")
    click.echo("  2. Run 'clis list' to see available skills")
    click.echo("  3. Try: clis \"show system information\"")
    click.echo()
    click.echo("For help, run: clis --help")


@main.command()
@click.argument("name")
def new(name: str) -> None:
    """
    Create a new skill with AI assistance.
    
    This will use LLM to generate a skill template based on your description.
    """
    from clis.agent import Agent
    from clis.utils.platform import get_skills_dir, ensure_dir
    
    config_manager = ConfigManager()
    
    # Check if config exists
    if not config_manager.config_exists():
        click.echo("⚠️  Configuration not found. Please run 'clis init' first.", err=True)
        sys.exit(1)
    
    # Check if skill already exists
    skill_path = get_skills_dir() / "custom" / f"{name}.md"
    if skill_path.exists():
        if not click.confirm(f"⚠️  Skill '{name}' already exists. Overwrite?", default=False):
            click.echo("Cancelled.")
            return
    
    click.echo(f"🎨 Creating new skill: {name}")
    click.echo()
    
    # Ask for skill description
    description = click.prompt("Brief description of what this skill does")
    click.echo()
    
    # Ask for main operations
    click.echo("What operations should this skill perform? (one per line, empty line to finish)")
    operations = []
    while True:
        op = input("  - ").strip()
        if not op:
            break
        operations.append(op)
    
    if not operations:
        click.echo("⚠️  No operations specified. Cancelled.")
        return
    
    click.echo()
    click.echo("🤖 Generating skill template with AI...")
    
    # Generate skill template using LLM
    try:
        agent = Agent(config_manager)
        
        operations_text = "\n".join([f"- {op}" for op in operations])
        
        system_prompt = """
You are a skill template generator for CLIS.
Generate a complete SKILL.md file based on the user's requirements.

The skill MUST follow this format:

# Skill Name: [Name]

## Description
[Brief description]

## Instructions
[Detailed instructions for the AI on how to execute this skill]
1. Step 1
2. Step 2
...

## Input Schema
```json
{
  "field1": "type (description)",
  "field2": "type (description)"
}
```

## Examples

**用户输入**: [example input]

**AI 输出**:
```json
{
  "commands": ["command1", "command2"],
  "explanation": "explanation"
}
```

## Safety Rules (CLIS Extension)
- Forbid: [dangerous patterns]
- Require confirmation: [risky patterns]

## Platform Compatibility (CLIS Extension)
- windows: [Windows-specific instructions]
- macos: [macOS-specific instructions]
- linux: [Linux-specific instructions]

## Dry-Run Mode (CLIS Extension)
[true/false]

Generate a complete, production-ready skill file.
"""
        
        prompt = f"""
Create a skill with the following details:

Name: {name}
Description: {description}

Operations to support:
{operations_text}

Generate the complete SKILL.md content.
"""
        
        skill_content = agent.generate(prompt, system_prompt, inject_context=False)
        
        # Clean up the response (remove markdown code blocks if present)
        if "```markdown" in skill_content:
            start = skill_content.find("```markdown") + 11
            end = skill_content.rfind("```")
            skill_content = skill_content[start:end].strip()
        elif "```" in skill_content:
            start = skill_content.find("```") + 3
            end = skill_content.rfind("```")
            skill_content = skill_content[start:end].strip()
        
        # Save skill file
        ensure_dir(skill_path.parent)
        with open(skill_path, "w", encoding="utf-8") as f:
            f.write(skill_content)
        
        click.echo()
        click.echo(f"✓ Skill created: {skill_path}")
        click.echo()
        click.echo("Next steps:")
        click.echo(f"  1. Review and edit: clis edit {name}")
        click.echo(f"  2. Validate: clis validate {name}")
        click.echo(f"  3. Use it: clis run \"[your query]\"")
    
    except Exception as e:
        click.echo(f"\n❌ Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.argument("name")
@click.option("--editor", help="Editor to use (code, vim, nano, etc.)")
def edit(name: str, editor: Optional[str] = None) -> None:
    """
    Edit a skill file.
    
    Opens the skill file in your configured editor.
    """
    import os
    import subprocess
    from pathlib import Path
    
    from clis.router import SkillRouter
    
    router = SkillRouter()
    skill = router.get_skill(name)
    
    if not skill:
        click.echo(f"Skill '{name}' not found", err=True)
        sys.exit(1)
    
    # Determine which editor to use
    if editor is None:
        config_manager = ConfigManager()
        base_config = config_manager.load_base_config()
        
        if base_config.editor.preferred != "auto":
            editor = base_config.editor.preferred
        else:
            # Try $EDITOR environment variable
            editor = os.environ.get("EDITOR")
            
            # Try fallback editors
            if not editor:
                for fallback in base_config.editor.fallback:
                    if subprocess.run(["which", fallback], capture_output=True).returncode == 0:
                        editor = fallback
                        break
            
            if not editor:
                editor = "vi"  # Last resort
    
    # Open editor
    try:
        subprocess.run([editor, str(skill.file_path)])
        click.echo(f"✓ Edited skill: {name}")
        
        # Clear cache to force reload
        cache_file = Path.home() / ".clis" / "cache" / "skill_index.json"
        if cache_file.exists():
            cache_file.unlink()
            click.echo("✓ Cleared skill cache")
    
    except Exception as e:
        click.echo(f"Error opening editor: {e}", err=True)
        sys.exit(1)


@main.command()
def list() -> None:
    """List all available skills."""
    from clis.output.formatter import OutputFormatter
    from clis.router import SkillRouter
    
    config_manager = ConfigManager()
    router = SkillRouter()
    formatter = OutputFormatter(config_manager)
    
    try:
        skills = router.scan_skills()
        skill_dicts = [skill.to_dict() for skill in skills]
        formatter.show_skill_list(skill_dicts)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.argument("name")
def validate(name: Optional[str] = None) -> None:
    """Validate skill format."""
    from clis.router import SkillRouter
    from clis.skills import SkillValidator
    
    router = SkillRouter()
    validator = SkillValidator()
    
    try:
        if name:
            skill = router.get_skill(name)
            if not skill:
                click.echo(f"Skill '{name}' not found", err=True)
                sys.exit(1)
            
            is_valid, errors = validator.validate(skill)
            if is_valid:
                click.echo(f"✓ Skill '{name}' is valid")
            else:
                click.echo(f"✗ Skill '{name}' has errors:", err=True)
                for error in errors:
                    click.echo(f"  - {error}", err=True)
                sys.exit(1)
        else:
            # Validate all skills
            skills = router.scan_skills()
            total = len(skills)
            valid = 0
            
            for skill in skills:
                is_valid, _ = validator.validate(skill)
                if is_valid:
                    valid += 1
            
            click.echo(f"Validated {total} skills: {valid} valid, {total - valid} invalid")
    
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
def doctor() -> None:
    """Check CLIS environment and configuration."""
    import platform
    from pathlib import Path
    
    click.echo("🔍 CLIS Doctor - Checking your setup...\n")
    
    # Check Python version
    py_version = platform.python_version()
    click.echo(f"✓ Python version: {py_version}")
    
    # Check platform
    os_name = get_platform()
    click.echo(f"✓ Operating system: {os_name}")
    
    # Check config directory
    config_dir = get_clis_dir()
    if config_dir.exists():
        click.echo(f"✓ Config directory: {config_dir}")
    else:
        click.echo(f"⚠️  Config directory not found: {config_dir}")
        click.echo("   Run 'clis init' to create configuration")
    
    # Check configuration files
    config_manager = ConfigManager()
    if config_manager.config_exists():
        click.echo("✓ Configuration files found")
        
        # Check LLM configuration
        try:
            llm_config = config_manager.load_llm_config()
            click.echo(f"✓ LLM provider: {llm_config.provider}")
            
            # Test LLM connection
            if llm_config.provider == "ollama":
                try:
                    response = requests.get(f"{llm_config.api.base_url}/api/tags", timeout=2)
                    if response.status_code == 200:
                        click.echo("✓ Ollama is running")
                    else:
                        click.echo("⚠️  Ollama is not responding correctly")
                except Exception:
                    click.echo("✗ Cannot connect to Ollama")
                    click.echo("   Make sure Ollama is running: https://ollama.ai/download")
            elif llm_config.api.key:
                if llm_config.api.key.startswith("${"):
                    click.echo("⚠️  API key is using environment variable (not validated)")
                else:
                    click.echo("✓ API key is configured")
            else:
                click.echo("⚠️  API key not configured")
        
        except Exception as e:
            click.echo(f"✗ Error loading LLM config: {e}")
    else:
        click.echo("✗ Configuration files not found")
        click.echo("   Run 'clis init' to create configuration")
    
    # Check skills directory
    from clis.router import SkillRouter
    
    try:
        router = SkillRouter()
        skills = router.scan_skills()
        click.echo(f"✓ Found {len(skills)} skills")
    except Exception as e:
        click.echo(f"⚠️  Error scanning skills: {e}")
    
    click.echo("\n✅ CLIS is ready to use!")
    click.echo("   Try: clis \"show system information\"")


@main.command()
@click.argument("key")
def config_get(key: str) -> None:
    """Get a configuration value."""
    config_manager = ConfigManager()
    
    try:
        value = config_manager.get_config_value(key)
        click.echo(value)
    except KeyError:
        click.echo(f"Configuration key not found: {key}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.argument("key")
@click.argument("value")
def config_set(key: str, value: str) -> None:
    """Set a configuration value."""
    config_manager = ConfigManager()
    
    try:
        config_manager.set_config_value(key, value)
        click.echo(f"✓ Set {key} = {value}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
