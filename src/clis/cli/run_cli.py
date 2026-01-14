"""
Run command - Execute natural language queries.
"""

import click


@click.command()
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
    # Import here to avoid circular imports
    from clis.cli import execute_query_interactive, execute_query
    
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
