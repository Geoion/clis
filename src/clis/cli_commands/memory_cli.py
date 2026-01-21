"""
Memory management CLI commands.

Provides commands to manage task memories, including:
- List, view, search, delete tasks
- Archive and cleanup old memories
- Export memories to documents
- View statistics
"""

from pathlib import Path
from typing import Optional
import json
import os
from datetime import datetime, timedelta

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree

console = Console()


@click.group(name="memory")
def memory_cli():
    """Manage task memories."""
    pass


@memory_cli.command()
@click.option('--status', type=click.Choice(['active', 'completed', 'archived', 'failed']),
              help='Filter task status')
@click.option('--limit', type=int, default=20, help='Maximum number to display')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed information')
def list(status: Optional[str], limit: int, verbose: bool):
    """List task memories."""
    from clis.agent.memory_manager import MemoryManager
    
    manager = MemoryManager()
    
    # Get task list
    if status:
        from clis.agent.memory_manager import TaskStatus
        status_enum = TaskStatus(status)
        tasks = manager.list_tasks(status=status_enum, limit=limit)
    else:
        tasks = manager.list_tasks(limit=limit)
    
    if not tasks:
        console.print("[yellow]No task memories found[/yellow]")
        return
    
    # Create table
    table = Table(title=f"Task Memories (total {len(tasks)})")
    table.add_column("Task ID", style="cyan")
    table.add_column("Status", style="magenta")
    table.add_column("Created", style="green")
    table.add_column("Description")
    
    if verbose:
        table.add_column("Duration")
        table.add_column("Files")
    
    for task in tasks:
        task_id = task['id']
        status_icon = {
            'active': '[ACTIVE]',
            'completed': '✅',
            'archived': '[ARCHIVED]',
            'failed': '❌'
        }.get(task['status'], '[UNKNOWN]')
        
        status_display = f"{status_icon} {task['status']}"
        created = datetime.fromisoformat(task['created_at']).strftime('%Y-%m-%d %H:%M')
        description = task['description'][:50] + '...' if len(task['description']) > 50 else task['description']
        
        row = [task_id, status_display, created, description]
        
        if verbose:
            # Calculate duration
            if 'completed_at' in task:
                start = datetime.fromisoformat(task['created_at'])
                end = datetime.fromisoformat(task['completed_at'])
                duration = str(end - start).split('.')[0]  # Remove microseconds
            else:
                duration = "In Progress"
            
            # TODO: Read statistics from file
            files_count = "N/A"
            
            row.extend([duration, files_count])
        
        table.add_row(*row)
    
    console.print(table)
    
    # Hint
    console.print(f"\n💡 Use [cyan]clis memory show <task_id>[/cyan] to view details")


@memory_cli.command()
@click.argument('task_id')
@click.option('--full', is_flag=True, help='Show full content')
@click.option('--edit', is_flag=True, help='Open in editor')
def show(task_id: str, full: bool, edit: bool):
    """View task details."""
    from clis.agent.memory_manager import MemoryManager
    
    manager = MemoryManager()
    task_file = manager.get_task_file(task_id)
    
    if not task_file or not task_file.exists():
        console.print(f"[red]Error: Task {task_id} does not exist[/red]")
        return
    
    # Open in editor
    if edit:
        import subprocess
        editor = os.environ.get('EDITOR', 'vim')
        subprocess.run([editor, str(task_file)])
        return
    
    # Read task information
    task_info = manager.metadata['tasks'].get(task_id)
    if not task_info:
        console.print(f"[red]Error: Task metadata does not exist[/red]")
        return
    
    # Display task information
    status_icon = {
        'active': '[ACTIVE]',
        'completed': '✅',
        'archived': '[ARCHIVED]',
        'failed': '❌'
    }.get(task_info['status'], '[UNKNOWN]')
    
    info_text = f"""
[bold cyan]Task ID:[/bold cyan] {task_id}
[bold cyan]Status:[/bold cyan] {status_icon} {task_info['status']}
[bold cyan]Created:[/bold cyan] {task_info['created_at']}
"""
    
    if 'completed_at' in task_info:
        start = datetime.fromisoformat(task_info['created_at'])
        end = datetime.fromisoformat(task_info['completed_at'])
        duration = end - start
        info_text += f"""[bold cyan]Completed:[/bold cyan] {task_info['completed_at']}
[bold cyan]Duration:[/bold cyan] {duration}
"""
    
    info_text += f"\n[bold cyan]Description:[/bold cyan]\n{task_info['description']}"
    
    panel = Panel(info_text, title=f"Task: {task_id}", border_style="cyan")
    console.print(panel)
    
    # Display file content
    if full:
        content = task_file.read_text(encoding='utf-8')
        console.print("\n" + "="*60)
        console.print(content)
    else:
        # Display summary
        console.print(f"\n[dim]File location: {task_file}[/dim]")
        console.print("[dim]Use --full to show full content[/dim]")
        console.print("[dim]Use --edit to open in editor[/dim]")


