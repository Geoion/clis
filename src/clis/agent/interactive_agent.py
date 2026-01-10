"""
Interactive agent with step-by-step execution and dynamic planning.

Similar to Cursor and Claude Code, this agent:
1. Thinks and plans one step at a time
2. Executes read-only commands automatically
3. Asks for confirmation only for write/modify operations
4. Adjusts plan based on execution results
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple, Literal

from clis.agent.agent import Agent
from clis.config import ConfigManager
from clis.tools.base import Tool, ToolExecutor, ToolResult
from clis.safety.risk_scorer import RiskScorer
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class StepResult:
    """Result of a single step execution."""
    
    def __init__(
        self,
        step_number: int,
        action_type: Literal["tool_call", "command", "thinking"],
        description: str,
        success: bool,
        output: str = "",
        error: Optional[str] = None,
        needs_confirmation: bool = False,
        risk_level: str = "low"
    ):
        self.step_number = step_number
        self.action_type = action_type
        self.description = description
        self.success = success
        self.output = output
        self.error = error
        self.needs_confirmation = needs_confirmation
        self.risk_level = risk_level


class InteractiveAgent:
    """
    Interactive agent with step-by-step execution.
    
    Features:
    - Dynamic planning: adjusts based on execution results
    - Smart confirmation: only asks for risky operations
    - Continuous thinking: re-evaluates after each step
    - Tool integration: uses tools to gather information
    
    Usage:
        agent = InteractiveAgent(config_manager, tools)
        
        for step in agent.execute_interactive(query):
            if step.needs_confirmation:
                if not confirm(step):
                    break
            
            print(f"Step {step.step_number}: {step.description}")
            if step.output:
                print(step.output)
    """
    
    def __init__(
        self,
        config_manager: Optional[ConfigManager] = None,
        tools: Optional[List[Tool]] = None,
        max_steps: int = 20,
        auto_approve_readonly: bool = True
    ):
        """
        Initialize interactive agent.
        
        Args:
            config_manager: Configuration manager
            tools: List of available tools
            max_steps: Maximum number of steps to execute
            auto_approve_readonly: Auto-approve read-only operations
        """
        self.config_manager = config_manager or ConfigManager()
        self.agent = Agent(self.config_manager)
        self.tools = tools or []
        self.tool_executor = ToolExecutor(self.tools)
        self.max_steps = max_steps
        self.auto_approve_readonly = auto_approve_readonly
        
        # Risk scorer for determining if confirmation is needed
        self.risk_scorer = RiskScorer()
        
        # Execution history
        self.history: List[StepResult] = []
        self.conversation_context: List[Dict[str, str]] = []
    
    def execute_interactive(
        self,
        query: str,
        system_prompt: Optional[str] = None
    ) -> List[StepResult]:
        """
        Execute query interactively with step-by-step planning.
        
        Args:
            query: User query
            system_prompt: Optional system prompt (skill instructions)
            
        Returns:
            List of StepResult objects
        """
        self.history = []
        self.conversation_context = []
        
        # Build system prompt
        if not system_prompt:
            system_prompt = self._build_default_system_prompt()
        
        # Add platform context
        from clis.utils.platform import get_platform, get_shell
        platform = get_platform()
        shell = get_shell()
        
        # Simplified system prompt to avoid timeout
        enhanced_system = f"""{system_prompt if system_prompt else "You are a helpful assistant."}

Platform: {platform}, Shell: {shell}

Available tools: {', '.join([t.name for t in self.tools])}

INSTRUCTIONS:
- Respond with ONE action at a time
- Use tools to gather info, then generate commands
- Adapt based on results

RESPONSE FORMAT (choose one):

1. Tool call:
```tool_call
{{"tool": "tool_name", "parameters": {{}}, "reasoning": "why"}}
```

2. Command:
```command
{{"command": "cmd", "reasoning": "why", "risk_level": "low", "is_readonly": false}}
```

3. Complete:
```complete
{{"summary": "done"}}
```

