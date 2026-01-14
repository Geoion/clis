"""
CLI command definitions using Click.
"""

import sys
from typing import Any, List, Optional, Tuple

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


def execute_query_interactive(query: str, verbose: bool = False, minimal: bool = False, debug: bool = False) -> None:
    """
    Execute a query in interactive mode (step-by-step execution).
    
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
        
        # Set output level
        if debug:
            config_manager.set_config_value("output.level", "debug")
        elif verbose:
            config_manager.set_config_value("output.level", "verbose")
        elif minimal:
            config_manager.set_config_value("output.level", "minimal")
        
        formatter = OutputFormatter(config_manager)
        
        # Step 1: Load and match skills (like Claude Code Skills)
        from clis.router import SkillRouter, SkillMatcher
        from clis.agent import Agent
        
        router = SkillRouter()
        skills = router.scan_skills()
        
        matched_skill = None
        skill_instructions = None
        
        if skills:
            # Try to match a skill for this query
            llm_agent = Agent(config_manager)
            matcher = SkillMatcher(llm_agent)
            match_result = matcher.match(query, skills)
            
            if match_result:
                matched_skill, confidence = match_result
                skill_instructions = matched_skill.instructions
                
                if verbose or debug:
                    click.echo(f"✓ Matched skill: {matched_skill.name} (confidence: {confidence:.2f})")
                    if hasattr(matched_skill, 'required_tools') and matched_skill.required_tools:
                        click.echo(f"  Required tools: {', '.join(matched_skill.required_tools)}")
        
        # Step 2: Initialize tools (dynamically based on skill if matched)
        from clis.agent.interactive_agent import InteractiveAgent
        from clis.tools import (
            ListFilesTool, ReadFileTool, ExecuteCommandTool, GitStatusTool, DockerPsTool,
            DeleteFileTool, EditFileTool, GrepTool, ReadLintsTool, SearchFilesTool, FileTreeTool, WriteFileTool, GetFileInfoTool,
            GitAddTool, GitBranchTool, GitCheckoutTool, GitCommitTool, GitDiffTool, GitLogTool, GitPullTool, GitPushTool,
            DockerLogsTool, DockerInspectTool, DockerStatsTool, DockerImagesTool, DockerRmiTool,
            SystemInfoTool, CheckCommandTool, GetEnvTool, ListProcessesTool, RunTerminalCmdTool,
            HttpRequestTool, CheckPortTool
        )
        from clis.tools.registry import ToolRegistry
        
        # Build tool list based on matched skill
        if matched_skill and hasattr(matched_skill, 'required_tools') and matched_skill.required_tools:
            # Create a mapping of tool names to tool instances
            all_available_tools = {
                'list_files': ListFilesTool(),
                'read_file': ReadFileTool(),
                'execute_command': ExecuteCommandTool(),
                'git_status': GitStatusTool(),
                'docker_ps': DockerPsTool(),
                'delete_file': DeleteFileTool(),
                'edit_file': EditFileTool(),
                'grep': GrepTool(),
                'read_lints': ReadLintsTool(),
                'search_files': SearchFilesTool(),
                'file_tree': FileTreeTool(),
                'write_file': WriteFileTool(),
                'get_file_info': GetFileInfoTool(),
                'git_add': GitAddTool(),
                'git_branch': GitBranchTool(),
                'git_checkout': GitCheckoutTool(),
                'git_commit': GitCommitTool(),
                'git_diff': GitDiffTool(),
                'git_log': GitLogTool(),
                'git_pull': GitPullTool(),
                'git_push': GitPushTool(),
                'docker_logs': DockerLogsTool(),
                'docker_inspect': DockerInspectTool(),
                'docker_stats': DockerStatsTool(),
                'docker_images': DockerImagesTool(),
                'docker_rmi': DockerRmiTool(),
                'system_info': SystemInfoTool(),
                'check_command': CheckCommandTool(),
                'get_env': GetEnvTool(),
                'list_processes': ListProcessesTool(),
                'run_terminal_cmd': RunTerminalCmdTool(),
                'http_request': HttpRequestTool(),
                'check_port': CheckPortTool(),
            }
            
            # Load only the tools required by the skill
            tools = []
            for tool_name in matched_skill.required_tools:
                tool = all_available_tools.get(tool_name)
                if tool:
                    tools.append(tool)
                else:
                    if verbose or debug:
                        click.echo(f"  ⚠️  Tool '{tool_name}' not found")
            
            # Always include essential tools
            if not any(t.name == 'execute_command' for t in tools):
                tools.append(ExecuteCommandTool())
            
            if verbose or debug:
                click.echo(f"  Loaded {len(tools)} tools for skill '{matched_skill.name}'")
        else:
            # No skill matched, use all available tools
            tools = [
                ListFilesTool(), ReadFileTool(), ExecuteCommandTool(), GitStatusTool(), DockerPsTool(),
                DeleteFileTool(), EditFileTool(), GrepTool(), ReadLintsTool(), SearchFilesTool(), FileTreeTool(), WriteFileTool(), GetFileInfoTool(),
                GitAddTool(), GitBranchTool(), GitCheckoutTool(), GitCommitTool(), GitDiffTool(), GitLogTool(), GitPullTool(), GitPushTool(),
                DockerLogsTool(), DockerInspectTool(), DockerStatsTool(), DockerImagesTool(), DockerRmiTool(),
                SystemInfoTool(), CheckCommandTool(), GetEnvTool(), ListProcessesTool(), RunTerminalCmdTool(),
                HttpRequestTool(), CheckPortTool()
            ]
        
        # Configure file chunker for ReadFileTool
        llm_config = config_manager.load_llm_config()
        if llm_config.model.context.auto_chunk:
            from clis.tools.filesystem.file_chunker import FileChunker
            chunker = FileChunker.from_config(llm_config.model.context)
            for tool in tools:
                if isinstance(tool, ReadFileTool):
                    tool.set_chunker(chunker)
                    break
        
        # Step 3: Initialize interactive agent with skill context
        agent = InteractiveAgent(
            config_manager=config_manager,
            tools=tools,
            skill_instructions=skill_instructions  # Pass skill instructions
        )
        
        # Display header with rich
        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text
        from rich import box
        
        console = Console()
        
        # Header - simple and clean
        console.print(Panel(
            Text(query, style="bold cyan"),
            title="[bold blue]🤖 Task[/bold blue]",
            border_style="blue",
            box=box.ROUNDED,
            padding=(0, 1)
        ))
        console.print()
        
        # Execute interactively (ReAct: Reason → Act → Observe loop)
        step_number = 0
        iteration_number = 0
        thinking_buffer = ""  # Buffer to collect thinking content
        
        # Enable streaming thinking only in verbose/debug mode
        stream_thinking = verbose or debug
        
        try:
            for step in agent.execute(query, stream_thinking=stream_thinking):
                step_type = step.get("type")
                
                # Display step based on type
                if step_type == "iteration_start":
                    iteration_number = step.get("iteration", iteration_number + 1)
                    # Don't display anything, just track the count
                
                elif step_type == "thinking_start":
                    # Reset thinking buffer
                    thinking_buffer = ""
                    # Show thinking indicator only in verbose/debug mode
                    if verbose or debug:
                        console.print(f"\n[dim italic]💭 Reasoning (Iteration {iteration_number})...[/dim italic]")
                
                elif step_type == "thinking_chunk":
                    # Collect thinking content
                    chunk = step.get("content", "")
                    thinking_buffer += chunk
                    # Stream in verbose/debug mode only
                    if verbose or debug:
                        console.print(chunk, end="", style="dim cyan")
                
                elif step_type == "thinking_end":
                    # Show thinking end only in verbose/debug mode
                    if verbose or debug:
                        console.print()  # New line after streaming
                        # Optionally show a nice panel with the reasoning
                        if thinking_buffer.strip():
                            from rich.panel import Panel
                            from rich.markdown import Markdown
                            import re
                            
                            # Format the reasoning buffer for better display
                            formatted_reasoning = thinking_buffer.strip()
                            
                            # Try to extract and format JSON action blocks
                            action_match = re.search(r'```action\s*\n(\{.*?\})\s*\n```', formatted_reasoning, re.DOTALL)
                            if action_match:
                                import json
                                try:
                                    import builtins
                                    action_json = json.loads(action_match.group(1))
                                    # Convert JSON to readable format
                                    action_md = "\n📋 Action:\n"
                                    for key, value in action_json.items():
                                        if isinstance(value, str):
                                            # For long strings, add line breaks
                                            if len(value) > 80:
                                                action_md += f"- {key}:\n  {value}\n"
                                            else:
                                                action_md += f"- {key}: {value}\n"
                                        elif isinstance(value, (builtins.list, builtins.tuple)):
                                            # Handle lists and tuples using builtins
                                            action_md += f"- {key}: {', '.join([str(v) for v in value])}\n"
                                        elif hasattr(value, 'items'):
                                            # Handle dict-like objects
                                            action_md += f"- {key}:\n"
                                            for k, v in value.items():
                                                action_md += f"  - {k}: {v}\n"
                                        else:
                                            action_md += f"- {key}: {value}\n"
                                    
                                    # Replace original JSON with formatted markdown
                                    formatted_reasoning = formatted_reasoning[:action_match.start()] + action_md + formatted_reasoning[action_match.end():]
                                except (json.JSONDecodeError, KeyError, AttributeError):
                                    pass  # Keep original format if parsing fails
                            
                            console.print(Panel(
                                formatted_reasoning,
                                title="[dim]💡 Complete Reasoning[/dim]",
                                border_style="dim cyan",
                                padding=(0, 1),
                                box=box.ROUNDED
                            ))
                
                elif step_type == "tool_call":
                    step_number += 1
                    tool_name = step.get('tool')
                    console.print(f"\n[bold blue]🔧 Step {step_number}:[/bold blue] [cyan]{tool_name}[/cyan]")
                    params = step.get('params', {})
                    if params:
                        console.print(f"   [dim]Parameters:[/dim] [yellow]{params}[/yellow]")
                    
                    # Display risk score if available
                    risk_score = step.get('risk_score')
                    risk_level = step.get('risk_level')
                    if risk_score is not None and risk_level:
                        risk_color = {"low": "green", "medium": "yellow", "high": "red", "critical": "bold red"}.get(risk_level, "white")
                        console.print(f"   [dim]Risk:[/dim] [{risk_color}]{risk_level}[/{risk_color}] [dim]({risk_score}/100)[/dim]")
                    
                    # Check if tool requires confirmation
                    if step.get('requires_confirmation'):
                        console.print(f"   [yellow]⚠️  This operation requires confirmation[/yellow]")
                        response = click.prompt(
                            "   Approve? [y/N]",
                            type=str,
                            default="N"
                        ).lower().strip()
                        
                        approved = response in ['y', 'yes']
                        
                        if not approved:
                            # Record rejection and display
                            result = agent.execute_tool(tool_name, params, approved=False)
                            console.print(f"   [yellow]⚠️  {result['content']}[/yellow]")
                            # Agent will continue with next iteration automatically
                        else:
                            # Execute after approval
                            result = agent.execute_tool(tool_name, params, approved=True)
                            if result['success']:
                                result_preview = result['content'][:200]
                                if len(result['content']) > 200:
                                    result_preview += "..."
                                console.print(f"   [green]✓[/green] [dim]{result_preview}[/dim]")
                            else:
                                error_msg = result.get('content', 'Unknown error')
                                console.print(f"   [red]✗ Failed:[/red] [red]{error_msg}[/red]")
                
                elif step_type == "tool_result":
                    # Display result based on success flag
                    content = step.get('content', '')
                    success = step.get('success', False)
                    
                    if success:
                        result_preview = content[:200] if content else "Success"
                        if len(content) > 200:
                            result_preview += "..."
                        console.print(f"   [green]✓[/green] [dim]{result_preview}[/dim]")
                    else:
                        error_msg = content if content else "Unknown error"
                        console.print(f"   [red]✗ Failed:[/red] [red]{error_msg}[/red]")
                
                elif step_type == "command":
                    step_number += 1
                    console.print(f"\n[bold magenta]⚡ Step {step_number}:[/bold magenta] [yellow]Execute command[/yellow]")
                    console.print(f"   [dim]Command:[/dim] [white]{step['content']}[/white]")
                    
                    risk = step['risk']
                    risk_score = step.get('risk_score', 0)
                    risk_color = {"low": "green", "medium": "yellow", "high": "red", "critical": "bold red"}.get(risk, "white")
                    console.print(f"   [dim]Risk:[/dim] [{risk_color}]{risk}[/{risk_color}] [dim]({risk_score}/100)[/dim]")
                    
                    if step.get('needs_confirmation'):
                        # Ask for confirmation
                        response = click.prompt(
                            "\n    Approve? [y/N]",
                            type=str,
                            default="N"
                        ).lower().strip()
                        
                        approved = response in ['y', 'yes']
                        
                        if not approved:
                            # Record rejection and continue (don't exit)
                            result = agent.execute_command(step['content'], approved=False)
                            console.print(f"\n[yellow]⚠️  {result['content']}[/yellow]")
                            # Continue to next iteration instead of exiting
                            continue
                        
                        # Execute after approval
                        result = agent.execute_command(step['content'], approved=True)
                        if result['success']:
                            result_preview = result['content'][:200]
                            if len(result['content']) > 200:
                                result_preview += "..."
                            console.print(f"   [green]✓[/green] [dim]{result_preview}[/dim]")
                        else:
                            console.print(f"   [red]✗ Failed[/red]")
                
                elif step_type == "command_result":
                    if step['success']:
                        result_preview = step['content'][:200]
                        if len(step['content']) > 200:
                            result_preview += "..."
                        console.print(f"   [green]✓[/green] [dim]{result_preview}[/dim]")
                    else:
                        console.print(f"   [red]✗ Failed[/red]")
                
                elif step_type == "complete":
                    console.print()
                    console.print(Panel(
                        Text(step['content'], style="bold green"),
                        title="[bold green]✅ Task Completed[/bold green]",
                        border_style="green",
                        box=box.ROUNDED
                    ))
                
                elif step_type == "error":
                    console.print()
                    console.print(Panel(
                        Text(step['content'], style="bold red"),
                        title="[bold red]❌ Error[/bold red]",
                        border_style="red",
                        box=box.ROUNDED
                    ))
            
            # Summary
            console.print()
            summary = Text()
            summary.append("✅ Completed: ", style="bold green")
            summary.append(f"{step_number} actions", style="cyan")
            summary.append(" in ", style="dim")
            summary.append(f"{iteration_number} iterations", style="cyan")
            console.print(summary)
        
        except Exception as e:
            formatter.show_error(f"\n❌ Error during execution: {e}")
            if debug:
                import traceback
                traceback.print_exc()
            sys.exit(1)
        
    except KeyboardInterrupt:
        click.echo("\n⚠️  Interrupted by user", err=True)
        sys.exit(130)
    except Exception as e:
        click.echo(f"\n❌ Error: {e}", err=True)
        if debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def execute_query(query: str, verbose: bool = False, minimal: bool = False, debug: bool = False, tool_calling: bool = False) -> None:
    """
    Execute a natural language query.
    
    Args:
        query: User's natural language query
        verbose: Enable verbose output
        minimal: Enable minimal output
        debug: Enable debug output
        tool_calling: Enable tool calling mode
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
        if tool_calling:
            # Use tool calling mode
            formatter.show_info("🔧 Tool calling mode enabled...")
            commands, explanation = _execute_with_tool_calling(
                query, skill, config_manager, formatter, verbose or debug
            )
        else:
            # Use standard mode
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


