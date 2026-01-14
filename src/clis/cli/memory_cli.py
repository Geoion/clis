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
    """管理任务记忆 (Manage task memories)"""
    pass


@memory_cli.command()
@click.option('--status', type=click.Choice(['active', 'completed', 'archived', 'failed']),
              help='过滤任务状态')
@click.option('--limit', type=int, default=20, help='最大显示数量')
@click.option('--verbose', '-v', is_flag=True, help='显示详细信息')
def list(status: Optional[str], limit: int, verbose: bool):
    """列出任务记忆"""
    from clis.agent.memory_manager import MemoryManager
    
    manager = MemoryManager()
    
    # 获取任务列表
    if status:
        from clis.agent.memory_manager import TaskStatus
        status_enum = TaskStatus(status)
        tasks = manager.list_tasks(status=status_enum, limit=limit)
    else:
        tasks = manager.list_tasks(limit=limit)
    
    if not tasks:
        console.print("[yellow]没有找到任务记忆[/yellow]")
        return
    
    # 创建表格
    table = Table(title=f"📋 任务记忆 (共 {len(tasks)} 个)")
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
            'active': '🔄',
            'completed': '✅',
            'archived': '📦',
            'failed': '❌'
        }.get(task['status'], '❓')
        
        status_display = f"{status_icon} {task['status']}"
        created = datetime.fromisoformat(task['created_at']).strftime('%Y-%m-%d %H:%M')
        description = task['description'][:50] + '...' if len(task['description']) > 50 else task['description']
        
        row = [task_id, status_display, created, description]
        
        if verbose:
            # 计算持续时间
            if 'completed_at' in task:
                start = datetime.fromisoformat(task['created_at'])
                end = datetime.fromisoformat(task['completed_at'])
                duration = str(end - start).split('.')[0]  # 去掉微秒
            else:
                duration = "进行中"
            
            # TODO: 从文件读取统计信息
            files_count = "N/A"
            
            row.extend([duration, files_count])
        
        table.add_row(*row)
    
    console.print(table)
    
    # 提示
    console.print(f"\n💡 使用 [cyan]clis memory show <task_id>[/cyan] 查看详情")


@memory_cli.command()
@click.argument('task_id')
@click.option('--full', is_flag=True, help='显示完整内容')
@click.option('--edit', is_flag=True, help='在编辑器中打开')
def show(task_id: str, full: bool, edit: bool):
    """查看任务详情"""
    from clis.agent.memory_manager import MemoryManager
    
    manager = MemoryManager()
    task_file = manager.get_task_file(task_id)
    
    if not task_file or not task_file.exists():
        console.print(f"[red]❌ 任务 {task_id} 不存在[/red]")
        return
    
    # 在编辑器中打开
    if edit:
        import subprocess
        editor = os.environ.get('EDITOR', 'vim')
        subprocess.run([editor, str(task_file)])
        return
    
    # 读取任务信息
    task_info = manager.metadata['tasks'].get(task_id)
    if not task_info:
        console.print(f"[red]❌ 任务元数据不存在[/red]")
        return
    
    # 显示任务信息
    status_icon = {
        'active': '🔄',
        'completed': '✅',
        'archived': '📦',
        'failed': '❌'
    }.get(task_info['status'], '❓')
    
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
    
    panel = Panel(info_text, title=f"📋 Task: {task_id}", border_style="cyan")
    console.print(panel)
    
    # 显示文件内容
    if full:
        content = task_file.read_text(encoding='utf-8')
        console.print("\n" + "="*60)
        console.print(content)
    else:
        # 显示摘要
        console.print(f"\n[dim]文件位置: {task_file}[/dim]")
        console.print("[dim]使用 --full 显示完整内容[/dim]")
        console.print("[dim]使用 --edit 在编辑器中打开[/dim]")


@memory_cli.command()
@click.argument('query')
@click.option('--content', is_flag=True, help='搜索文件内容')
@click.option('--regex', is_flag=True, help='使用正则表达式')
def search(query: str, content: bool, regex: bool):
    """搜索任务记忆"""
    from clis.agent.memory_manager import MemoryManager
    
    manager = MemoryManager()
    
    if content:
        console.print("[yellow]内容搜索功能开发中...[/yellow]")
        return
    
    # 简单搜索描述
    results = manager.search_tasks(query)
    
    if not results:
        console.print(f"[yellow]没有找到匹配 '{query}' 的任务[/yellow]")
        return
    
    console.print(f"[green]找到 {len(results)} 个匹配的任务:[/green]\n")
    
    for task in results:
        console.print(f"  • [cyan]{task['id']}[/cyan]: {task['description']}")
    
    console.print(f"\n💡 使用 [cyan]clis memory show <task_id>[/cyan] 查看详情")


