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
        max_iterations: int = 20
    ):
        self.config_manager = config_manager or ConfigManager()
        self.agent = Agent(self.config_manager)
        self.tools = tools or []
        self.tool_executor = ToolExecutor(self.tools)
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
        
        # Build tool call history summary
        tool_history_summary = ""
        if self.tool_call_history:
            recent_calls = self.tool_call_history[-5:]
            tool_history_summary = "\n\n🚫 ALREADY CALLED (DON'T REPEAT):\n"
            for call in recent_calls:
                tool_history_summary += f"- {call['tool']}({call['params']})\n"
            tool_history_summary += "\n⚠️ If you call these again, you will FAIL!\n"
        
        # Analyze task type
        task_analysis = self._analyze_task(query)
        
        system_prompt = f"""You are a command-line assistant. Platform: {platform}, Shell: {shell}

Available tools: {', '.join([t.name for t in self.tools])}

🚨 CRITICAL RULES (VIOLATION = FAILURE):
1. ⚠️ NEVER EVER repeat a tool call you already made
2. ⚠️ Check "ALREADY CALLED" list below - DON'T call those again
3. ⚠️ If you see duplicate warnings in observations, CHANGE YOUR APPROACH
4. ⚠️ After iteration 3, STOP gathering and START executing
5. ⚠️ For batch commits: git_add → git_commit → move to NEXT file
6. ⚠️ When task is complete, respond with {{"type": "done", "summary": "..."}}

TASK ANALYSIS:
{task_analysis}

EXECUTION STRATEGY FOR BATCH COMMITS:
Step 1: git_status → get file list
Step 2: Pick FIRST file → git_diff (if needed)
Step 3: git_add(files=["first_file.py"])
Step 4: git_commit(message="...")
Step 5: Pick NEXT file (DIFFERENT from previous) → repeat steps 3-4
Step 6: When all files committed → {{"type": "done"}}

TOOL USAGE:
- git_status: Check current git status (call ONCE)
- git_diff: View file changes for ONE file at a time
- git_add: Stage ONE file: git_add(files=["path/to/file.py"])
- git_commit: Commit staged file: git_commit(message="description")
- file_tree: See directory structure (call ONCE)
- read_file: Read file content (if you need to understand changes)
{tool_history_summary}

FORMAT (respond with ONLY ONE action):
```action
{{"type": "tool", "tool": "name", "params": {{}}}}
```
OR
```action
{{"type": "done", "summary": "..."}}
```
"""
        
        current_context = f"User request: {query}\n\nWhat's your first step?"
        
        for iteration in range(self.max_iterations):
            logger.info(f"Iteration {iteration + 1}/{self.max_iterations}")
            
            # Mark new iteration in context manager
            self.context_manager.next_iteration()
            
            # Yield iteration start (always, for counting)
            yield {"type": "iteration_start", "iteration": iteration + 1}
            
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
                
                # Check for duplicate tool calls BEFORE executing
                call_signature = f"{tool_name}({params})"
                recent_calls = [f"{c['tool']}({c['params']})" for c in self.tool_call_history[-3:]]
                
                if call_signature in recent_calls:
                    # Duplicate detected - record it and add to history to prevent future duplicates
                    observation = f"⚠️ DUPLICATE CALL DETECTED: {tool_name}. You already called this. DO SOMETHING DIFFERENT!"
                    
                    # CRITICAL: Add to history to prevent checking same duplicate again
                    self.tool_call_history.append({
                        "tool": tool_name,
                        "params": params,
                        "success": False,
                        "duplicate": True
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
                    yield {
                        "type": "tool_call",
                        "content": f"Calling {tool_name}",
                        "tool": tool_name,
                        "params": params
                    }
                    
                    # Execute
                    result = self.tool_executor.execute(tool_name, params)
                    
                    # Track tool call
                    self.tool_call_history.append({
                        "tool": tool_name,
                        "params": params,
                        "success": result.success
                    })
                    
                    # Add to context manager
                    obs_type = ObservationType.ERROR if not result.success else ObservationType.TOOL_RESULT
                    self.context_manager.add_observation(
                        content=f"Tool '{tool_name}' result: {result.output[:500]}",
                        obs_type=obs_type,
                        is_critical=not result.success,
                        tool_name=tool_name
                    )
                    
                    yield {
                        "type": "tool_result",
                        "content": result.output[:500],
                        "success": result.success
                    }
                
            elif action_type == "command":
                # Command - may need confirmation
                command = action.get("command")
                risk = action.get("risk", "medium")
                
                needs_confirm = risk in ["medium", "high"]
                
                yield {
                    "type": "command",
                    "content": command,
                    "risk": risk,
                    "needs_confirmation": needs_confirm
                }
                
                if needs_confirm:
                    # Wait for user confirmation
                    # Caller will handle this and call execute_command()
                    return
                
                # Execute command
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
            phase_hint = self._get_phase_hint(iteration + 1)
            
            # Determine next action hint based on task and progress
            next_action_hint = self._get_next_action_hint(query, iteration + 1)
            
            # Build progress summary
            committed_count = len([c for c in self.tool_call_history if c.get('tool') == 'git_commit'])
            progress_summary = f"Files committed so far: {committed_count}"
            
            current_context = f"""User request: {query}

📊 PROGRESS: Iteration {iteration + 1}/{self.max_iterations}
📊 {progress_summary}
📊 CURRENT PHASE: {phase_hint}

Previous observations ({stats['total']} total, {stats['critical']} critical):
{context_summary}

🎯 YOUR NEXT ACTION:
{next_action_hint}

⚠️ IMPORTANT:
- If you see "DUPLICATE" in observations, you're repeating yourself!
- DO NOT call the same tool with same params again
- If task is COMPLETE, respond with {{"type": "done", "summary": "..."}}
- Otherwise, take a DIFFERENT action to make progress

Respond with ONE action only:"""
        
        # Max iterations reached
        yield {
            "type": "error",
            "content": f"Reached maximum iterations ({self.max_iterations})"
        }
    
    def _analyze_task(self, query: str) -> str:
        """
        分析任务类型和需求.
        
        Args:
            query: 用户查询
            
        Returns:
            任务分析描述
        """
        query_lower = query.lower()
        
        # 检测批量提交任务
        if "commit" in query_lower:
            if any(kw in query_lower for kw in ["one by one", "逐个", "each file", "separately"]):
                return """
This is a BATCH COMMIT task:
- You need to commit multiple files SEPARATELY
- For EACH file: git_add(files=["file.py"]) → git_commit(message="...")
- Generate meaningful commit message based on file content
- Repeat for all modified files
"""
            elif any(kw in query_lower for kw in ["all", "所有", "together"]):
                return """
This is a SINGLE COMMIT task:
- Stage all files at once: git_add(all=True)
- Commit with one message: git_commit(message="...")
"""
        
        # 检测文件操作任务
        if any(kw in query_lower for kw in ["find", "search", "list"]):
            return """
This is an INFORMATION GATHERING task:
- Use file_tree, search_files, or list_files
- Present results and mark as done
"""
        
        # 检测 git 查询任务
        if any(kw in query_lower for kw in ["status", "diff", "log"]):
            return """
This is a GIT QUERY task:
- Use git_status, git_diff, or git_log
- Present results and mark as done
"""
        
        return "Standard task - analyze and execute step by step"
    
    def _get_phase_hint(self, iteration: int) -> str:
        """
        根据迭代次数给出阶段提示.
        
        Args:
            iteration: 当前迭代次数(从0开始)
            
        Returns:
            阶段提示
        """
        if iteration <= 2:
            return "Phase 1: Gather information (git_status, git_diff, file_tree)"
        elif iteration <= 5:
            return "⚠️ Phase 2: START EXECUTING (use git_add, git_commit)"
        else:
            return "🚨 Phase 2: You should be EXECUTING by now! Stop gathering info!"
    
    def _get_next_action_hint(self, query: str, iteration: int) -> str:
        """
        根据任务和进度给出具体的下一步建议.
        
        Args:
            query: 用户查询
            iteration: 当前迭代次数
            
        Returns:
            下一步行动建议
        """
        query_lower = query.lower()
        
        # 检测是否是批量提交任务
        is_batch_commit = "commit" in query_lower and any(
            kw in query_lower for kw in ["one by one", "逐个", "each file", "separately"]
        )
        
        if is_batch_commit:
            if iteration <= 2:
                return """
1. Use git_status to get list of modified files
2. DON'T call git_diff yet - wait until you have the file list
"""
            elif iteration == 3:
                return """
1. Now you have the file list
2. Pick the FIRST file from the list
3. Use git_diff on that ONE file to see changes
4. DON'T call git_diff on the same file again!
"""
            elif iteration >= 4:
                # Check what's been done
                committed_files = [
                    call for call in self.tool_call_history 
                    if call.get('tool') == 'git_commit'
                ]
                
                added_files = [
                    call for call in self.tool_call_history 
                    if call.get('tool') == 'git_add'
                ]
                
                if not committed_files:
                    if not added_files:
                        return """
🚨 CRITICAL: You should be executing by now!
EXACT NEXT STEP: git_add(files=["src/clis/agent/agent.py"])
Then: git_commit(message="Add Generator import and streaming support")
DON'T call git_diff or git_status again!
"""
                    else:
                        return """
🚨 You staged a file but didn't commit!
EXACT NEXT STEP: git_commit(message="your commit message here")
"""
                else:
                    # Get the last committed file to avoid repeating
                    last_commit_call = [c for c in self.tool_call_history if c.get('tool') == 'git_commit'][-1]
                    
                    return f"""
✅ Good! You've committed {len(committed_files)} file(s).
NEXT STEPS:
1. Call git_status to see remaining files
2. Pick a DIFFERENT file (not the one you just committed)
3. git_add(files=["new_file.py"]) → git_commit(message="...")
4. If no more files, respond with {{"type": "done", "summary": "Committed {len(committed_files)} files"}}
"""
        
        # 其他任务类型
        if iteration >= 4:
            return "You've gathered enough info. Execute the task now!"
        
        return "Gather necessary information, then execute."
    
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