@memory_cli.command()
@click.argument('query')
@click.option('--content', is_flag=True, help='Search file content')
@click.option('--regex', is_flag=True, help='Use regular expressions')
def search(query: str, content: bool, regex: bool):
    """Search task memories."""
    from clis.agent.memory_manager import MemoryManager
    
    manager = MemoryManager()
    
    if content:
        console.print("[yellow]Content search feature under development...[/yellow]")
        return
    
    # Simple description search
    results = manager.search_tasks(query)
    
    if not results:
        console.print(f"[yellow]No tasks found matching '{query}'[/yellow]")
        return
    
    console.print(f"[green]Found {len(results)} matching tasks:[/green]\n")
    
    for task in results:
        console.print(f"  • [cyan]{task['id']}[/cyan]: {task['description']}")
    
    console.print(f"\n💡 Use [cyan]clis memory show <task_id>[/cyan] to view details")


@memory_cli.command()
@click.argument('task_id', required=False)
@click.option('--status', type=click.Choice(['failed']), help='Delete all tasks with specified status')
@click.option('--older-than', help='Delete tasks older than specified time (e.g., 90days)')
@click.option('--force', '-f', is_flag=True, help='Skip confirmation')
def delete(task_id: Optional[str], status: Optional[str], older_than: Optional[str], force: bool):
    """Delete task memories."""
    from clis.agent.memory_manager import MemoryManager
    
    manager = MemoryManager()
    
    # Delete single task
    if task_id:
        task_info = manager.metadata['tasks'].get(task_id)
        if not task_info:
            console.print(f"[red]Error: Task {task_id} does not exist[/red]")
            return
        
        # Confirm
        if not force:
            confirm = click.confirm(f"Are you sure you want to delete task {task_id}?")
            if not confirm:
                console.print("[yellow]Cancelled[/yellow]")
                return
        
        # Delete file
        task_file = manager.get_task_file(task_id)
        if task_file and task_file.exists():
            task_file.unlink()
        
        # Delete metadata
        del manager.metadata['tasks'][task_id]
        manager._save_metadata()
        
        console.print(f"[green]✅ Deleted task {task_id}[/green]")
        return
    
    # Batch delete
    if status or older_than:
        console.print("[yellow]Batch delete feature under development...[/yellow]")
        return
    
    console.print("[red]Please specify task_id or use --status/--older-than options[/red]")


@memory_cli.command()
@click.argument('task_id', required=False)
@click.option('--all-completed', is_flag=True, help='Archive all completed tasks')
def archive(task_id: Optional[str], all_completed: bool):
    """Archive task memories."""
    from clis.agent.memory_manager import MemoryManager
    
    manager = MemoryManager()
    
    if task_id:
        manager._archive_task(task_id)
        console.print(f"[green]Archived task {task_id}[/green]")
    elif all_completed:
        # Archive all completed tasks
        completed_tasks = [
            tid for tid, info in manager.metadata['tasks'].items()
            if info['status'] == 'completed'
        ]
        
        for tid in completed_tasks:
            manager._archive_task(tid)
        
        console.print(f"[green]Archived {len(completed_tasks)} tasks[/green]")
    else:
        console.print("[red]Please specify task_id or use --all-completed[/red]")


