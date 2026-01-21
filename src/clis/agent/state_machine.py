"""
Task State Machine Module - Explicitly guide weak models

Design purpose:
- Reduce model's decision burden
- Clearly inform what should be done now
- Automatically detect abnormal states and intervene
"""

from enum import Enum
from typing import Optional
from dataclasses import dataclass


class TaskState(Enum):
    """Task state"""
    INIT = "initialization"           # Initialization
    GATHER = "information_gathering"  # Information gathering
    ANALYZE = "data_analysis"         # Data analysis  
    EXECUTE = "execution"             # Execution
    FINALIZE = "finalization"         # Finalization
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
    Task State Machine - Explicitly guide weak models
    
    Automatically determines current phase and provides clear advice by detecting working memory state
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
        Detect current state and provide advice
        
        Args:
            iteration: Current iteration count
            working_memory: Working memory object
            
        Returns:
            State and advice
        """
        # Detect loops
        is_loop, loop_reason = working_memory.detect_loop()
        if is_loop:
            self.current_state = TaskState.STUCK
            return StateAdvice(
                state=TaskState.STUCK,
                message=f"🚨 Loop detected: {loop_reason}",
                suggested_actions=[
                    "Stop current operation immediately",
                    "Summarize answer based on existing information",
                    "Call {\"type\": \"done\", \"summary\": \"...\"}",
                    "Don't try more reads or commands!"
                ],
                is_urgent=True
            )
        
        # Detect information overload (too many files read)
        if len(working_memory.files_read) > 15 and len(working_memory.files_written) == 0:
            self.current_state = TaskState.ANALYZE
            return StateAdvice(
                state=TaskState.ANALYZE,
                message="📚 Information gathering sufficient → Switch to analysis phase",
                suggested_actions=[
                    "Don't read new files",
                    "Analyze collected information",
                    "Extract key findings",
                    "Prepare to give conclusion"
                ],
                is_urgent=False
            )
        
        # Detect approaching iteration limit
        if iteration >= self.max_iterations * 0.8:
            self.current_state = TaskState.FINALIZE
            return StateAdvice(
                state=TaskState.FINALIZE,
                message=f"⏰ Approaching iteration limit ({iteration}/{self.max_iterations}) → Must wrap up",
                suggested_actions=[
                    "Immediately give answer based on existing information",
                    "Don't start new subtasks",
                    "Call {\"type\": \"done\", \"summary\": \"...\"} to end"
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
                    "Continue collecting necessary information",
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
                    "Prepare to execute or give conclusion"
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
│                  🎯 State Machine Guidance                    │
╰──────────────────────────────────────────────────────────────╯

{urgency} {advice.message}

📋 Suggested Actions:
{actions_text}
"""