Respond with your first action now."""
        
        # Initial query
        current_query = f"""User request: {query}

Start by analyzing the request and deciding the first step. What information do you need? What should be done first?

Respond with your first action (tool_call, command, or thinking)."""
        
        step_number = 0
        
        while step_number < self.max_steps:
            step_number += 1
            logger.debug(f"Interactive step {step_number}/{self.max_steps}")
            
            # Get LLM response
            response = self.agent.generate(
                current_query,
                enhanced_system,
                inject_context=False
            )
            
            logger.debug(f"LLM Response:\n{response}")
            
            # Parse response and execute action
            action = self._parse_action(response)
            
            if not action:
                # Invalid response, ask for clarification
                step_result = StepResult(
                    step_number=step_number,
                    action_type="thinking",
                    description="Invalid response format",
                    success=False,
                    error="Could not parse LLM response"
                )
                self.history.append(step_result)
                
                current_query = """Your previous response was not in a valid format.
Please respond with one of: tool_call, command, thinking, or complete."""
                continue
            
            action_type = action["type"]
            
            # Handle completion
            if action_type == "complete":
                step_result = StepResult(
                    step_number=step_number,
                    action_type="thinking",
                    description="Task completed",
                    success=True,
                    output=action.get("summary", "Task completed successfully")
                )
                self.history.append(step_result)
                break
            
            # Handle thinking
            if action_type == "thinking":
                step_result = StepResult(
                    step_number=step_number,
                    action_type="thinking",
                    description=action.get("thought", "Analyzing..."),
                    success=True,
                    output=action.get("next_action", "")
                )
                self.history.append(step_result)
                
                current_query = f"""Continue with your planned action: {action.get('next_action', 'proceed')}"""
                continue
            
            # Handle tool call
            if action_type == "tool_call":
                step_result = self._execute_tool_call(
                    step_number,
                    action["tool"],
                    action.get("parameters", {}),
                    action.get("reasoning", "")
                )
                self.history.append(step_result)
                
                # Build next query with result
                current_query = self._build_next_query_after_tool(step_result, query)
                continue
            
            # Handle command execution
            if action_type == "command":
                step_result = self._prepare_command_execution(
                    step_number,
                    action["command"],
                    action.get("reasoning", ""),
                    action.get("risk_level", "medium"),
                    action.get("is_readonly", False)
                )
                self.history.append(step_result)
                
                # Check if needs confirmation
                if step_result.needs_confirmation:
                    # Return to caller for confirmation
                    # Caller should check needs_confirmation and decide
                    return self.history
                
                # Auto-execute if approved
                execution_result = self._execute_command(step_result)
                
                # Build next query with result
                current_query = self._build_next_query_after_command(execution_result, query)
                continue
        
        # Max steps reached
        if step_number >= self.max_steps:
            step_result = StepResult(
                step_number=step_number,
                action_type="thinking",
                description="Maximum steps reached",
                success=False,
                error=f"Reached maximum of {self.max_steps} steps"
            )
            self.history.append(step_result)
        
        return self.history
    
    def _parse_action(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse LLM response to extract action."""
        # Try to extract tool_call
        tool_match = re.search(r'```tool_call\s*\n(.*?)\n```', response, re.DOTALL)
        if tool_match:
            try:
                data = json.loads(tool_match.group(1))
                data["type"] = "tool_call"
                return data
            except json.JSONDecodeError:
                pass
        
        # Try to extract command
        cmd_match = re.search(r'```command\s*\n(.*?)\n```', response, re.DOTALL)
        if cmd_match:
            try:
                data = json.loads(cmd_match.group(1))
                data["type"] = "command"
                return data
            except json.JSONDecodeError:
                pass
        
        # Try to extract thinking
        think_match = re.search(r'```thinking\s*\n(.*?)\n```', response, re.DOTALL)
        if think_match:
            try:
                data = json.loads(think_match.group(1))
                data["type"] = "thinking"
                return data
            except json.JSONDecodeError:
                pass
        
        # Try to extract complete
        complete_match = re.search(r'```complete\s*\n(.*?)\n```', response, re.DOTALL)
        if complete_match:
            try:
                data = json.loads(complete_match.group(1))
                data["type"] = "complete"
                return data
            except json.JSONDecodeError:
                pass
        
        return None
    
    def _execute_tool_call(
        self,
        step_number: int,
        tool_name: str,
        parameters: Dict[str, Any],
        reasoning: str
    ) -> StepResult:
        """Execute a tool call."""
        logger.info(f"Step {step_number}: Calling tool '{tool_name}' - {reasoning}")
        
        result = self.tool_executor.execute(tool_name, parameters)
        
        return StepResult(
            step_number=step_number,
            action_type="tool_call",
            description=f"Tool: {tool_name} - {reasoning}",
            success=result.success,
            output=result.output if result.success else "",
            error=result.error if not result.success else None,
            needs_confirmation=False  # Tool calls don't need confirmation
        )
    
    def _prepare_command_execution(
        self,
        step_number: int,
        command: str,
        reasoning: str,
        risk_level: str,
        is_readonly: bool
    ) -> StepResult:
        """Prepare command for execution (check if confirmation needed)."""
        logger.info(f"Step {step_number}: Command - {command}")
        
        # Calculate risk score
        risk_score = self.risk_scorer.score(command)
        
        # Determine if confirmation is needed
        needs_confirmation = not (
            self.auto_approve_readonly and 
            is_readonly and 
            risk_score < 30  # Low risk threshold
        )
        
        return StepResult(
            step_number=step_number,
            action_type="command",
            description=f"{reasoning}\nCommand: {command}",
            success=True,  # Not executed yet
            needs_confirmation=needs_confirmation,
            risk_level=risk_level
        )
    
    def _execute_command(self, step_result: StepResult) -> StepResult:
        """Actually execute a command (after confirmation if needed)."""
        # Extract command from description
        command = step_result.description.split("Command: ", 1)[1] if "Command: " in step_result.description else ""
        
        if not command:
            step_result.success = False
            step_result.error = "No command to execute"
            return step_result
        
        # Execute using tool executor
        result = self.tool_executor.execute("execute_command", {"command": command})
        
        step_result.success = result.success
        step_result.output = result.output
        step_result.error = result.error if not result.success else None
        
        return step_result
    
    def _build_next_query_after_tool(self, step_result: StepResult, original_query: str) -> str:
        """Build next query after tool execution."""
        return f"""Tool execution result:
- Tool: {step_result.description}
- Success: {step_result.success}
- Output: {step_result.output[:1000]}{'...(truncated)' if len(step_result.output) > 1000 else ''}
{f'- Error: {step_result.error}' if step_result.error else ''}

Original request: {original_query}

Based on this result, what should be the next step? Respond with your next action."""
    
    def _build_next_query_after_command(self, step_result: StepResult, original_query: str) -> str:
        """Build next query after command execution."""
        return f"""Command execution result:
- Command: {step_result.description}
- Success: {step_result.success}
- Output: {step_result.output[:1000]}{'...(truncated)' if len(step_result.output) > 1000 else ''}
{f'- Error: {step_result.error}' if step_result.error else ''}

Original request: {original_query}

Based on this result, what should be the next step? 
- If the task is complete, respond with ```complete```
- Otherwise, respond with your next action."""
    
    def _format_tools(self) -> str:
        """Format tool definitions for prompt."""
        if not self.tools:
            return "No tools available."
        
        tools_text = []
        for tool in self.tools:
            tools_text.append(f"- {tool.name}: {tool.description}")
        
        return "\n".join(tools_text)
    
    def _build_default_system_prompt(self) -> str:
        """Build default system prompt."""
        return """You are an intelligent command-line assistant that helps users accomplish tasks through step-by-step execution.

Your approach:
1. Gather information using tools
2. Plan one step at a time
3. Execute commands incrementally
4. Adapt based on results
5. Provide clear reasoning for each action"""
