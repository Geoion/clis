"""
Interactive Agent - ReAct Pattern

Reason → Act → Observe → Reason → Act → ...

This agent executes tasks step-by-step, thinking and adapting based on results.
"""

import json
import re
from datetime import datetime
from typing import Any, Dict, Optional, Generator

from clis.agent.agent import Agent
from clis.agent.context_manager import ContextManager, ObservationType
from clis.agent.working_memory import WorkingMemory
from clis.agent.episodic_memory import EpisodicMemory
from clis.agent.state_machine import TaskStateMachine
from clis.agent.memory_manager import MemoryManager
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
        
        # ============ New: Hybrid memory system ============
        # Working memory (in-memory)
        self.working_memory = WorkingMemory()
        
        # Episodic memory (task document) - created at task start
        self.episodic_memory: Optional[EpisodicMemory] = None
        
        # State machine
        self.state_machine = TaskStateMachine(max_iterations=self.max_iterations)
        
        # Memory manager
        self.memory_manager = MemoryManager()
        
        # Current task ID
        self.current_task_id: Optional[str] = None
    
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
        # ============ 初始化记忆系统 ============
        # 创建任务记忆
        self.current_task_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        task_id, task_file = self.memory_manager.create_task_memory(query, self.current_task_id)
        self.episodic_memory = EpisodicMemory(task_id)
        self.episodic_memory.load_or_create(query)
        
        # 清空工作记忆
        self.working_memory.clear()
        
        logger.info(f"Task memory created: {task_file}")
        
        platform = get_platform()
        shell = get_shell()
        
        # 用于跟踪任务是否成功
        task_success = True
        
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

🖥️  SYSTEM INFORMATION:
Platform: {platform} | Shell: {shell}
Available tools: {', '.join([t.name for t in self.tools])}

⚠️  IMPORTANT: When providing platform-specific guidance, use ONLY the information for "{platform}". 
Do NOT list multiple platforms (e.g., "macOS/Windows" or "Linux/macOS") - be specific to the current platform.

{examples}

🎯 CURRENT TASK:
User request: {query}

{skill_section}{phase_hint}

📋 TOOL DESCRIPTIONS:

🔍 SEARCH & ANALYSIS:
- codebase_search: Semantic search (meaning-based, query like "how do we handle auth?")
- find_definition: Find where a symbol is defined (function, class, variable)
- find_references: Find all usages/references of a symbol
- get_symbols: Get outline of a file (all functions, classes, methods)
- search_files: Basic text search (literal matching, no regex)
- grep: Advanced search with regex and context support

📝 FILE OPERATIONS:
- read_file: Read file content (params: path, offset, limit)
- write_file: Write/create file (params: path, content) - requires confirmation
- edit_file: Edit using search-replace (params: path, old_content, new_content) - PREFERRED for modifications
- search_replace: Batch find-replace across multiple files (supports regex) - requires confirmation
- insert_code: Insert code at specific line (params: path, line, content)
- delete_lines: Delete specific lines (params: path, start_line, end_line)
- delete_file: Delete a file (params: path) - requires confirmation
- file_tree: View directory structure (params: path, max_depth, show_hidden, pattern)
- list_files: List files in a directory
- read_lints: Read linter errors for files

📦 GIT OPERATIONS:
- git_status: Check current git status
- git_diff: View changes in files
- git_add: Stage files for commit (can stage multiple: files=["a.py", "b.py"])
- git_commit: Commit staged changes with a message
- git_push: Push commits to remote
- git_pull: Pull updates from remote
- git_branch: List/create/delete branches
- git_checkout: Switch branches or restore files

💻 TERMINAL & SYSTEM:
- list_terminals: List all active terminals
- read_terminal_output: Read output from a terminal
- execute_command: Execute shell command (use only when no specific tool available)