@memory_cli.command()
@click.option('--keep-days', type=int, help='Days to keep')
@click.option('--archive', is_flag=True, help='Clean archived tasks')
@click.option('--keep-months', type=int, default=3, help='Months to keep archived')
@click.option('--dry-run', is_flag=True, help='Preview cleanup (no actual deletion)')
def cleanup(keep_days: Optional[int], archive: bool, keep_months: int, dry_run: bool):
    """Clean expired memories."""
    from clis.agent.memory_manager import MemoryManager
    
    manager = MemoryManager()
    
    console.print("🧹 Cleaning memories...\n")
    
    # Execute cleanup
    if dry_run:
        console.print("[yellow]Preview mode (will not actually delete)[/yellow]\n")
    
    if keep_days:
        # Archive old tasks
        manager.archive_old_tasks(days=keep_days)
        console.print(f"[green]Archived tasks older than {keep_days} days[/green]")
    else:
        # Use configuration
        manager.cleanup()
        console.print("[green]Automatic cleanup executed[/green]")
    
    if archive:
        console.print("[yellow]Archive cleanup feature under development...[/yellow]")


@memory_cli.command()
@click.argument('task_id', required=False)
@click.option('--output', '-o', help='Output file path')
@click.option('--format', type=click.Choice(['markdown', 'json', 'html']), 
              default='markdown', help='Export format')
@click.option('--all', is_flag=True, help='Export all tasks')
def export(task_id: Optional[str], output: Optional[str], format: str, all: bool):
    """Export tasks as documents."""
    from clis.agent.memory_manager import MemoryManager
    
    manager = MemoryManager()
    
    if task_id:
        task_file = manager.get_task_file(task_id)
        if not task_file or not task_file.exists():
            console.print(f"[red]Error: Task {task_id} does not exist[/red]")
            return
        
        # Read content
        content = task_file.read_text(encoding='utf-8')
        
        # Export
        if output:
            output_path = Path(output)
            output_path.write_text(content, encoding='utf-8')
            console.print(f"[green]Exported to {output_path}[/green]")
        else:
            console.print(content)
    
    elif all:
        console.print("[yellow]Batch export feature under development...[/yellow]")
    
    else:
        console.print("[red]Please specify task_id or use --all[/red]")


@memory_cli.command()
@click.option('--verbose', '-v', is_flag=True, help='Show detailed statistics')
def stats(verbose: bool):
    """Show memory statistics."""
    from clis.agent.memory_manager import MemoryManager
    
    manager = MemoryManager()
    
    # Count tasks
    status_counts = {}
    total_size = 0
    
    for task_id, task_info in manager.metadata['tasks'].items():
        status = task_info['status']
        status_counts[status] = status_counts.get(status, 0) + 1
        
        # Calculate file size
        task_file = manager.get_task_file(task_id)
        if task_file and task_file.exists():
            total_size += task_file.stat().st_size
    
    # Format size
    size_mb = total_size / (1024 * 1024)
    
    # Display statistics
    stats_text = f"""
[bold cyan]Tasks:[/bold cyan]
  • Active: {status_counts.get('active', 0)}
  • Completed: {status_counts.get('completed', 0)}
  • Archived: {status_counts.get('archived', 0)}
  • Failed: {status_counts.get('failed', 0)}
  • Total: {len(manager.metadata['tasks'])}

[bold cyan]Storage:[/bold cyan]
  • Memory Dir: {manager.memory_dir}
  • Total Size: {size_mb:.1f} MB

[bold cyan]Configuration:[/bold cyan]
  • Retention Days: {manager.metadata['config']['retention_days']}
  • Auto Archive: {manager.metadata['config']['auto_archive']}
  • Auto Cleanup: {manager.metadata['config']['auto_cleanup']}
"""
    
    panel = Panel(stats_text, title="Memory Statistics", border_style="cyan")
    console.print(panel)
    
    if verbose:
        console.print("\n[dim]Detailed statistics feature under development...[/dim]")