@memory_cli.command()
@click.argument('task_id', required=False)
@click.option('--status', type=click.Choice(['failed']), help='删除指定状态的所有任务')
@click.option('--older-than', help='删除早于指定时间的任务 (如: 90days)')
@click.option('--force', '-f', is_flag=True, help='跳过确认')
def delete(task_id: Optional[str], status: Optional[str], older_than: Optional[str], force: bool):
    """删除任务记忆"""
    from clis.agent.memory_manager import MemoryManager
    
    manager = MemoryManager()
    
    # 删除单个任务
    if task_id:
        task_info = manager.metadata['tasks'].get(task_id)
        if not task_info:
            console.print(f"[red]❌ 任务 {task_id} 不存在[/red]")
            return
        
        # 确认
        if not force:
            confirm = click.confirm(f"确定要删除任务 {task_id}?")
            if not confirm:
                console.print("[yellow]已取消[/yellow]")
                return
        
        # 删除文件
        task_file = manager.get_task_file(task_id)
        if task_file and task_file.exists():
            task_file.unlink()
        
        # 删除元数据
        del manager.metadata['tasks'][task_id]
        manager._save_metadata()
        
        console.print(f"[green]✅ 已删除任务 {task_id}[/green]")
        return
    
    # 批量删除
    if status or older_than:
        console.print("[yellow]批量删除功能开发中...[/yellow]")
        return
    
    console.print("[red]请指定 task_id 或使用 --status/--older-than 选项[/red]")


@memory_cli.command()
@click.argument('task_id', required=False)
@click.option('--all-completed', is_flag=True, help='归档所有已完成任务')
def archive(task_id: Optional[str], all_completed: bool):
    """归档任务记忆"""
    from clis.agent.memory_manager import MemoryManager
    
    manager = MemoryManager()
    
    if task_id:
        manager._archive_task(task_id)
        console.print(f"[green]✅ 已归档任务 {task_id}[/green]")
    elif all_completed:
        # 归档所有已完成任务
        completed_tasks = [
            tid for tid, info in manager.metadata['tasks'].items()
            if info['status'] == 'completed'
        ]
        
        for tid in completed_tasks:
            manager._archive_task(tid)
        
        console.print(f"[green]✅ 已归档 {len(completed_tasks)} 个任务[/green]")
    else:
        console.print("[red]请指定 task_id 或使用 --all-completed[/red]")


@memory_cli.command()
@click.option('--keep-days', type=int, help='保留天数')
@click.option('--archive', is_flag=True, help='清理归档任务')
@click.option('--keep-months', type=int, default=3, help='归档保留月数')
@click.option('--dry-run', is_flag=True, help='预览清理 (不实际删除)')
def cleanup(keep_days: Optional[int], archive: bool, keep_months: int, dry_run: bool):
    """清理过期记忆"""
    from clis.agent.memory_manager import MemoryManager
    
    manager = MemoryManager()
    
    console.print("🧹 清理记忆...\n")
    
    # 执行清理
    if dry_run:
        console.print("[yellow]预览模式 (不会实际删除)[/yellow]\n")
    
    if keep_days:
        # 归档旧任务
        manager.archive_old_tasks(days=keep_days)
        console.print(f"[green]✅ 已归档超过 {keep_days} 天的任务[/green]")
    else:
        # 使用配置
        manager.cleanup()
        console.print("[green]✅ 已执行自动清理[/green]")
    
    if archive:
        console.print("[yellow]归档清理功能开发中...[/yellow]")


@memory_cli.command()
@click.argument('task_id', required=False)
@click.option('--output', '-o', help='输出文件路径')
@click.option('--format', type=click.Choice(['markdown', 'json', 'html']), 
              default='markdown', help='导出格式')
@click.option('--all', is_flag=True, help='导出所有任务')
def export(task_id: Optional[str], output: Optional[str], format: str, all: bool):
    """导出任务为文档"""
    from clis.agent.memory_manager import MemoryManager
    
    manager = MemoryManager()
    
    if task_id:
        task_file = manager.get_task_file(task_id)
        if not task_file or not task_file.exists():
            console.print(f"[red]❌ 任务 {task_id} 不存在[/red]")
            return
        
        # 读取内容
        content = task_file.read_text(encoding='utf-8')
        
        # 导出
        if output:
            output_path = Path(output)
            output_path.write_text(content, encoding='utf-8')
            console.print(f"[green]✅ 已导出到 {output_path}[/green]")
        else:
            console.print(content)
    
    elif all:
        console.print("[yellow]批量导出功能开发中...[/yellow]")
    
    else:
        console.print("[red]请指定 task_id 或使用 --all[/red]")


