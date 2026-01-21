"""
错误展示模块 - 用户友好的错误信息展示

提供美观、清晰、有帮助的错误提示
"""

from typing import Optional, List, Any
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.markdown import Markdown

console = Console()


class ErrorDisplay:
    """错误展示类"""
    
    @staticmethod
    def show_error(
        error_type: str,
        message: str,
        context: Optional[str] = None,
        suggestions: Optional[List[str]] = None,
        show_help: bool = True
    ):
        """
        展示格式化的错误信息
        
        Args:
            error_type: 错误类型
            message: 错误信息
            context: 上下文
            suggestions: 解决建议列表
            show_help: 是否显示帮助信息
        """
        # 构建错误内容
        content = f"[bold red]错误类型:[/bold red] {error_type}\n"
        content += f"[bold]错误信息:[/bold] {message}\n"
        
        if context:
            content += f"\n[dim]发生位置:[/dim] {context}\n"
        
        if suggestions:
            content += f"\n[bold yellow]💡 解决建议:[/bold yellow]\n"
            for i, suggestion in enumerate(suggestions, 1):
                content += f"   {i}. {suggestion}\n"
        
        if show_help:
            content += f"\n[dim]📚 获取帮助:[/dim]\n"
            content += f"   • 运行诊断: [cyan]clis doctor[/cyan]\n"
            content += f"   • 查看文档: [cyan]https://github.com/eskiyin/clis[/cyan]\n"
            content += f"   • 查看日志: [dim]~/.clis/logs/clis.log[/dim]\n"
        
        # 显示面板
        console.print(Panel(
            content,
            title="[bold red]❌ 错误[/bold red]",
            border_style="red"
        ))
    
    @staticmethod
    def show_tool_error(
        tool_name: str,
        error_type: str,
        message: str,
        params: dict,
        suggestions: Optional[List[str]] = None
    ):
        """
        展示工具执行错误
        
        Args:
            tool_name: 工具名称
            error_type: 错误类型
            message: 错误信息
            params: 工具参数
            suggestions: 解决建议
        """
        content = f"[bold]工具:[/bold] {tool_name}\n"
        content += f"[bold red]错误:[/bold red] {error_type}\n"
        content += f"[bold]信息:[/bold] {message}\n"
        
        # 显示参数
        if params:
            content += f"\n[bold]调用参数:[/bold]\n"
            for key, value in params.items():
                # 截断过长的值
                value_str = str(value)
                if len(value_str) > 100:
                    value_str = value_str[:97] + "..."
                content += f"   • {key}: {value_str}\n"
        
        if suggestions:
            content += f"\n[bold yellow]💡 建议:[/bold yellow]\n"
            for i, suggestion in enumerate(suggestions, 1):
                content += f"   {i}. {suggestion}\n"
        
        console.print(Panel(
            content,
            title=f"[bold red]❌ 工具执行失败: {tool_name}[/bold red]",
            border_style="red"
        ))
    
    @staticmethod
    def show_warning(message: str, title: str = "警告"):
        """展示警告信息"""
        console.print(Panel(
            f"[yellow]{message}[/yellow]",
            title=f"[bold yellow]⚠️  {title}[/bold yellow]",
            border_style="yellow"
        ))
    
    @staticmethod
    def show_success(message: str, title: str = "成功"):
        """展示成功信息"""
        console.print(Panel(
            f"[green]{message}[/green]",
            title=f"[bold green]✅ {title}[/bold green]",
            border_style="green"
        ))
    
    @staticmethod
    def show_tip(message: str):
        """展示提示信息"""
        console.print(f"\n[dim]💡 提示: {message}[/dim]\n")
    
    @staticmethod
    def show_validation_error(field: str, value: Any, expected: str):
        """
        展示参数验证错误
        
        Args:
            field: 字段名
            value: 实际值
            expected: 期望的格式/类型
        """
        content = f"[bold]参数验证失败[/bold]\n\n"
        content += f"字段: [cyan]{field}[/cyan]\n"
        content += f"实际值: [red]{value}[/red]\n"
        content += f"期望: [green]{expected}[/green]\n"
        
        console.print(Panel(
            content,
            title="[bold red]❌ 参数错误[/bold red]",
            border_style="red"
        ))
    
    @staticmethod
    def show_progress_error(task: str, current: int, total: int, error: str):
        """
        展示进度相关的错误
        
        Args:
            task: 任务名称
            current: 当前进度
            total: 总数
            error: 错误信息
        """
        content = f"[bold]任务:[/bold] {task}\n"
        content += f"[bold]进度:[/bold] {current}/{total}\n"
        content += f"[bold red]错误:[/bold red] {error}\n"
        
        console.print(Panel(
            content,
            title="[bold red]❌ 任务执行失败[/bold red]",
            border_style="red"
        ))


# 导出
__all__ = ['ErrorDisplay']
