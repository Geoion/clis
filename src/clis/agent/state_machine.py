"""
Task state machine module - Explicitly guide weak models

Design purpose:
- Reduce the model's decision-making burden
- Clearly tell it what should be done now
- Automatically detect abnormal states and intervene
"""

from enum import Enum
from typing import Optional
from dataclasses import dataclass


class TaskState(Enum):
    """Task states"""
    INIT = "initialization"           # Initialization
    GATHER = "information_gathering"  # Information gathering
    ANALYZE = "data_analysis"         # Data analysis  
    EXECUTE = "execution"             # Execute operations
    FINALIZE = "finalization"         # Finalize summary
    STUCK = "stuck_in_loop"           # Stuck in loop


@dataclass
class StateAdvice:
    """State advice"""
    state: TaskState
    message: str
    suggested_actions: list[str]
    is_urgent: bool = False


class TaskStateMachine:
    """
    Task state machine - Explicitly guide weak models
    
    By detecting the state of working memory, automatically determine the current stage and give clear advice
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
        Detect current state and give advice
        
        Args:
            iteration: Current iteration number
            working_memory: Working memory object
            
        Returns:
            State and advice
        """
        # Detect loop
        is_loop, loop_reason = working_memory.detect_loop()
        if is_loop:
            self.current_state = TaskState.STUCK
            return StateAdvice(
                state=TaskState.STUCK,
                message=f"🚨 Loop detected: {loop_reason}",
                suggested_actions=[
                    "Immediately stop current operation",
                    "Summarize answer based on existing information",
                    "Call {\"type\": \"done\", \"summary\": \"...\"}",
                    "Do not attempt more reads or commands!"
                ],
                is_urgent=True
            )
        
        # Detect information overload (reading too many files)
        if len(working_memory.files_read) > 15 and len(working_memory.files_written) == 0:
            self.current_state = TaskState.ANALYZE
            return StateAdvice(
                state=TaskState.ANALYZE,
                message="📚 Information gathering complete → Switch to analysis phase",
                suggested_actions=[
                    "Do not read more new files",
                    "Analyze collected information",
                    "Extract key findings",
                    "Prepare to give conclusions"
                ],
                is_urgent=False
            )
        
        # Detect approaching iteration limit
        if iteration >= self.max_iterations * 0.8:
            self.current_state = TaskState.FINALIZE
            return StateAdvice(
                state=TaskState.FINALIZE,
                message=f"⏰ Approaching iteration limit ({iteration}/{self.max_iterations}) → Must finalize",
                suggested_actions=[
                    "Immediately give answer based on existing information",
                    "Do not start new subtasks",
                    "Call {\"type\": \"done\", \"summary\": \"...\"} to finish"
                ],
                is_urgent=True
            )
        
        # Normal state judgment
        if len(working_memory.files_read) < 5 and len(working_memory.commands_run) == 0:
            self.current_state = TaskState.GATHER
            return StateAdvice(
                state=TaskState.GATHER,
                message="🔍 Information gathering phase",
                suggested_actions=[
                    "Continue gathering necessary information",
                    "Read relevant files",
                    "Explore project structure"
                ],
                is_urgent=False
            )
        
        elif len(working_memory.files_read) >= 5:
            self.current_state = TaskState.ANALYZE
            return StateAdvice(
                state=TaskState.ANALYZE,
                message="🧠 Analysis phase",
                suggested_actions=[
                    "Analyze collected data",
                    "Extract key information",
                    "Prepare to execute or give conclusions"
                ],
                is_urgent=False
            )
        
        self.current_state = TaskState.EXECUTE
        return StateAdvice(
            state=TaskState.EXECUTE,
            message="⚙️ Execution phase",
            suggested_actions=["Continue executing task"],
            is_urgent=False
        )
    
    def format_advice(self, advice: StateAdvice) -> str:
        """Format advice as prompt text"""
        urgency = "🚨 Urgent!" if advice.is_urgent else ""
        
        actions_text = "\n".join(f"   {i+1}. {action}" 
                                for i, action in enumerate(advice.suggested_actions))
        
        return f"""
╭──────────────────────────────────────────────────────────────╮
│                  🎯 STATE MACHINE GUIDANCE                    │
╰──────────────────────────────────────────────────────────────╯

{urgency} {advice.message}

📋 Suggested Actions:
{actions_text}
"""
