"""
任务状态机模块 - 显式引导弱模型

设计目的:
- 减少模型的决策负担
- 明确告知当前应该做什么
- 自动检测异常状态并干预
"""

from enum import Enum
from typing import Optional
from dataclasses import dataclass


class TaskState(Enum):
    """任务状态"""
    INIT = "initialization"           # 初始化
    GATHER = "information_gathering"  # 信息收集
    ANALYZE = "data_analysis"         # 数据分析  
    EXECUTE = "execution"             # 执行操作
    FINALIZE = "finalization"         # 完成总结
    STUCK = "stuck_in_loop"           # 陷入循环


@dataclass
class StateAdvice:
    """状态建议"""
    state: TaskState
    message: str
    suggested_actions: list[str]
    is_urgent: bool = False


class TaskStateMachine:
    """
    任务状态机 - 显式引导弱模型
    
    通过检测工作记忆的状态,自动判断当前阶段并给出明确建议
    """
    
    def __init__(self, max_iterations: int = 100):
        self.max_iterations = max_iterations
        self.current_state = TaskState.INIT
    
    def detect_state(
        self, 
        iteration: int,
        working_memory
    ) -> StateAdvice:
        """
        检测当前状态并给出建议
        
        Args:
            iteration: 当前迭代次数
            working_memory: 工作记忆对象
            
        Returns:
            状态和建议
        """
        # 检测循环
        is_loop, loop_reason = working_memory.detect_loop()
        if is_loop:
            self.current_state = TaskState.STUCK
            return StateAdvice(
                state=TaskState.STUCK,
                message=f"🚨 检测到循环: {loop_reason}",
                suggested_actions=[
                    "立即停止当前操作",
                    "基于已有信息总结答案",
                    "调用 {\"type\": \"done\", \"summary\": \"...\"}",
                    "不要尝试更多读取或命令!"
                ],
                is_urgent=True
            )
        
        # 检测信息过载 (读太多文件)
        if len(working_memory.files_read) > 15 and len(working_memory.files_written) == 0:
            self.current_state = TaskState.ANALYZE
            return StateAdvice(
                state=TaskState.ANALYZE,
                message="📚 信息收集已充分 → 切换到分析阶段",
                suggested_actions=[
                    "不要再读取新文件",
                    "分析已收集的信息",
                    "提取关键发现",
                    "准备给出结论"
                ],
                is_urgent=False
            )
        
        # 检测接近迭代上限
        if iteration >= self.max_iterations * 0.8:
            self.current_state = TaskState.FINALIZE
            return StateAdvice(
                state=TaskState.FINALIZE,
                message=f"⏰ 接近迭代上限 ({iteration}/{self.max_iterations}) → 必须收尾",
                suggested_actions=[
                    "立即基于现有信息给出答案",
                    "不要开启新的子任务",
                    "调用 {\"type\": \"done\", \"summary\": \"...\"} 结束"
                ],
                is_urgent=True
            )
        
        # 正常状态判断
        if len(working_memory.files_read) < 5 and len(working_memory.commands_run) == 0:
            self.current_state = TaskState.GATHER
            return StateAdvice(
                state=TaskState.GATHER,
                message="🔍 信息收集阶段",
                suggested_actions=[
                    "继续收集必要信息",
                    "读取相关文件",
                    "探索项目结构"
                ],
                is_urgent=False
            )
        
        elif len(working_memory.files_read) >= 5:
            self.current_state = TaskState.ANALYZE
            return StateAdvice(
                state=TaskState.ANALYZE,
                message="🧠 分析阶段",
                suggested_actions=[
                    "分析已收集的数据",
                    "提取关键信息",
                    "准备执行或给出结论"
                ],
                is_urgent=False
            )
        
        self.current_state = TaskState.EXECUTE
        return StateAdvice(
            state=TaskState.EXECUTE,
            message="⚙️ 执行阶段",
            suggested_actions=["继续执行任务"],
            is_urgent=False
        )
    
    def format_advice(self, advice: StateAdvice) -> str:
        """格式化建议为 prompt 文本"""
        urgency = "🚨 紧急!" if advice.is_urgent else ""
        
        actions_text = "\n".join(f"   {i+1}. {action}" 
                                for i, action in enumerate(advice.suggested_actions))
        
        return f"""
╭──────────────────────────────────────────────────────────────╮
│                  🎯 状态机引导 (STATE MACHINE)                │
╰──────────────────────────────────────────────────────────────╯

{urgency} {advice.message}

📋 建议行动:
{actions_text}
"""
