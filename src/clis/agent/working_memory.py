"""
工作记忆模块 - 最近 5-10 步的结构化操作记录

特点:
- 轻量级,纯内存
- 结构化,易于查询
- 显式状态,减少推理
"""

from typing import List, Dict, Set
from dataclasses import dataclass, field
from datetime import datetime
from collections import Counter


@dataclass
class WorkingMemory:
    """
    工作记忆 - 最近 5-10 步的结构化操作记录
    
    用于显式跟踪 Agent 的操作历史,帮助弱模型避免循环
    """
    
    # 操作记录 (保留顺序)
    files_read: List[str] = field(default_factory=list)
    files_written: List[str] = field(default_factory=list)
    commands_run: List[Dict] = field(default_factory=list)  # {cmd, time, success}
    
    # 工具使用统计
    tools_used: Dict[str, int] = field(default_factory=dict)
    
    # 显式状态
    current_phase: str = "initialization"
    phase_progress: str = "0/0"
    
    # 去重集合 (快速查询)
    _files_read_set: Set[str] = field(default_factory=set, init=False, repr=False)
    _files_written_set: Set[str] = field(default_factory=set, init=False, repr=False)
    
    def add_file_read(self, path: str) -> bool:
        """
        记录文件读取
        
        Args:
            path: 文件路径
            
        Returns:
            True if new, False if duplicate
        """
        is_new = path not in self._files_read_set
        if is_new:
            self.files_read.append(path)
            self._files_read_set.add(path)
        else:
            # 即使是重复,也记录(用于检测循环)
            self.files_read.append(path)
        return is_new
    
    def add_file_written(self, path: str):
        """记录文件写入"""
        if path not in self._files_written_set:
            self.files_written.append(path)
            self._files_written_set.add(path)
    
    def add_command(self, cmd: str, success: bool):
        """记录命令执行"""
        self.commands_run.append({
            'cmd': cmd,
            'time': datetime.now().isoformat(),
            'success': success
        })
    
    def increment_tool(self, tool_name: str):
        """增加工具使用计数"""
        self.tools_used[tool_name] = self.tools_used.get(tool_name, 0) + 1
    
    def update_phase(self, phase: str, progress: str):
        """更新当前阶段"""
        self.current_phase = phase
        self.phase_progress = progress
    
    def to_prompt(self, max_items: int = 10) -> str:
        """
        转换为弱模型友好的 prompt 文本
        
        设计原则:
        - 使用 emoji 和树状结构 (视觉清晰)
        - 显示数量统计 (让模型有"进度感")
        - 高亮最近项目 (时间就近性)
        - 明确警告重复操作
        
        Args:
            max_items: 最多显示的项目数
            
        Returns:
            格式化的 prompt 文本
        """
        recent_files = self.files_read[-max_items:] if self.files_read else ["无"]
        files_summary = ", ".join(recent_files) if len(recent_files) <= 5 else \
                       ", ".join(recent_files[:5]) + f" ... (共 {len(self.files_read)} 个)"
        
        recent_written = self.files_written[-5:] if self.files_written else ["无"]
        written_summary = ", ".join(recent_written)
        
        recent_cmds = [c['cmd'][:50] for c in self.commands_run[-3:]] if self.commands_run else ["无"]
        cmd_summary = "\n   ".join(recent_cmds)
        
        return f"""
╭──────────────────────────────────────────────────────────────╮
│                   📋 工作记忆 (WORKING MEMORY)                │
╰──────────────────────────────────────────────────────────────╯

🎯 当前阶段: {self.current_phase} ({self.phase_progress})

📂 已读文件 (共 {len(self.files_read)} 个):
   {files_summary}

✏️  已写文件 (共 {len(self.files_written)} 个):
   {written_summary}

⚙️  已执行命令 (共 {len(self.commands_run)} 个):
   {cmd_summary}

📊 工具使用统计:
   {self._format_tool_stats()}

⚠️  重要提醒:
   • 如果你想读的文件已在"已读"列表 → 不要重复读取!
   • 如果已读文件超过 10 个 → 应该开始分析而非继续收集
   • 如果同一工具使用超过 5 次 → 可能陷入循环,改变策略!
"""
    
    def _format_tool_stats(self) -> str:
        """格式化工具统计"""
        if not self.tools_used:
            return "   (暂无)"
        
        sorted_tools = sorted(self.tools_used.items(), key=lambda x: x[1], reverse=True)
        stats = []
        for tool, count in sorted_tools[:5]:
            warning = " ⚠️ 过度使用!" if count > 5 else ""
            stats.append(f"{tool}: {count}次{warning}")
        return "\n   ".join(stats)
    
    def detect_loop(self) -> tuple[bool, str]:
        """
        检测是否陷入循环
        
        Returns:
            (is_loop, reason)
        """
        # 规则 1: 单个文件读取超过 2 次
        file_counts = Counter(self.files_read)
        for file, count in file_counts.items():
            if count > 2:
                return True, f"文件 '{file}' 已读取 {count} 次!"
        
        # 规则 2: 单个工具使用超过 10 次
        for tool, count in self.tools_used.items():
            if count > 10:
                return True, f"工具 '{tool}' 已使用 {count} 次!"
        
        # 规则 3: 最近 5 次操作都是 read_file
        if len(self.files_read) >= 5:
            recent = self.files_read[-5:]
            if len(set(recent)) <= 2:  # 只在读 2 个文件来回切换
                return True, f"最近 5 次操作都在读取文件: {set(recent)}"
        
        return False, ""
    
    def get_stats(self) -> Dict:
        """
        获取统计信息
        
        Returns:
            统计信息字典
        """
        return {
            'files_read_count': len(self.files_read),
            'files_written_count': len(self.files_written),
            'commands_run_count': len(self.commands_run),
            'unique_files_read': len(self._files_read_set),
            'unique_files_written': len(self._files_written_set),
            'tools_used': dict(self.tools_used),
            'current_phase': self.current_phase,
            'phase_progress': self.phase_progress,
        }
    
    def clear(self):
        """清空工作记忆"""
        self.files_read.clear()
        self.files_written.clear()
        self.commands_run.clear()
        self.tools_used.clear()
        self._files_read_set.clear()
        self._files_written_set.clear()
        self.current_phase = "initialization"
        self.phase_progress = "0/0"