# Import memory CLI commands
from clis.cli.memory_cli import memory_cli

# Add memory command group
main.add_command(memory_cli)


@main.command()
@click.argument("query")
@click.option("--no-tool-calling", is_flag=True, help="Disable tool calling mode (use standard mode)")
@click.pass_context
def run(ctx: click.Context, query: str, no_tool_calling: bool) -> None:
    """
    Execute a natural language query.
    
    Tool calling mode is enabled by default with step-by-step execution (ReAct pattern).
    Use --no-tool-calling to use standard mode (single-shot generation).
    
    Examples:
        clis run "show system information"
        clis run "commit code with message: fix bug"
        clis run "find and fix all TODOs"
        clis run "list files" --no-tool-calling
    """
    verbose = ctx.obj.get("verbose", False)
    minimal = ctx.obj.get("minimal", False)
    debug = ctx.obj.get("debug", False)
    
    # Tool calling is enabled by default (ReAct mode)
    tool_calling = not no_tool_calling
    
    if tool_calling:
        # Use ReAct mode (step-by-step with tools)
        execute_query_interactive(query, verbose, minimal, debug)
    else:
        # Use standard mode (single-shot)
        execute_query(query, verbose, minimal, debug, tool_calling=False)


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
@click.option("--auto", is_flag=True, help="Use LLM to auto-generate skill based on prompt")
@click.option("--tools", multiple=True, help="Required tools for this skill (e.g., --tools git_status --tools read_file)")
def create(name: str, auto: bool, tools: Tuple[str, ...]) -> None:
    """
    Create a new skill file.
    
    Two modes:
    1. Template mode (default): clis create "skill-name"
       Creates a basic skill template that you can edit manually.
    
    2. Auto mode: clis create "description of skill" --auto
       Uses LLM to generate a complete skill based on your description.
    
    Examples:
        clis create "my-custom-skill"
        clis create "my-skill" --tools git_status --tools read_file
        clis create "a skill to manage docker containers" --auto
    """
    from clis.agent import Agent
    from clis.utils.platform import get_skills_dir, ensure_dir
    
    config_manager = ConfigManager()
    
    # Check if config exists
    if not config_manager.config_exists():
        click.echo("⚠️  Configuration not found. Please run 'clis init' first.", err=True)
        sys.exit(1)
    
    if auto:
        # Auto mode: use LLM to generate skill
        _create_skill_with_llm(name, config_manager, list(tools))
    else:
        # Template mode: create basic template
        _create_skill_template(name, config_manager, list(tools))


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
@click.argument("source")
@click.option("--with-deps", is_flag=True, help="Download skill dependencies (templates, resources)")
def install(source: str, with_deps: bool) -> None:
    """
    Install a skill from GitHub or URL.
    
    Examples:
        clis install github.com/user/repo/skill.md
        clis install https://raw.githubusercontent.com/user/repo/main/skill.md
        clis install user/repo  # Will scan for *.md files
        clis install --with-deps user/repo/skill.md  # Include dependencies
    """
    import re
    from pathlib import Path
    from urllib.parse import urlparse
    
    from clis.utils.platform import ensure_dir, get_skills_dir
    
    click.echo(f"📦 Installing skill from: {source}")
    
    # Parse source
    if source.startswith("http://") or source.startswith("https://"):
        # Direct URL - convert GitHub web URL to raw URL if needed
        if "github.com" in source and "/blob/" in source:
            # Convert: https://github.com/user/repo/blob/branch/path/file.md
            # To: https://raw.githubusercontent.com/user/repo/branch/path/file.md
            url = source.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
            click.echo(f"Converted to raw URL: {url}")
        else:
            url = source
    elif source.startswith("github.com/") or "/" in source:
        # GitHub shorthand
        if source.startswith("github.com/"):
            source = source[11:]  # Remove "github.com/"
        
        # Parse GitHub path
        parts = source.split("/")
        if len(parts) < 2:
            click.echo("Invalid GitHub path. Format: user/repo or user/repo/path/to/skill.md", err=True)
            sys.exit(1)
        
        user, repo = parts[0], parts[1]
        path = "/".join(parts[2:]) if len(parts) > 2 else ""
        
        if path and path.endswith(".md"):
            # Direct file
            url = f"https://raw.githubusercontent.com/{user}/{repo}/main/{path}"
        else:
            # Repository - scan for skills
            click.echo(f"Scanning repository: {user}/{repo}")
            url = f"https://api.github.com/repos/{user}/{repo}/contents/{path}"
            
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                
                files = response.json()
                md_files = [f for f in files if f["name"].endswith(".md")]
                
                if not md_files:
                    click.echo("No .md files found in repository", err=True)
                    sys.exit(1)
                
                click.echo(f"\nFound {len(md_files)} skill file(s):")
                for i, f in enumerate(md_files, 1):
                    click.echo(f"  {i}. {f['name']}")
                
                if len(md_files) == 1:
                    selected = 0
                else:
                    choice = click.prompt(
                        "\nSelect file to install",
                        type=click.IntRange(1, len(md_files)),
                        default=1,
                    )
                    selected = choice - 1
                
                url = md_files[selected]["download_url"]
                click.echo(f"\nInstalling: {md_files[selected]['name']}")
            
            except Exception as e:
                click.echo(f"Error accessing GitHub: {e}", err=True)
                sys.exit(1)
    else:
        click.echo("Invalid source. Use: github.com/user/repo or https://...", err=True)
        sys.exit(1)
    
    # Download skill file
    try:
        click.echo(f"Downloading from: {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        content = response.text
        
        # Parse skill to get name
        from clis.skills.parser import SkillParser
        from clis.skills.validator import SkillValidator
        
        parser = SkillParser()
        validator = SkillValidator()
        
        skill = parser.parse_content(content)
        
        # Validate skill
        is_valid, errors = validator.validate(skill)
        if not is_valid:
            click.echo("\n⚠️  Skill validation failed:", err=True)
            for error in errors:
                click.echo(f"  - {error}", err=True)
            
            if not click.confirm("\nInstall anyway?", default=False):
                click.echo("Installation cancelled.")
                return
        
        # Save skill
        custom_dir = get_skills_dir() / "custom"
        ensure_dir(custom_dir)
        
        # Generate filename from skill name
        filename = re.sub(r"[^\w\s-]", "", skill.name.lower())
        filename = re.sub(r"[-\s]+", "-", filename)
        skill_path = custom_dir / f"{filename}.md"
        
        if skill_path.exists():
            if not click.confirm(f"\n⚠️  Skill '{skill.name}' already exists. Overwrite?", default=False):
                click.echo("Installation cancelled.")
                return
        
        with open(skill_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        click.echo(f"\n✓ Skill installed: {skill.name}")
        click.echo(f"  Location: {skill_path}")
        
        # Check for dependencies (templates, resources)
        dependencies_found = []
        if "templates/" in content or "resources/" in content:
            # Extract referenced files
            import re
            file_refs = re.findall(r'["\']([^"\']*(?:templates|resources)/[^"\']+)["\']', content)
            
            if file_refs and with_deps:
                click.echo("\n📦 Downloading dependencies...")
                
                # Try to download dependencies
                for ref in set(file_refs):
                    try:
                        # Construct URL for dependency
                        # Assume same repo structure
                        if url.startswith("https://raw.githubusercontent.com/"):
                            # Extract repo info
                            parts = url.replace("https://raw.githubusercontent.com/", "").split("/")
                            if len(parts) >= 3:
                                user, repo, branch = parts[0], parts[1], parts[2]
                                # Get the directory of the skill file
                                skill_dir = "/".join(url.split("/")[:-1])
                                dep_url = f"{skill_dir}/{ref}"
                                
                                click.echo(f"  Downloading: {ref}")
                                dep_response = requests.get(dep_url, timeout=10)
                                if dep_response.status_code == 200:
                                    # Save dependency file
                                    dep_path = skill_path.parent / ref
                                    ensure_dir(dep_path.parent)
                                    with open(dep_path, "w", encoding="utf-8") as f:
                                        f.write(dep_response.text)
                                    click.echo(f"    ✓ Saved: {dep_path}")
                                    dependencies_found.append(ref)
                                else:
                                    click.echo(f"    ⚠️  Not found: {ref}")
                    except Exception as e:
                        click.echo(f"    ⚠️  Failed to download {ref}: {e}")
                
                if dependencies_found:
                    click.echo(f"\n✓ Downloaded {len(dependencies_found)} dependencies")
            
            elif file_refs and not with_deps:
                click.echo("\n⚠️  This skill requires additional files (templates/resources)")
                click.echo("   The skill references external files that were not downloaded.")
                click.echo("\n   Referenced files:")
                for ref in set(file_refs):
                    click.echo(f"     - {ref}")
                click.echo("\n   To download dependencies:")
                click.echo(f"     clis install --with-deps {source}")
                click.echo("\n   Or manually:")
                click.echo("     1. Clone the repository to get all files")
                click.echo("     2. Copy files to the skill directory")
        
        # Clear cache
        cache_file = Path.home() / ".clis" / "cache" / "skill_index.json"
        if cache_file.exists():
            cache_file.unlink()
        
        click.echo("\n✓ Skill cache cleared")
        click.echo("\nNext steps:")
        click.echo(f"  1. Validate: clis validate {skill.name}")
        
        if dependencies_found or "templates/" in content or "resources/" in content:
            click.echo(f"  2. Review dependencies: clis edit {skill.name}")
            click.echo(f"  3. Use it: clis run \"[your query]\"")
        else:
            click.echo(f"  2. Use it: clis run \"[your query]\"")
    
    except requests.exceptions.RequestException as e:
        click.echo(f"\n❌ Download failed: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"\n❌ Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.argument("name")
def validate(name: str) -> None:
    """
    Validate a skill file.
    
    Checks:
    - Skill file format and structure
    - Required sections (name, description, instructions)
    - JSON examples syntax
    - Safety rules format
    - Tool references (if any)
    
    Examples:
        clis validate git
        clis validate my-custom-skill
    """
    from clis.router import SkillRouter
    from clis.skills.validator import SkillValidator
    
    router = SkillRouter()
    validator = SkillValidator()
    
    # Load skill
    skill = router.get_skill(name)
    
    if not skill:
        click.echo(f"❌ Skill '{name}' not found", err=True)
        click.echo("\nAvailable skills:")
        skills = router.scan_skills()
        for s in skills:
            click.echo(f"  - {s.name}")
        sys.exit(1)
    
    click.echo(f"🔍 Validating skill: {skill.name}")
    click.echo(f"   Location: {skill.file_path}")
    click.echo()
    
    # Validate
    is_valid, errors = validator.validate(skill)
    
    if is_valid:
        click.echo("✅ Skill is valid!")
        click.echo()
        click.echo("Skill details:")
        click.echo(f"  Name: {skill.name}")
        click.echo(f"  Description: {skill.description[:100]}..." if len(skill.description) > 100 else f"  Description: {skill.description}")
        
        if hasattr(skill, 'required_tools') and skill.required_tools:
            click.echo(f"  Required tools: {', '.join(skill.required_tools)}")
        
        if skill.safety_rules:
            click.echo(f"  Safety rules: {len(skill.safety_rules)} rule(s)")
        
        if skill.platform_compatibility:
            click.echo(f"  Platform support: {', '.join(skill.platform_compatibility.keys())}")
    else:
        click.echo("❌ Skill validation failed:")
        click.echo()
        for error in errors:
            click.echo(f"  - {error}")
        click.echo()
        click.echo(f"💡 Fix the errors and run: clis validate {name}")
        sys.exit(1)


@main.command()
@click.argument("name")
@click.argument("query", required=False)
@click.option("--dry-run", is_flag=True, help="Show what would be executed without running")
def test(name: str, query: Optional[str], dry_run: bool) -> None:
    """
    Test a skill with a sample query.
    
    This command helps you test if a skill works correctly by:
    1. Loading the skill
    2. Generating commands based on your query
    3. Optionally executing the commands (or showing them with --dry-run)
    
    Examples:
        clis test git "show status"
        clis test docker "list containers" --dry-run
        clis test my-skill  # Will prompt for query
    """
    from clis.router import SkillRouter, SkillMatcher
    from clis.agent import Agent
    
    config_manager = ConfigManager()
    
    # Check if config exists
    if not config_manager.config_exists():
        click.echo("⚠️  Configuration not found. Please run 'clis init' first.", err=True)
        sys.exit(1)
    
    router = SkillRouter()
    agent = Agent(config_manager)
    
    # Load skill
    skill = router.get_skill(name)
    
    if not skill:
        click.echo(f"❌ Skill '{name}' not found", err=True)
        sys.exit(1)
    
    # Get query
    if not query:
        query = click.prompt("Enter test query")
    
    click.echo(f"🧪 Testing skill: {skill.name}")
    click.echo(f"   Query: {query}")
    click.echo()
    
    try:
        # Build system prompt
        system_prompt = f"""
You are executing the "{skill.name}" skill.

{skill.instructions}

Generate commands based on the user's request.
"""
        
        # Generate commands
        click.echo("🤖 Generating commands...")
        response = agent.generate_json(query, system_prompt)
        
        commands = response.get("commands", [])
        explanation = response.get("explanation", "")
        
        if not commands:
            click.echo("⚠️  No commands generated", err=True)
            sys.exit(1)
        
        click.echo()
        click.echo("📋 Generated commands:")
        for i, cmd in enumerate(commands, 1):
            click.echo(f"  {i}. {cmd}")
        
        click.echo()
        click.echo(f"💡 Explanation: {explanation}")
        
        if dry_run:
            click.echo()
            click.echo("✅ Dry-run mode: Commands not executed")
        else:
            click.echo()
            if click.confirm("Execute these commands?", default=False):
                from clis.executor import CommandExecutor
                executor = CommandExecutor(config_manager)
                
                for i, cmd in enumerate(commands, 1):
                    click.echo(f"\n▶️  Executing command {i}/{len(commands)}: {cmd}")
                    result = executor.execute(cmd)
                    
                    if result.success:
                        click.echo(f"✅ Success")
                        if result.output:
                            click.echo(result.output)
                    else:
                        click.echo(f"❌ Failed: {result.error}")
                        if not click.confirm("Continue with next command?", default=True):
                            break
            else:
                click.echo("Test cancelled.")
    
    except Exception as e:
        click.echo(f"\n❌ Test failed: {e}", err=True)
        import traceback
        if config_manager.load_base_config().output.level == "debug":
            traceback.print_exc()
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
def config() -> None:
    """Show all configuration values in a table."""
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    
    config_manager = ConfigManager()
    console = Console()
    
    try:
        # Load all configs
        base_config = config_manager.load_base_config()
        llm_config = config_manager.load_llm_config()
        safety_config = config_manager.load_safety_config()
        
        def mask_sensitive(key: str, value: str) -> str:
            """
            Mask sensitive values (show only first and last 4 characters).
            Only masks API keys.
            """
            # Only mask API keys
            if "api.key" in key.lower() or key.lower().endswith(".key"):
                if value and len(value) > 8:
                    return f"{value[:4]}{'*' * (len(value) - 8)}{value[-4:]}"
                elif value:
                    return "*" * len(value)
            return value
        
        def flatten_config(obj: Any, prefix: str = "") -> List[Tuple[str, str]]:
            """Flatten nested config object to key-value pairs."""
            items = []
            
            if hasattr(obj, "__dict__"):
                for key, value in obj.__dict__.items():
                    if key.startswith("_"):
                        continue
                    
                    full_key = f"{prefix}.{key}" if prefix else key
                    
                    # Check if value has nested attributes
                    if hasattr(value, "__dict__") and not isinstance(value, type):
                        items.extend(flatten_config(value, full_key))
                    # Check if value is a list or tuple using type name
                    elif type(value).__name__ in ('list', 'tuple'):
                        items.append((full_key, ", ".join(str(v) for v in value)))
                    elif value is not None:
                        items.append((full_key, str(value)))
            
            return items
        
        # Collect all config items
        all_items = []
        all_items.extend(flatten_config(base_config, "base"))
        all_items.extend(flatten_config(llm_config, "llm"))
        all_items.extend(flatten_config(safety_config, "safety"))
        
        # Create rich table
        table = Table(
            title="📋 CLIS Configuration",
            title_style="bold cyan",
            show_header=True,
            header_style="bold magenta",
            border_style="bright_blue",
            show_lines=False,
            expand=True,
            padding=(0, 1),
        )
        
        table.add_column("Category", style="cyan", no_wrap=True, width=12, justify="left")
        table.add_column("Key", style="green", no_wrap=False, min_width=25)
        table.add_column("Value", style="yellow", no_wrap=False, min_width=30)
        
        # Group items by category
        for key, value in sorted(all_items):
            masked_value = mask_sensitive(key, value)
            is_masked = masked_value != value
            
            # Extract category and key parts
            parts = key.split(".", 1)
            if len(parts) == 2:
                category, sub_key = parts
            else:
                category = "other"
                sub_key = key
            
            # Color category
            if category == "base":
                category_style = "[bold blue]base[/]"
            elif category == "llm":
                category_style = "[bold green]llm[/]"
            elif category == "safety":
                category_style = "[bold red]safety[/]"
            else:
                category_style = category
            
            # Style the value based on type
            if masked_value.lower() in ("true", "false"):
                value_style = f"[bold {'bright_green' if masked_value.lower() == 'true' else 'bright_red'}]{masked_value}[/]"
            elif is_masked:
                # API key is masked
                value_style = f"[bold red]{masked_value}[/] [dim]🔒[/]"
            elif masked_value.isdigit() or (masked_value.replace(".", "", 1).isdigit() and masked_value.count(".") <= 1):
                value_style = f"[bright_cyan]{masked_value}[/]"
            elif not masked_value:
                value_style = "[dim italic]<empty>[/]"
            else:
                value_style = f"[white]{masked_value}[/]"
            
            table.add_row(category_style, sub_key, value_style)
        
        # Print table
        console.print()
        console.print(table)
        console.print()
        
        # Print summary and tips in a panel
        tips_text = Text()
        tips_text.append("💡 ", style="bold yellow")
        tips_text.append("Usage Tips\n\n", style="bold cyan")
        tips_text.append("• ", style="bold")
        tips_text.append("Get config: ", style="bold green")
        tips_text.append("clis config-get <key>\n", style="dim")
        tips_text.append("  Example: ", style="dim")
        tips_text.append("clis config-get api.key\n\n", style="cyan")
        tips_text.append("• ", style="bold")
        tips_text.append("Set config: ", style="bold green")
        tips_text.append("clis config-set <key> <value>\n", style="dim")
        tips_text.append("  Example: ", style="dim")
        tips_text.append("clis config-set output.level verbose\n\n", style="cyan")
        tips_text.append("• ", style="bold")
        tips_text.append("Note: ", style="bold yellow")
        tips_text.append("Keys in the table don't include Category prefix\n", style="dim")
        tips_text.append("  Use keys without Category when using config-get/set\n", style="dim")
        tips_text.append("  For example, use ", style="dim")
        tips_text.append("api.key", style="cyan")
        tips_text.append(" instead of ", style="dim")
        tips_text.append("llm.api.key\n\n", style="cyan")
        tips_text.append("🔒 ", style="bold red")
        tips_text.append("API Key is masked (only first and last 4 characters shown)", style="dim")
        
        panel = Panel(
            tips_text,
            border_style="green",
            padding=(1, 2),
        )
        console.print(panel)
        
        # Print summary
        console.print(f"[bold]Total:[/] [cyan]{len(all_items)}[/] configuration items", justify="center")
        console.print()
    
    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        sys.exit(1)


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


def _create_skill_template(name: str, config_manager: ConfigManager, tools: Optional[List[str]] = None) -> None:
    """
    Create a basic skill template (direct mode).
    
    Args:
        name: Skill name
        config_manager: Configuration manager instance
        tools: Optional list of required tools
    """
    from pathlib import Path
    from clis.utils.platform import get_skills_dir, ensure_dir
    
    # Generate filename from skill name
    import re
    filename = re.sub(r"[^\w\s-]", "", name.lower())
    filename = re.sub(r"[-\s]+", "-", filename)
    
    # Check if skill already exists
    skill_path = get_skills_dir() / "custom" / f"{filename}.md"
    if skill_path.exists():
        if not click.confirm(f"⚠️  Skill '{filename}' already exists. Overwrite?", default=False):
            click.echo("Cancelled.")
            return
    
    click.echo(f"📝 Creating skill template: {name}")
    if tools:
        click.echo(f"   Required tools: {', '.join(tools)}")
    click.echo()
    
    # Create YAML front matter if tools are specified
    yaml_header = ""
    if tools:
        yaml_header = f"""---
name: {name}
description: [Brief description of this skill's functionality]
tools:
{chr(10).join(f'  - {tool}' for tool in tools)}
---

"""
    
    # Create basic skill template
    template = f"""{yaml_header}# Skill Name: {name}

## Description
[Brief description of this skill's functionality]

## Instructions
You are a {name} assistant. Generate appropriate commands based on user requirements.

1. **Analyze user requirements**:
   - [Requirement type 1]: Use [command/tool]
   - [Requirement type 2]: Use [command/tool]
   - [Requirement type 3]: Use [command/tool]

2. **Platform adaptation**:
   - macOS: [macOS specific instructions]
   - Linux: [Linux specific instructions]
   - Windows: [Windows specific instructions]

3. **Generate commands**:
   - Return JSON format: `{{"commands": [...], "explanation": "..."}}`
   - Provide clear explanations
   - Ensure commands are safe and reliable

## Examples

**User input**: [Example input 1]

**AI output**:
```json
{{
  "commands": [
    "command1",
    "command2"
  ],
  "explanation": "Command explanation"
}}
```

**User input**: [Example input 2]

**AI output**:
```json
{{
  "commands": [
    "command3"
  ],
  "explanation": "Command explanation"
}}
```

## Safety Rules (CLIS Extension)
- Allow: [Allowed operation types]
- Forbid: [Forbidden operation types]
- Require confirmation: [Operations requiring confirmation]

## Platform Compatibility (CLIS Extension)
- windows: [Windows platform instructions]
- macos: [macOS platform instructions]
- linux: [Linux platform instructions]

## Dry-Run Mode (CLIS Extension)
false
"""
    
    try:
        # Save skill file
        ensure_dir(skill_path.parent)
        with open(skill_path, "w", encoding="utf-8") as f:
            f.write(template)
        
        click.echo(f"✓ Skill template created: {skill_path}")
        click.echo()
        click.echo("Next steps:")
        click.echo(f"  1. Edit the template: clis edit {filename}")
        click.echo(f"  2. Validate: clis validate {filename}")
        click.echo(f"  3. Test: clis test {filename} \"your test query\"")
        click.echo(f"  4. Use it: clis run \"[your query]\"")
        click.echo()
        click.echo("💡 Tip: Use 'clis create \"description\" --auto' to generate with AI")
    
    except Exception as e:
        click.echo(f"\n❌ Error: {e}", err=True)
        sys.exit(1)


def _create_skill_with_llm(prompt: str, config_manager: ConfigManager, tools: Optional[List[str]] = None) -> None:
    """
    Create a skill using LLM (auto mode).
    
    Args:
        prompt: User's description/prompt for the skill
        config_manager: Configuration manager instance
        tools: Optional list of required tools
    """
    from pathlib import Path
    from clis.agent import Agent
    from clis.utils.platform import get_skills_dir, ensure_dir
    
    click.echo(f"🤖 Generating skill from prompt: {prompt}")
    click.echo()
    
    # Generate skill template using LLM
    try:
        agent = Agent(config_manager)
        
        tools_section = ""
        if tools:
            tools_section = f"""
If tools are specified, add YAML front matter at the beginning:
---
name: [Skill Name]
description: [Brief description]
tools:
{chr(10).join(f'  - {tool}' for tool in tools)}
---

"""
        
        system_prompt = f"""
You are a skill template generator for CLIS (Command Line Interface Skills).
Generate a complete skill file in Markdown format based on the user's description.

{tools_section}The skill MUST follow this exact format:

# Skill Name: [Descriptive Name]

## Description
[Brief description in English]

## Instructions
You are a [skill type] assistant. Generate appropriate commands based on user requirements.

1. **Analyze user requirements**:
   - [Requirement type 1]: Use [command/tool]
   - [Requirement type 2]: Use [command/tool]
   - [Requirement type 3]: Use [command/tool]

2. **Platform adaptation**:
   - macOS: [macOS specific instructions]
   - Linux: [Linux specific instructions]
   - Windows: [Windows specific instructions]

3. **Generate commands**:
   - Return JSON format: `{{"commands": [...], "explanation": "..."}}`
   - Provide clear explanations
   - Ensure commands are safe and reliable

## Examples

**User input**: [realistic example input]

**AI output**:
```json
{{
  "commands": [
    "command1",
    "command2"
  ],
  "explanation": "Command explanation"
}}
```

[Add 2-3 more examples]

## Safety Rules (CLIS Extension)
- Allow: [Allowed operation types]
- Forbid: [Forbidden dangerous operations]
- Require confirmation: [Operations requiring confirmation]

## Platform Compatibility (CLIS Extension)
- windows: [Windows platform specific instructions]
- macos: [macOS platform specific instructions]
- linux: [Linux platform specific instructions]

## Dry-Run Mode (CLIS Extension)
[true/false - true if commands should be tested without execution first]

IMPORTANT:
1. Generate complete, production-ready content
2. Use English for descriptions and explanations
3. Provide realistic, practical examples
4. Include proper safety rules
5. Consider cross-platform compatibility
6. Make instructions clear and actionable
"""
        
        tools_info = ""
        if tools:
            tools_info = f"\n\nRequired tools for this skill: {', '.join(tools)}"
        
        user_prompt = f"""
Generate a complete CLIS skill based on this description:

{prompt}{tools_info}

Generate the complete skill file content following the template format exactly.
"""
        
        click.echo("⏳ Calling LLM to generate skill...")
        skill_content = agent.generate(user_prompt, system_prompt, inject_context=False)
        
        # Clean up the response (remove markdown code blocks if present)
        if "```markdown" in skill_content:
            start = skill_content.find("```markdown") + 11
            end = skill_content.rfind("```")
            skill_content = skill_content[start:end].strip()
        elif "```" in skill_content:
            start = skill_content.find("```") + 3
            end = skill_content.rfind("```")
            skill_content = skill_content[start:end].strip()
        
        # Extract skill name from generated content
        import re
        name_match = re.search(r"^#\s+(?:Skill Name:\s+)?(.+)$", skill_content, re.MULTILINE)
        if name_match:
            skill_name = name_match.group(1).strip()
        else:
            skill_name = "Generated Skill"
        
        # Generate filename
        filename = re.sub(r"[^\w\s-]", "", skill_name.lower())
        filename = re.sub(r"[-\s]+", "-", filename)
        
        # Check if skill already exists
        skill_path = get_skills_dir() / "custom" / f"{filename}.md"
        if skill_path.exists():
            if not click.confirm(f"\n⚠️  Skill '{filename}' already exists. Overwrite?", default=False):
                click.echo("Cancelled.")
                return
        
        # Save skill file
        ensure_dir(skill_path.parent)
        with open(skill_path, "w", encoding="utf-8") as f:
            f.write(skill_content)
        
        click.echo()
        click.echo(f"✓ Skill generated: {skill_name}")
        click.echo(f"✓ Saved to: {skill_path}")
        click.echo()
        click.echo("Next steps:")
        click.echo(f"  1. Review and edit: clis edit {filename}")
        click.echo(f"  2. Validate: clis validate {filename}")
        click.echo(f"  3. Use it: clis run \"[your query]\"")
    
    except Exception as e:
        click.echo(f"\n❌ Error: {e}", err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


def _execute_with_tool_calling(
    query: str,
    skill: Any,
    config_manager: ConfigManager,
    formatter: Any,
    show_tool_calls: bool = False
) -> Tuple[List[str], str]:
    """
    Execute query with tool calling mode.
    
    Args:
        query: User query
        skill: Matched skill
        config_manager: Configuration manager
        formatter: Output formatter
        show_tool_calls: Whether to show tool call details
        
    Returns:
        Tuple of (commands, explanation)
    """
    from clis.agent.tool_calling import ToolCallingAgent
    from clis.tools import (
        # Phase 0: Built-in
        ListFilesTool,
        ReadFileTool,
        GitStatusTool,
        DockerPsTool,
        # Phase 1: Core Tools
        SearchFilesTool,
        GitDiffTool,
        FileTreeTool,
        HttpRequestTool,
        DockerLogsTool,
        # Phase 2: Important Tools
        WriteFileTool,
        SystemInfoTool,
        GitLogTool,
        CheckCommandTool,
        # Phase 3: Enhanced Tools
        GetEnvTool,
        ListProcessesTool,
        CheckPortTool,
        DockerInspectTool,
        DockerStatsTool,
        GetFileInfoTool,
        # ExecuteCommandTool is risky, not included by default
    )
    
    # Initialize tools
    tools = [
        # Phase 0: Built-in (basic file and status tools)
        ListFilesTool(),
        ReadFileTool(),
        GitStatusTool(),
        DockerPsTool(),
        # Phase 1: Core Tools (high value, low risk)
        SearchFilesTool(),
        GitDiffTool(),
        FileTreeTool(),
        HttpRequestTool(),
        DockerLogsTool(),
        # Phase 2: Important Tools
        SystemInfoTool(),
        GitLogTool(),
        CheckCommandTool(),
        # Phase 3: Enhanced Tools (read-only, safe)
        GetEnvTool(),
        ListProcessesTool(),
        CheckPortTool(),
        DockerInspectTool(),
        DockerStatsTool(),
        GetFileInfoTool(),
        # WriteFileTool() is excluded by default (needs user confirmation)
        # ExecuteCommandTool() is excluded by default (risky)
    ]
    
    # Create tool calling agent
    tool_agent = ToolCallingAgent(
        config_manager=config_manager,
        tools=tools,
        max_iterations=10
    )
    
    # Build system prompt
    system_prompt = f"""
You are executing the "{skill.name}" skill.

{skill.instructions}

Generate commands based on the user's request.
"""
    
    # Execute with tools
    formatter.show_info("🔧 Calling tools to gather information...")
    
    commands, explanation, tool_calls_history = tool_agent.execute_with_tools(
        query=query,
        system_prompt=system_prompt,
        skill_name=skill.name
    )
    
    # Show tool calls if requested
    if show_tool_calls and tool_calls_history:
        formatter.show_info(f"\n📋 Tool calls made: {len(tool_calls_history)}")
        for i, call in enumerate(tool_calls_history, 1):
            status = "✓" if call["success"] else "✗"
            formatter.show_info(f"  {status} {i}. {call['tool']}({call['parameters']})")
            if show_tool_calls:
                if call["success"]:
                    output_preview = call["output"][:100] + "..." if len(call["output"]) > 100 else call["output"]
                    formatter.show_info(f"     Output: {output_preview}")
                else:
                    formatter.show_info(f"     Error: {call['error']}")
    
    return commands, explanation


if __name__ == "__main__":
    main()