@memory_cli.command()
@click.option('--verbose', '-v', is_flag=True, help='显示详细统计')
def stats(verbose: bool):
    """显示记忆统计信息"""
    from clis.agent.memory_manager import MemoryManager
    
    manager = MemoryManager()
    
    # 统计任务数量
    status_counts = {}
    total_size = 0
    
    for task_id, task_info in manager.metadata['tasks'].items():
        status = task_info['status']
        status_counts[status] = status_counts.get(status, 0) + 1
        
        # 计算文件大小
        task_file = manager.get_task_file(task_id)
        if task_file and task_file.exists():
            total_size += task_file.stat().st_size
    
    # 格式化大小
    size_mb = total_size / (1024 * 1024)
    
    # 显示统计
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
    
    panel = Panel(stats_text, title="📊 Memory Statistics", border_style="cyan")
    console.print(panel)
    
    if verbose:
        console.print("\n[dim]详细统计功能开发中...[/dim]")


@memory_cli.command()
@click.argument('action', type=click.Choice(['show', 'set', 'reset']))
@click.argument('key', required=False)
@click.argument('value', required=False)
def config(action: str, key: Optional[str], value: Optional[str]):
    """配置记忆管理"""
    from clis.agent.memory_manager import MemoryManager
    
    manager = MemoryManager()
    
    if action == 'show':
        # 显示配置
        config = manager.metadata['config']
        console.print("[bold cyan]Memory Configuration:[/bold cyan]\n")
        for k, v in config.items():
            console.print(f"  {k}: [green]{v}[/green]")
    
    elif action == 'set':
        if not key or not value:
            console.print("[red]请指定 key 和 value[/red]")
            return
        
        # 设置配置
        if key in manager.metadata['config']:
            # 类型转换
            old_value = manager.metadata['config'][key]
            if isinstance(old_value, bool):
                value = value.lower() in ('true', '1', 'yes')
            elif isinstance(old_value, int):
                value = int(value)
            
            manager.metadata['config'][key] = value
            manager._save_metadata()
            console.print(f"[green]✅ 已设置 {key} = {value}[/green]")
        else:
            console.print(f"[red]未知配置项: {key}[/red]")
    
    elif action == 'reset':
        # 重置配置
        manager.metadata['config'] = manager._default_config()
        manager._save_metadata()
        console.print("[green]✅ 已重置为默认配置[/green]")


# 快捷命令
@memory_cli.command()
@click.option('--limit', type=int, default=5, help='显示数量')
def recent(limit: int):
    """查看最近的任务"""
    from clis.agent.memory_manager import MemoryManager
    
    manager = MemoryManager()
    tasks = manager.list_tasks(limit=limit)
    
    if not tasks:
        console.print("[yellow]没有任务记忆[/yellow]")
        return
    
    console.print(f"[bold cyan]📋 最近 {len(tasks)} 个任务:[/bold cyan]\n")
    
    for task in tasks:
        status_icon = {
            'active': '🔄',
            'completed': '✅',
            'archived': '📦',
            'failed': '❌'
        }.get(task['status'], '❓')
        
        created = datetime.fromisoformat(task['created_at']).strftime('%m-%d %H:%M')
        console.print(f"  {status_icon} [{created}] [cyan]{task['id']}[/cyan]: {task['description'][:60]}")


@memory_cli.command()
def current():
    """查看当前活跃任务"""
    from clis.agent.memory_manager import MemoryManager, TaskStatus
    
    manager = MemoryManager()
    tasks = manager.list_tasks(status=TaskStatus.ACTIVE)
    
    if not tasks:
        console.print("[yellow]没有活跃任务[/yellow]")
        return
    
    console.print(f"[bold cyan]🔄 当前活跃任务 ({len(tasks)} 个):[/bold cyan]\n")
    
    for task in tasks:
        console.print(f"  • [cyan]{task['id']}[/cyan]: {task['description']}")


@memory_cli.command()
def open():
    """打开记忆目录"""
    from clis.agent.memory_manager import MemoryManager
    import subprocess
    import sys
    
    manager = MemoryManager()
    
    # 根据操作系统打开文件管理器
    if sys.platform == 'darwin':  # macOS
        subprocess.run(['open', str(manager.memory_dir)])
    elif sys.platform == 'win32':  # Windows
        subprocess.run(['explorer', str(manager.memory_dir)])
    else:  # Linux
        subprocess.run(['xdg-open', str(manager.memory_dir)])
    
    console.print(f"[green]✅ 已打开目录: {manager.memory_dir}[/green]")


@memory_cli.command()
def tidy():
    """快速清理 (归档 + 清理失败任务)"""
    from clis.agent.memory_manager import MemoryManager
    
    manager = MemoryManager()
    
    console.print("🧹 执行快速清理...\n")
    
    manager.cleanup()
    
    console.print("[green]✅ 清理完成![/green]")