⚠️ IMPORTANT RULES:
1. Don't call the same tool with same parameters 3+ times (causes loops)
2. After gathering info (2-3 iterations), START EXECUTING
3. For simple tasks (deletion, single commit), act immediately
4. When task is complete, respond with {{"type": "done", "summary": "..."}}
5. Use specific tools (delete_file, write_file, edit_file) instead of execute_command
6. **PARAMETER NAMING**: Always use correct parameter names:
   - codebase_search: query (natural language), target_directories, file_pattern, max_results
   - find_definition/find_references: symbol, path, file_pattern
   - get_symbols: path, symbol_types, include_private
   - search_replace: pattern, replacement, path, file_pattern, regex, dry_run
   - insert_code: path, line (0-indexed), content
   - delete_lines: path, start_line, end_line
   - search_files: pattern, path, file_pattern, case_sensitive, max_results (NO regex!)
   - grep: pattern, path, file_pattern, regex, ignore_case, max_results, context_lines (NO limit!)
   - edit_file: path, old_content, new_content (use for targeted edits)
   - write_file: path, content (use for new files or complete rewrites)
   - list_terminals: (no parameters)
   - read_terminal_output: terminal_id, tail_lines, grep_pattern
   - If unsure, check the tool description above carefully!
7. **ERROR HANDLING**: If a tool fails with an error:
   - DON'T immediately give up or repeat the same action
   - Analyze the error message and provide helpful guidance to the user
   - For "Cannot connect to Docker daemon": Tell user to start Docker Desktop/service
   - For "command not found": Tell user to install the missing tool
   - For "permission denied": Explain why and suggest solutions
   - For "unexpected keyword argument 'regex'": You tried to use grep parameters on search_files - use grep tool instead!
   - For "unexpected keyword argument 'limit'": Use max_results instead of limit for grep tool
   - For "unexpected keyword argument 'include'": Use file_pattern instead of include for search_files/grep
   - Mark as done with clear explanation of the problem and solution
