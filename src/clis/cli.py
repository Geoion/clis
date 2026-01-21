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
            DeleteFileTool, EditFileTool, SearchReplaceTool, InsertCodeTool, DeleteLinesTool,
            GrepTool, ReadLintsTool, SearchFilesTool, FileTreeTool, WriteFileTool, GetFileInfoTool,
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
                DeleteFileTool(), EditFileTool(), SearchReplaceTool(), InsertCodeTool(), DeleteLinesTool(),
                GrepTool(), ReadLintsTool(), SearchFilesTool(), FileTreeTool(), WriteFileTool(), GetFileInfoTool(),
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


# Import CLI command modules
from clis.cli_commands import (
    memory_cli,
    run,
    config_cli,
    skill_cli,
    version,
    doctor,
    init,
)

# Register all command groups and commands
main.add_command(run)           # clis run
main.add_command(memory_cli)    # clis memory
main.add_command(config_cli)    # clis config
main.add_command(skill_cli)     # clis skill
main.add_command(version)       # clis version
main.add_command(doctor)        # clis doctor
main.add_command(init)          # clis init


# Note: version, init, doctor commands are now in system_cli.py
# Note: skill commands (create, edit, install, validate, test, list) are now in skill_cli.py
# Note: config commands (config, config-get, config-set) are now in config_cli.py


# =============================================================================
# REMOVED: Duplicate @main.command() definitions
# =============================================================================
# The following commands have been moved to modular CLI files:
#  - version, init, doctor → src/clis/cli/system_cli.py
#  - create, edit, install, validate, test, list → src/clis/cli/skill_cli.py  
#  - config, config-get, config-set → src/clis/cli/config_cli.py
#
# Utility functions below are kept for use by the CLI modules:
# =============================================================================


# Utility function for skill creation (used by skill_cli.py)


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
