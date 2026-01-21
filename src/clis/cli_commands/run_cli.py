"""
Run command - Execute natural language queries.
"""

import click


@click.command()
@click.argument("query")
@click.option("--no-tool-calling", is_flag=True, help="Disable tool calling mode (use standard mode)")
@click.option("--mode", type=click.Choice(['auto', 'fast', 'plan', 'react', 'explore']), default='auto',
              help="Execution mode: auto (R1 decides), fast (quick plan-execute), plan (plan-execute), react (step-by-step), explore (exploratory)")
@click.pass_context
def run(ctx: click.Context, query: str, no_tool_calling: bool, mode: str) -> None:
    """
    Execute a natural language query.
    
    Modes:
    - auto (default): R1 analyzes task and selects optimal mode (PEVL with self-healing)
    - fast: Quick Plan-Execute with Chat (simple tasks)
    - plan: Plan-Execute mode (planning then execution)
    - react: ReAct mode (step-by-step exploration)
    - explore: Exploratory ReAct (information gathering)
    
    Examples:
        clis run "create Flask service"  # auto mode (R1 decides)
        clis run "create file" --mode=fast  # fast mode
        clis run "analyze project" --mode=explore  # exploratory
    """
    # Import here to avoid circular imports
    from clis import cli as cli_module
    
    verbose = ctx.obj.get("verbose", False)
    minimal = ctx.obj.get("minimal", False)
    debug = ctx.obj.get("debug", False)
    
    if no_tool_calling:
        # Use standard mode (single-shot)
        cli_module.execute_query(query, verbose, minimal, debug, tool_calling=False)
    elif mode == 'auto':
        # Use PEVL mode (R1 auto-select, self-healing)
        cli_module.execute_query_pevl(query, verbose, minimal, debug)
    elif mode == 'fast':
        # Use PEVL mode with fast mode override
        cli_module.execute_query_pevl(query, verbose, minimal, debug, user_mode='fast')
    elif mode == 'plan':
        # Use Plan-Execute mode (two-phase)
        cli_module.execute_query_two_phase(query, verbose, minimal, debug)
    elif mode in ['react', 'explore']:
        # Use ReAct mode (step-by-step with tools)
        cli_module.execute_query_interactive(query, verbose, minimal, debug)
    else:
        # Default: PEVL
        cli_module.execute_query_pevl(query, verbose, minimal, debug)