8. **USER REJECTION HANDLING**: If user rejects a tool (see "User rejected tool" in recent actions):
   - DON'T just give up and mark as done
   - Ask the user if they want to modify the operation (e.g., delete fewer images)
   - Provide alternatives or ask for clarification
   - Only mark as done if the user clearly wants to abort the task
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
            
            # ============ 状态机检测 ============
            state_advice = self.state_machine.detect_state(iteration, self.working_memory)
            
            # 如果是紧急状态(循环或超时),强制提示
            if state_advice.is_urgent:
                logger.warning(f"Urgent state detected: {state_advice.message}")
                yield {
                    "type": "warning",
                    "content": f"{state_advice.message}\n建议: {'; '.join(state_advice.suggested_actions)}"
                }
            
            # 更新进度
            self.working_memory.update_phase(
                state_advice.state.value,
                f"{iteration + 1}/{self.max_iterations}"
            )
            self.episodic_memory.update_progress(
                state_advice.state.value,
                f"{iteration + 1}/{self.max_iterations}"
            )
            
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
                # ============ 完成任务记忆 ============
                summary = action.get("summary", "Task completed")
                self.episodic_memory.update_step("任务完成", "done")
                self.episodic_memory.update_next_action(f"✅ 已完成: {summary}")
                
                # 完成任务
                self.memory_manager.complete_task(
                    self.current_task_id,
                    success=task_success,
                    extract_knowledge=True
                )
                
                # 显示统计
                stats = self.working_memory.get_stats()
                logger.info(f"Task completed. Stats: {stats}")
                
                yield {
                    "type": "complete",
                    "content": summary,
                    "stats": stats,
                    "task_file": str(self.episodic_memory.get_file_path())
                }
                return  # Exit cleanly
            
            # ACT: Execute the action
            if action_type == "tool":
                # Tool call - execute immediately
                tool_name = action.get("tool")
                params = action.get("params", {})
                
                # ============ 更新工作记忆 ============
                self.working_memory.increment_tool(tool_name)
                
                # 特殊处理: 文件读取
                if tool_name == 'read_file':
                    file_path = params.get('path', '')
                    is_new = self.working_memory.add_file_read(file_path)
                    
                    if not is_new:
                        # 重复读取!强制警告
                        warning_msg = f"⚠️ 警告: 文件 '{file_path}' 已经读过!可能陷入循环。"
                        yield {
                            "type": "warning",
                            "content": warning_msg
                        }
                        self.episodic_memory.add_finding(
                            f"重复读取文件: {file_path}",
                            category="warning"
                        )
                
                # Check for problematic duplicate tool calls
                # Whitelist: Read-only tools that can be safely repeated
                readonly_tools = {
                    'read_file', 'list_files', 'file_tree', 'search_files', 'grep', 'get_file_info',
                    'git_status', 'git_log', 'git_diff', 
                    'docker_ps', 'docker_logs', 'docker_inspect', 'docker_stats', 'docker_images',
                    'system_info', 'check_command', 'get_env', 'list_processes', 'check_port',
                    'http_request'  # GET requests are typically read-only
                }
                
                # Only check for loops on non-readonly tools
                should_check_loop = tool_name not in readonly_tools
                
                if should_check_loop:
                    # Detect: 3 consecutive calls to the same tool with same parameters
                    call_signature = f"{tool_name}({params})"
                    
                    # Only check recent consecutive calls
                    recent_same_calls = []
                    for call in reversed(self.tool_call_history[-3:]):
                        call_sig = f"{call['tool']}({call['params']})"
                        if call_sig == call_signature:
                            recent_same_calls.append(call)
                        else:
                            break  # Stop when encountering a different call
                else:
                    recent_same_calls = []
                
                # If 3 consecutive calls are the same (for non-readonly tools), it indicates a loop
                if should_check_loop and len(recent_same_calls) >= 2:
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
                    
                    # If tool requires confirmation, we stop here
                    # CLI will handle confirmation and call execute_tool
                    # Then we'll continue on next iteration
                    if requires_confirmation:
                        # Don't execute tool here, let CLI handle it
                        # But don't return - we need to continue the loop
                        # Update context with the observation
                        current_context = f"Waiting for user confirmation for {tool_name}..."
                        continue  # Continue to next iteration of the for loop
                    
                    # Execute
                    result = self.tool_executor.execute(tool_name, params)
                    
                    # Track tool call
                    self.tool_call_history.append({
                        "tool": tool_name,
                        "params": params,
                        "success": result.success
                    })
                    
                    # ============ 更新记忆系统 ============
                    # 记录文件写入
                    if tool_name in ('write_file', 'edit_file'):
                        file_path = params.get('path', '')
                        self.working_memory.add_file_written(file_path)
                        self.episodic_memory.update_step(f"写入文件: {file_path}", "done")
                    
                    # 记录关键发现
                    if result.success and tool_name in ('read_file', 'search_files', 'file_tree'):
                        preview = result.output[:100] if result.output else ""
                        self.episodic_memory.add_finding(
                            f"从 {tool_name}({params}) 获取: {preview}...",
                            category="data"
                        )
                    
                    # Prepare content for return (use error message if failed)
                    if result.success:
                        content = result.output[:500] if result.output else "Success"
                    else:
                        content = result.error if result.error else (result.output[:500] if result.output else "Unknown error")
                        task_success = False  # 标记任务失败
                    
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
                    task_success = False
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
                
                # ============ 更新工作记忆 ============
                self.working_memory.add_command(command, result.success)
                if not result.success:
                    task_success = False
                
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
            
            # ============ 注入记忆系统到 prompt ============
            state_advice_text = self.state_machine.format_advice(state_advice)
            working_memory_text = self.working_memory.to_prompt()
            episodic_memory_text = self.episodic_memory.inject_to_prompt(include_log=False)
            
            current_context = f"""User request: {query}

{state_advice_text}

{working_memory_text}

{episodic_memory_text}

╭──────────────────────────────────────────────────────────────╮
│                  📜 最近观察 (OBSERVATIONS)                   │
╰──────────────────────────────────────────────────────────────╯

Previous observations ({stats['total']} total, {stats['critical']} critical):
{context_summary}

⚠️ IMPORTANT:
- 检查工作记忆中的"已读文件"列表,不要重复读取!
- 查看状态机建议,遵循当前阶段的指导
- 参考任务记忆中的已完成步骤和关键发现
- If task is COMPLETE, respond with {{"type": "done", "summary": "..."}}
- Otherwise, take a DIFFERENT action to make progress

What's your next action?"""
        
        # Max iterations reached
        # ============ 标记任务失败 ============
        self.episodic_memory.update_step("任务未完成(达到迭代上限)", "done")
        self.memory_manager.complete_task(
            self.current_task_id,
            success=False,
            extract_knowledge=False
        )
        
        if self.auto_mode:
            yield {
                "type": "error",
                "content": f"Reached safety limit ({self.max_iterations} iterations). Agent did not complete the task.",
                "task_file": str(self.episodic_memory.get_file_path())
            }
        else:
            yield {
                "type": "error",
                "content": f"Reached maximum iterations ({self.max_iterations})",
                "task_file": str(self.episodic_memory.get_file_path())
            }
    
    def _get_few_shot_examples(self) -> str:
        """
        Generate Few-shot Learning examples to teach the LLM the correct execution pattern.
        
        Returns:
            String containing multiple examples
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

─────────────────────────────────────────
Example 6: Edit Existing File (Preferred for modifications)
─────────────────────────────────────────
User: "Change the log level from DEBUG to INFO in config.py"

✅ CORRECT Approach (use edit_file):
Iteration 1: Read current content
```action
{"type": "tool", "tool": "read_file", "params": {"path": "config.py"}}
```

Iteration 2: Edit specific part
```action
{"type": "tool", "tool": "edit_file", "params": {"path": "config.py", "old_string": "log_level = 'DEBUG'", "new_string": "log_level = 'INFO'"}}
```

Iteration 3: Done
```action
{"type": "done", "summary": "Changed log level from DEBUG to INFO"}
```

❌ WRONG: Don't use write_file for small changes (overwrites entire file)

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
        Provide concise phase hints based on iteration count.
        
        Args:
            iteration: Current iteration number (starting from 0)
            
        Returns:
            Phase hint string
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
            # 记录到任务文档
            if self.episodic_memory:
                self.episodic_memory.add_finding(
                    f"用户拒绝工具: {tool_name}({params})",
                    category="rejection"
                )
            return {
                "type": "tool_result",
                "content": "Tool execution rejected by user",
                "success": False
            }
        
        result = self.tool_executor.execute(tool_name, params)
        
        # ============ 更新工作记忆 ============
        if self.working_memory:
            self.working_memory.increment_tool(tool_name)
            
            if tool_name == 'read_file':
                file_path = params.get('path', '')
                self.working_memory.add_file_read(file_path)
            elif tool_name in ('write_file', 'edit_file'):
                file_path = params.get('path', '')
                self.working_memory.add_file_written(file_path)
        
        # 更新任务文档
        if self.episodic_memory and result.success:
            if tool_name in ('write_file', 'edit_file'):
                file_path = params.get('path', '')
                self.episodic_memory.update_step(f"写入文件: {file_path}", "done")
        
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
            # 记录到任务文档
            if self.episodic_memory:
                self.episodic_memory.add_finding(
                    f"用户拒绝命令: {command}",
                    category="rejection"
                )
            return {
                "type": "command_result",
                "content": "Command rejected by user",
                "success": False
            }
        
        result = self.tool_executor.execute("execute_command", {"command": command})
        
        # ============ 更新工作记忆 ============
        if self.working_memory:
            self.working_memory.add_command(command, result.success)
        
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
