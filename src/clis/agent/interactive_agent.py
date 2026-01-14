"""
Interactive Agent - ReAct Pattern

Reason → Act → Observe → Reason → Act → ...

This agent executes tasks step-by-step, thinking and adapting based on results.
"""

import json
import re
from typing import Any, Dict, Optional, Generator

from clis.agent.agent import Agent
from clis.agent.context_manager import ContextManager, ObservationType
from clis.config import ConfigManager
from clis.safety.risk_scorer import RiskScorer
from clis.tools.base import Tool, ToolExecutor
from clis.utils.logger import get_logger
from clis.utils.platform import get_platform, get_shell

logger = get_logger(__name__)


class InteractiveAgent:
    """
    True interactive agent following ReAct pattern.
    
    Each iteration:
    1. Reason: LLM thinks about what to do next
    2. Act: Execute one action (tool call or command)
    3. Observe: See the result
    4. Loop back to Reason with the new observation
    """
    
    def __init__(
        self,
        config_manager: Optional[ConfigManager] = None,
        tools: Optional[list[Tool]] = None,
        max_iterations: Optional[int] = None,
        skill_instructions: Optional[str] = None
    ):
        self.config_manager = config_manager or ConfigManager()
        self.agent = Agent(self.config_manager)
        self.tools = tools or []
        self.tool_executor = ToolExecutor(self.tools)
        self.risk_scorer = RiskScorer(self.config_manager)
        self.skill_instructions = skill_instructions  # Store skill instructions
        
        # Load max_iterations from config if not specified
        if max_iterations is None:
            try:
                safety_config = self.config_manager.load_safety_config()
                config_value = safety_config.agent.max_iterations
                if config_value == "auto":
                    # Auto mode: Agent decides when to stop, with a safety limit
                    self.auto_mode = True
                    self.max_iterations = safety_config.agent.auto_iterations_base  # Safety limit
                else:
                    # Fixed mode: Hard limit
                    self.auto_mode = False
                    self.max_iterations = int(config_value)
            except Exception as e:
                logger.warning(f"Failed to load agent config: {e}, using default")
                self.auto_mode = False
                self.max_iterations = 20
        else:
            self.auto_mode = False
            self.max_iterations = max_iterations
        
        # Intelligent context management
        self.context_manager = ContextManager(self.config_manager)
        
        # Track tool calls to avoid repetition
        self.tool_call_history = []
        
        # Load safety configuration
        try:
            self.safety_config = self.config_manager.load_safety_config()
        except Exception as e:
            logger.warning(f"Failed to load safety config: {e}")
            self.safety_config = None
    
    def execute(self, query: str, stream_thinking: bool = False) -> Generator[Dict[str, Any], None, None]:
        """
        Execute query interactively following ReAct pattern.
        
        ReAct: Reason → Act → Observe (synchronous loop)
        
        Args:
            query: User query
            stream_thinking: Whether to stream thinking process (for display only)
        
        Yields steps one by one:
        {
            "type": "thinking" | "tool_call" | "command" | "complete",
            "content": "...",
            "result": "..." (for actions),
            "needs_confirmation": bool (for commands)
        }
        """
        platform = get_platform()
        shell = get_shell()
        
        # Build base system prompt template (will be updated each iteration)
        def build_system_prompt(iteration: int) -> str:
            # Build tool call history summary (DYNAMIC - updates each iteration)
            tool_history_summary = ""
            if self.tool_call_history:
                recent_calls = self.tool_call_history[-5:]
                tool_history_summary = "\n\n📋 RECENT ACTIONS:\n"
                for i, call in enumerate(recent_calls, 1):
                    status = "✓" if call.get('success', True) else "✗"
                    tool_history_summary += f"{i}. {status} {call['tool']}({call['params']})\n"
                
                # Check for loops
                if len(recent_calls) >= 2:
                    last_call = f"{recent_calls[-1]['tool']}({recent_calls[-1]['params']})"
                    second_last = f"{recent_calls[-2]['tool']}({recent_calls[-2]['params']})"
                    if last_call == second_last:
                        tool_history_summary += "\n⚠️ WARNING: You're repeating the same call! Do something different!\n"
            
            # Get few-shot examples
            examples = self._get_few_shot_examples()
            
            # Get phase hint based on iteration
            phase_hint = self._get_phase_hint_simple(iteration)
            
            # Build skill instructions section if available
            skill_section = ""
            if self.skill_instructions:
                skill_section = f"""
📚 SKILL INSTRUCTIONS:
{self.skill_instructions}

Follow the above skill instructions carefully when executing this task.
"""
            
            return f"""You are an expert command-line assistant that executes tasks efficiently.

Platform: {platform} | Shell: {shell}
Available tools: {', '.join([t.name for t in self.tools])}

{examples}

🎯 CURRENT TASK:
User request: {query}

{skill_section}{phase_hint}

📋 TOOL DESCRIPTIONS:
- git_status: Check current git status
- git_diff: View changes in files
- git_add: Stage files for commit (can stage multiple: files=["a.py", "b.py"])
- git_commit: Commit staged changes with a message
- file_tree: View directory structure
- read_file: Read file content
- write_file: Write content to file (requires confirmation)
- delete_file: Delete a file (requires confirmation)
- search_files: Search for files by name pattern
- list_files: List files in a directory
- execute_command: Execute shell command (use only when no specific tool available)

⚠️ IMPORTANT RULES:
1. Don't call the same tool with same parameters 3+ times (causes loops)
2. After gathering info (2-3 iterations), START EXECUTING
3. For simple tasks (deletion, single commit), act immediately
4. When task is complete, respond with {{"type": "done", "summary": "..."}}
5. Use specific tools (delete_file, write_file) instead of execute_command
{tool_history_summary}

📤 RESPONSE FORMAT (respond with ONLY ONE action):
```action
{{"type": "tool", "tool": "tool_name", "params": {{"key": "value"}}}}
```
OR when complete:
```action
{{"type": "done", "summary": "Task completed successfully"}}
```
"""
        
        current_context = f"User request: {query}\n\nWhat's your first step?"
        
        # In auto mode, max_iterations is just a safety limit
        if self.auto_mode:
            logger.info(f"Auto mode: Agent will decide when to stop (safety limit: {self.max_iterations})")
        
        for iteration in range(self.max_iterations):
            if self.auto_mode:
                logger.info(f"Iteration {iteration + 1} (auto mode)")
            else:
                logger.info(f"Iteration {iteration + 1}/{self.max_iterations}")
            
            # Mark new iteration in context manager
            self.context_manager.next_iteration()
            
            # Yield iteration start (always, for counting)
            yield {"type": "iteration_start", "iteration": iteration + 1}
            
            # Build system prompt with CURRENT tool history (updates each iteration)
            system_prompt = build_system_prompt(iteration)
            
            # REASON: Ask LLM what to do next (synchronous with optional streaming display)
            if stream_thinking:
                yield {"type": "thinking_start", "content": f"Thinking... (iteration {iteration + 1})"}
                
                # Stream for display, but collect complete response
                response = ""
                for chunk in self.agent.generate_stream(
                    current_context,
                    system_prompt,
                    inject_context=False
                ):
                    response += chunk
                    yield {"type": "thinking_chunk", "content": chunk}
                
                yield {"type": "thinking_end", "content": response}
            else:
                # Non-streaming: just generate complete response
                response = self.agent.generate(
                    current_context,
                    system_prompt,
                    inject_context=False
                )
            
            logger.debug(f"LLM response: {response}")
            
            # Parse action
            action = self._parse_action(response)
            
            if not action:
                yield {"type": "error", "content": "Could not parse LLM response"}
                return  # Exit cleanly
            
            action_type = action.get("type")
            
            # Handle completion
            if action_type == "done":
                yield {
                    "type": "complete",
                    "content": action.get("summary", "Task completed")
                }
                return  # Exit cleanly
            
            # ACT: Execute the action
            if action_type == "tool":
                # Tool call - execute immediately
                tool_name = action.get("tool")
                params = action.get("params", {})
                
                # Check for problematic duplicate tool calls
                # Allow: git_status, git_log (查询类工具可以重复)
                # Detect: 连续3次调用相同的工具且参数相同
                call_signature = f"{tool_name}({params})"
                
                # 只检查最近的连续调用
                recent_same_calls = []
                for call in reversed(self.tool_call_history[-3:]):
                    call_sig = f"{call['tool']}({call['params']})"
                    if call_sig == call_signature:
                        recent_same_calls.append(call)
                    else:
                        break  # 遇到不同的调用就停止
                
                # 如果连续3次都是相同调用,说明陷入循环
                if len(recent_same_calls) >= 2:
                    observation = f"⚠️ LOOP DETECTED: You called {tool_name} {len(recent_same_calls)+1} times in a row! CHANGE YOUR APPROACH!"
                    
                    self.tool_call_history.append({
                        "tool": tool_name,
                        "params": params,
                        "success": False,
                        "loop_detected": True
                    })
                    
                    self.context_manager.add_observation(
                        content=observation,
                        obs_type=ObservationType.ERROR,
                        is_critical=True,
                        tool_name=tool_name
                    )
                    
                    yield {
                        "type": "tool_result",
                        "content": observation,
                        "success": False
                    }
                else:
                    # Check if tool requires confirmation
                    tool = self.tool_executor.get_tool(tool_name)
                    requires_confirmation = getattr(tool, 'requires_confirmation', False) if tool else False
                    
                    # Calculate risk score for this tool operation
                    risk_score = self.risk_scorer.score_tool_operation(tool_name, params)
                    risk_level = self.risk_scorer.get_risk_level(risk_score)
                    
                    # Override requires_confirmation based on risk level
                    if risk_level in ["high", "critical"]:
                        requires_confirmation = True
                    
                    yield {
                        "type": "tool_call",
                        "content": f"Calling {tool_name}",
                        "tool": tool_name,
                        "params": params,
                        "requires_confirmation": requires_confirmation,
                        "risk_score": risk_score,
                        "risk_level": risk_level
                    }
                    
                    # If tool requires confirmation, wait for user approval
                    if requires_confirmation:
                        # Caller (CLI) will handle confirmation
                        return
                    
                    # Execute
                    result = self.tool_executor.execute(tool_name, params)
                    
                    # Track tool call
                    self.tool_call_history.append({
                        "tool": tool_name,
                        "params": params,
                        "success": result.success
                    })
                    
                    # Prepare content for return (use error message if failed)
                    if result.success:
                        content = result.output[:500] if result.output else "Success"
                    else:
                        content = result.error if result.error else (result.output[:500] if result.output else "Unknown error")
                    
                    # Add to context manager
                    obs_type = ObservationType.ERROR if not result.success else ObservationType.TOOL_RESULT
                    self.context_manager.add_observation(
                        content=f"Tool '{tool_name}' result: {content}",
                        obs_type=obs_type,
                        is_critical=not result.success,
                        tool_name=tool_name
                    )
                    
                    yield {
                        "type": "tool_result",
                        "content": content,
                        "success": result.success
                    }
                
            elif action_type == "command":
                # Command - evaluate risk and may need confirmation
                command = action.get("command")
                
                # Evaluate risk using risk scorer
                risk_score = self.risk_scorer.score(command)
                risk_level = self.risk_scorer.get_risk_level(risk_score)
                
                # Determine if confirmation is needed
                needs_confirm = risk_level in ["medium", "high", "critical"]
                
                if risk_level == "critical":
                    # Block critical commands
                    error_msg = f"Command blocked due to critical risk: {command}"
                    self.context_manager.add_observation(
                        content=error_msg,
                        obs_type=ObservationType.ERROR,
                        is_critical=True
                    )
                    yield {
                        "type": "error",
                        "content": error_msg
                    }
                    continue
                
                yield {
                    "type": "command",
                    "content": command,
                    "risk": risk_level,
                    "risk_score": risk_score,
                    "needs_confirmation": needs_confirm
                }
                
                if needs_confirm:
                    # Wait for user confirmation
                    # Caller will handle this and call execute_command()
                    return
                
                # Execute command (low risk, auto-approved)
                result = self.tool_executor.execute("execute_command", {"command": command})
                
                # Add to context manager
                obs_type = ObservationType.ERROR if not result.success else ObservationType.COMMAND_RESULT
                self.context_manager.add_observation(
                    content=f"Command result: {result.output[:500]}",
                    obs_type=obs_type,
                    is_critical=not result.success
                )
                
                yield {
                    "type": "command_result",
                    "content": result.output[:500],
                    "success": result.success
                }
            
            else:
                # Unknown action type - record as error
                self.context_manager.add_observation(
                    content=f"Unknown action type: {action_type}",
                    obs_type=ObservationType.ERROR,
                    is_critical=True
                )
                yield {"type": "error", "content": f"Unknown action type: {action_type}"}
            
            # Build context for next iteration using context manager
            context_summary = self.context_manager.get_context()
            stats = self.context_manager.get_summary()
            phase_hint = self._get_phase_hint_simple(iteration + 1)
            
            current_context = f"""User request: {query}

📊 PROGRESS: Iteration {iteration + 1}/{self.max_iterations}
📊 CURRENT PHASE: {phase_hint}

Previous observations ({stats['total']} total, {stats['critical']} critical):
{context_summary}

⚠️ IMPORTANT:
- If you see "DUPLICATE" in observations, you're repeating yourself!
- DO NOT call the same tool with same params again
- If task is COMPLETE, respond with {{"type": "done", "summary": "..."}}
- Otherwise, take a DIFFERENT action to make progress

What's your next action?"""
        
        # Max iterations reached
        if self.auto_mode:
            yield {
                "type": "error",
                "content": f"Reached safety limit ({self.max_iterations} iterations). Agent did not complete the task."
            }
        else:
            yield {
            "type": "error",
            "content": f"Reached maximum iterations ({self.max_iterations})"
        }
    
    def _get_few_shot_examples(self) -> str:
        """
        生成 Few-shot Learning 示例来教会 LLM 正确的执行模式.
        
        Returns:
            包含多个示例的字符串
        """
        return """
═══════════════════════════════════════════════════════════════
📚 LEARN FROM THESE EXAMPLES - How to Handle Different Tasks:
═══════════════════════════════════════════════════════════════

Example 1: Simple File Deletion (1 step)
─────────────────────────────────────────
User: "Delete the test.py file"

✅ CORRECT Approach:
Iteration 1:
```action
{"type": "tool", "tool": "delete_file", "params": {"path": "test.py"}}
```
Observation: File deleted successfully
Iteration 2:
```action
{"type": "done", "summary": "Deleted test.py"}
```

❌ WRONG Approach (too many steps):
- Don't call git_status first
- Don't call file_tree to check if file exists
- Just delete it directly!

─────────────────────────────────────────
Example 2: Batch Commit (Multiple Files Separately)
─────────────────────────────────────────
User: "Commit all Python files one by one"

✅ CORRECT Approach:
Iteration 1: Check what files are modified
```action
{"type": "tool", "tool": "git_status", "params": {}}
```
Observation: Modified files: a.py, b.js, c.py, README.md

Iteration 2: Add FIRST Python file
```action
{"type": "tool", "tool": "git_add", "params": {"files": ["a.py"]}}
```

Iteration 3: Commit it
```action
{"type": "tool", "tool": "git_commit", "params": {"message": "Update a.py"}}
```

Iteration 4: Check remaining files
```action
{"type": "tool", "tool": "git_status", "params": {}}
```
Observation: Modified files: b.js, c.py, README.md

Iteration 5: Add SECOND Python file (skip b.js - not Python!)
```action
{"type": "tool", "tool": "git_add", "params": {"files": ["c.py"]}}
```

Iteration 6: Commit it
```action
{"type": "tool", "tool": "git_commit", "params": {"message": "Update c.py"}}
```

Iteration 7: Check remaining
```action
{"type": "tool", "tool": "git_status", "params": {}}
```
Observation: Modified files: b.js, README.md (no more Python files)

Iteration 8: Done!
```action
{"type": "done", "summary": "Committed 2 Python files: a.py, c.py"}
```

Key Pattern: git_add → git_commit → git_status → repeat for next file

─────────────────────────────────────────
Example 3: Single Commit (All Files Together)
─────────────────────────────────────────
User: "Commit all changes with message 'Update files'"

✅ CORRECT Approach:
Iteration 1: Check status
```action
{"type": "tool", "tool": "git_status", "params": {}}
```
Observation: Modified files: a.py, b.js, c.md

Iteration 2: Stage all files
```action
{"type": "tool", "tool": "git_add", "params": {"files": ["a.py", "b.js", "c.md"]}}
```

Iteration 3: Commit all together
```action
{"type": "tool", "tool": "git_commit", "params": {"message": "Update files"}}
```

Iteration 4: Done
```action
{"type": "done", "summary": "Committed 3 files together"}
```

─────────────────────────────────────────
Example 4: Information Query
─────────────────────────────────────────
User: "What files are in the src directory?"

✅ CORRECT Approach:
Iteration 1:
```action
{"type": "tool", "tool": "list_files", "params": {"path": "src"}}
```
Observation: Files: main.py, utils.py, config.py

Iteration 2:
```action
{"type": "done", "summary": "Found 3 files in src: main.py, utils.py, config.py"}
```

❌ WRONG: Don't call list_files multiple times!

─────────────────────────────────────────
Example 5: Complex Task (Needs Planning)
─────────────────────────────────────────
User: "Add a new feature to the authentication module"

✅ CORRECT Approach:
Iteration 1: Understand structure
```action
{"type": "tool", "tool": "file_tree", "params": {"max_depth": 2}}
```

Iteration 2: Read existing auth code
```action
{"type": "tool", "tool": "read_file", "params": {"path": "src/auth.py"}}
```

Iteration 3: Write new code
```action
{"type": "tool", "tool": "write_file", "params": {"path": "src/auth.py", "content": "..."}}
```

Iteration 4: Done
```action
{"type": "done", "summary": "Added new feature to auth module"}
```

═══════════════════════════════════════════════════════════════
🎯 KEY PRINCIPLES:
1. Simple tasks (deletion, single query) → Act immediately (1-2 steps)
2. Batch operations → Use a loop pattern (add → commit → check → repeat)
3. Complex tasks → Gather info first (2-3 steps), then execute
4. When task is complete → Always respond with {"type": "done"}
5. Don't repeat the same tool call 3+ times!
═══════════════════════════════════════════════════════════════
"""
    
    def _get_phase_hint_simple(self, iteration: int) -> str:
        """
        根据迭代次数给出简洁的阶段提示.
        
        Args:
            iteration: 当前迭代次数(从0开始)
            
        Returns:
            阶段提示
        """
        if iteration == 0:
            return "🟢 Phase: Initial Analysis - Understand the request and plan your approach"
        elif iteration <= 2:
            return "🔵 Phase: Information Gathering - Collect necessary data (if needed)"
        elif iteration <= 5:
            return "🟡 Phase: Execution - Time to take action! Stop gathering and start executing"
        else:
            return "🔴 Phase: Late Stage - You should be finishing up or already done!"
    
    def execute_tool(self, tool_name: str, params: Dict[str, Any], approved: bool = True) -> Dict[str, Any]:
        """
        Execute a tool after user confirmation.
        
        Args:
            tool_name: Tool name
            params: Tool parameters
            approved: Whether user approved the operation
            
        Returns:
            Result dictionary
        """
        if not approved:
            # Record rejection
            self.context_manager.add_observation(
                content=f"User rejected tool: {tool_name}",
                obs_type=ObservationType.REJECTION,
                is_critical=True
            )
            return {
                "type": "tool_result",
                "content": "Tool execution rejected by user",
                "success": False
            }
        
        result = self.tool_executor.execute(tool_name, params)
        
        # Prepare content for return (use error message if failed)
        if result.success:
            content = result.output[:500] if result.output else "Success"
        else:
            content = result.error if result.error else (result.output[:500] if result.output else "Unknown error")
        
        # Add to context manager
        obs_type = ObservationType.ERROR if not result.success else ObservationType.TOOL_RESULT
        self.context_manager.add_observation(
            content=f"Tool '{tool_name}' result: {content}",
            obs_type=obs_type,
            is_critical=not result.success,
            tool_name=tool_name
        )
        
        # Track tool call
        self.tool_call_history.append({
            "tool": tool_name,
            "params": params,
            "success": result.success
        })
        
        return {
            "type": "tool_result",
            "content": content,
            "success": result.success
        }
    
    def execute_command(self, command: str, approved: bool = True) -> Dict[str, Any]:
        """
        Execute a command after user confirmation.
        
        Args:
            command: Command to execute
            approved: Whether user approved the command
            
        Returns:
            Result dictionary
        """
        if not approved:
            # Record rejection
            self.context_manager.add_rejection(command, "User rejected command")
            return {
                "type": "command_result",
                "content": "Command rejected by user",
                "success": False
            }
        
        result = self.tool_executor.execute("execute_command", {"command": command})
        
        # Add to context manager
        obs_type = ObservationType.ERROR if not result.success else ObservationType.COMMAND_RESULT
        self.context_manager.add_observation(
            content=f"Command '{command}' result: {result.output[:500]}",
            obs_type=obs_type,
            is_critical=not result.success
        )
        
        return {
            "type": "command_result",
            "content": result.output[:500],
            "success": result.success
        }
    
    def _parse_action(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse LLM response to extract action."""
        # Try to find ```action ... ```
        match = re.search(r'```action\s*\n(.*?)\n```', response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Fallback: try to find any JSON
        match = re.search(r'\{.*?"type".*?\}', response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        
        return None