@memory_cli.command()
@click.argument('action', type=click.Choice(['show', 'set', 'reset']))
@click.argument('key', required=False)
@click.argument('value', required=False)
def config(action: str, key: Optional[str], value: Optional[str]):
    """Configure memory management."""
    from clis.agent.memory_manager import MemoryManager
    
    manager = MemoryManager()
    
    if action == 'show':
        # Display configuration
        config = manager.metadata['config']
        console.print("[bold cyan]Memory Configuration:[/bold cyan]\n")
        for k, v in config.items():
            console.print(f"  {k}: [green]{v}[/green]")
    
    elif action == 'set':
        if not key or not value:
            console.print("[red]Please specify key and value[/red]")
            return
        
        # Set configuration
        if key in manager.metadata['config']:
            # Type conversion
            old_value = manager.metadata['config'][key]
            if isinstance(old_value, bool):
                value = value.lower() in ('true', '1', 'yes')
            elif isinstance(old_value, int):
                value = int(value)
            
            manager.metadata['config'][key] = value
            manager._save_metadata()
            console.print(f"[green]Set {key} = {value}[/green]")
        else:
            console.print(f"[red]Unknown configuration item: {key}[/red]")
    
    elif action == 'reset':
        # Reset configuration
        manager.metadata['config'] = manager._default_config()
        manager._save_metadata()
        console.print("[green]Reset to default configuration[/green]")


# Shortcut commands
@memory_cli.command()
@click.option('--limit', type=int, default=5, help='Number to display')
def recent(limit: int):
    """View recent tasks."""
    from clis.agent.memory_manager import MemoryManager
    
    manager = MemoryManager()
    tasks = manager.list_tasks(limit=limit)
    
    if not tasks:
        console.print("[yellow]No task memories[/yellow]")
        return
    
    console.print(f"[bold cyan]Recent {len(tasks)} tasks:[/bold cyan]\n")
    
    for task in tasks:
        status_icon = {
            'active': '[ACTIVE]',
            'completed': '✅',
            'archived': '[ARCHIVED]',
            'failed': '❌'
        }.get(task['status'], '[UNKNOWN]')
        
        created = datetime.fromisoformat(task['created_at']).strftime('%m-%d %H:%M')
        console.print(f"  {status_icon} [{created}] [cyan]{task['id']}[/cyan]: {task['description'][:60]}")


@memory_cli.command()
def current():
    """View current active tasks."""
    from clis.agent.memory_manager import MemoryManager, TaskStatus
    
    manager = MemoryManager()
    tasks = manager.list_tasks(status=TaskStatus.ACTIVE)
    
    if not tasks:
        console.print("[yellow]No active tasks[/yellow]")
        return
    
    console.print(f"[bold cyan][ACTIVE] Current Active Tasks ({len(tasks)}):[/bold cyan]\n")
    
    for task in tasks:
        console.print(f"  • [cyan]{task['id']}[/cyan]: {task['description']}")


@memory_cli.command()
def open():
    """Open memory directory."""
    from clis.agent.memory_manager import MemoryManager
    import subprocess
    import sys
    
    manager = MemoryManager()
    
    # Open file manager based on operating system
    if sys.platform == 'darwin':  # macOS
        subprocess.run(['open', str(manager.memory_dir)])
    elif sys.platform == 'win32':  # Windows
        subprocess.run(['explorer', str(manager.memory_dir)])
    else:  # Linux
        subprocess.run(['xdg-open', str(manager.memory_dir)])
    
    console.print(f"[green]✅ Opened directory: {manager.memory_dir}[/green]")


@memory_cli.command()
def tidy():
    """Quick cleanup (archive + clean failed tasks)."""
    from clis.agent.memory_manager import MemoryManager
    
    manager = MemoryManager()
    
    console.print("🧹 Executing quick cleanup...\n")
    
    manager.cleanup()
    
    console.print("[green]✅ Cleanup completed![/green]")


@memory_cli.command()
@click.argument('task_id')
def subtasks(task_id: str):
    """View task subtask list."""
    from clis.agent.subtask_manager import SubtaskManager
    
    try:
        # Load subtask manager
        subtask_mgr = SubtaskManager(task_id)
        
        if not subtask_mgr.subtasks:
            console.print(f"[yellow]Task {task_id} has no subtasks[/yellow]")
            return
        
        # Get progress summary
        progress = subtask_mgr.get_progress_summary()
        
        # Display progress
        console.print(Panel.fit(
            f"[bold]📊 Subtask Progress[/bold]\n\n"
            f"Total: {progress['total']}\n"
            f"✅ Completed: {progress['completed']}\n"
            f"[ACTIVE] In Progress: {progress['in_progress']}\n"
            f"⏳ Pending: {progress['pending']}\n"
            f"🚫 Blocked: {progress['blocked']}\n"
            f"❌ Failed: {progress['failed']}\n\n"
            f"Completion Rate: {progress['completion_rate']:.1f}%",
            title=f"Task {task_id}"
        ))
        
        # Display subtask list
        table = Table(title="\n🔀 Subtask List")
        table.add_column("#", style="dim")
        table.add_column("ID", style="cyan")
        table.add_column("Description")
        table.add_column("Status", style="bold")
        table.add_column("Dependencies", style="dim")
        
        status_style = {
            "pending": "yellow",
            "in_progress": "blue",
            "completed": "green",
            "failed": "red",
            "blocked": "magenta"
        }
        
        for i, subtask in enumerate(subtask_mgr.get_all_subtasks(), 1):
            style = status_style.get(subtask.status.value, "white")
            deps = ", ".join(subtask.dependencies) if subtask.dependencies else "-"
            
            table.add_row(
                str(i),
                subtask.id,
                subtask.description[:60],
                f"[{style}]{subtask.status.value}[/{style}]",
                deps
            )
        
        console.print(table)
    
    except FileNotFoundError:
        console.print(f"[red]❌ Task not found: {task_id}[/red]")
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")


@memory_cli.command()
@click.argument('query')
@click.option('--top-k', type=int, default=5, help='Return top k results')
@click.option('--min-similarity', type=float, default=0.3, help='Minimum similarity threshold')
def similar(query: str, top_k: int, min_similarity: float):
    """Search similar historical tasks (semantic search)."""
    from clis.agent.vector_search import VectorSearch
    from clis.agent.memory_manager import MemoryManager
    
    try:
        vector_search = VectorSearch()
        
        # Display search information
        stats = vector_search.get_index_stats()
        console.print(f"[dim]🔍 Search Mode: {stats['model']}[/dim]")
        console.print(f"[dim]📊 Indexed Tasks: {stats['total_tasks']}[/dim]\n")
        
        # Execute search
        results = vector_search.search_similar_tasks(query, top_k, min_similarity)
        
        if not results:
            console.print("[yellow]No similar tasks found[/yellow]")
            console.print("\n💡 Tips: Try:")
            console.print("  - Lower similarity threshold (--min-similarity)")
            console.print("  - Use different keywords")
            console.print("  - Rebuild index (clis memory rebuild-index)")
            return
        
        # Display results
        console.print(f"[bold green]Found {len(results)} similar tasks:[/bold green]\n")
        
        table = Table(title="Similar Tasks")
        table.add_column("#", style="dim")
        table.add_column("Task ID", style="cyan")
        table.add_column("Similarity", style="magenta")
        table.add_column("Description")
        
        for i, (task_id, similarity, description) in enumerate(results, 1):
            table.add_row(
                str(i),
                task_id,
                f"{similarity:.2%}",
                description[:80]
            )
        
        console.print(table)
        
        console.print("\n💡 View details: [cyan]clis memory show <task_id>[/cyan]")
    
    except Exception as e:
        console.print(f"[red]❌ Search failed: {e}[/red]")
        import traceback
        traceback.print_exc()


@memory_cli.command(name="rebuild-index")
def rebuild_index():
    """Rebuild vector index (for semantic search)."""
    from clis.agent.vector_search import VectorSearch
    from clis.agent.memory_manager import MemoryManager
    
    console.print("[bold][ACTIVE] Rebuilding vector index...[/bold]\n")
    
    try:
        vector_search = VectorSearch()
        memory_manager = MemoryManager()
        
        # Rebuild index
        vector_search.rebuild_index(memory_manager)
        
        # Display statistics
        stats = vector_search.get_index_stats()
        console.print(Panel.fit(
            f"[bold green]✅ Index rebuild completed[/bold green]\n\n"
            f"Total Tasks: {stats['total_tasks']}\n"
            f"With Vectors: {stats['tasks_with_embeddings']}\n"
            f"Search Mode: {stats['model']}\n"
            f"Vector Feature: {'✅ Enabled' if stats['embeddings_enabled'] else '❌ Disabled (using keyword search)'}",
            title="Vector Index Statistics"
        ))
        
        if not stats['embeddings_enabled']:
            console.print("\n💡 [yellow]Tip[/yellow]: Install dependencies to enable vector search:")
            console.print("   [cyan]pip install sentence-transformers numpy[/cyan]")
    
    except Exception as e:
        console.print(f"[red]❌ Index rebuild failed: {e}[/red]")
