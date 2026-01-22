"""
PEVL Agent - Plan-Execute-Verify Loop with Self-Healing

Hybrid model architecture:
- Phase 0: Task Analysis (R1) - one-time
- Phase 1-3 Loop: Plan (R1) → Execute (Chat) → Verify (R1)
- Self-healing: Auto-replan on failure, max 3 rounds
"""

from typing import Dict, Any, List, Optional, Generator
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
import json

from clis.agent.agent import Agent
from clis.agent.planner import ExecutionPlan, PlanStep
from clis.agent.working_directory import WorkingDirectoryManager
from clis.agent.working_memory import WorkingMemory
from clis.agent.episodic_memory import EpisodicMemory
from clis.agent.memory_manager import MemoryManager
from clis.agent.vector_search import VectorSearch
from clis.agent.context_manager import ContextManager
from clis.agent.state_machine import TaskStateMachine, TaskState
from clis.config import ConfigManager
from clis.safety.risk_scorer import RiskScorer
from clis.tools.base import Tool, ToolExecutor, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TaskAnalysis:
    """Task analysis result"""
    complexity: str  # trivial | simple | medium | complex
    uncertainty: str  # low | medium | high
    task_type: str
    estimated_steps: int
    recommended_mode: str  # direct | fast | hybrid | explore
    reasoning: str
    model_config: Dict[str, str]


@dataclass
class Verification:
    """Verification result"""
    success: bool
    failed_steps: List[int]
    diagnosis: Dict[str, Any]
    should_replan: bool
    replan_suggestion: str
    reasoning: str


@dataclass
class ReplanDecision:
    """Replan decision"""
    decision: bool
    confidence: float
    reasoning: str
    suggested_changes: List[str]


class PEVLAgent:
    """
    Plan-Execute-Verify Loop Agent
    
    Features:
    - Hybrid model: R1 (planning/verification) + Chat/Qwen (execution)
    - Self-healing: Auto-replan on failure
    - Smart selection: R1 auto-determines mode
    - Loop control: Max 3 rounds
    """
    
    def __init__(
        self,
        config_manager: Optional[ConfigManager] = None,
        tools: Optional[List[Tool]] = None,
        max_rounds: int = 5,
        relevant_skills: Optional[List] = None
    ):
        """
        Initialize PEVL Agent
        
        Args:
            config_manager: Configuration manager
            tools: Tool list
            max_rounds: Maximum number of rounds (default: 5)
            relevant_skills: List of relevant skills for guidance
        """
        self.config_manager = config_manager or ConfigManager()
        self.tools = tools or []
        self.max_rounds = max_rounds
        self.relevant_skills = relevant_skills or []
        
        # LLM Agents - Will configure different models based on task analysis
        # Default to same agent
        self.analyzer_agent = Agent(self.config_manager)  # R1 for analysis
        self.planner_agent = Agent(self.config_manager)   # R1 for planning
        self.executor_agent = Agent(self.config_manager)  # Chat for execution
        self.verifier_agent = Agent(self.config_manager)  # R1 for verification
        
        # Tool executor
        self.tool_executor = ToolExecutor(self.tools)
        
        # ============ Memory System (fully aligned with ReAct) ============
        self.working_memory = WorkingMemory()
        self.episodic_memory: Optional[EpisodicMemory] = None
        self.memory_manager = MemoryManager()
        self.vector_search = VectorSearch()
        self.working_dir_manager = WorkingDirectoryManager()
        
        # ============ Smart Components (aligned with ReAct) ============
        # Context Manager - Smart context compression
        self.context_manager = ContextManager(self.config_manager)
        
        # State Machine - Loop and timeout detection
        # Configured for larger iterations since PEVL has round control
        self.state_machine = TaskStateMachine(max_iterations=max_rounds * 10)
        
        # Risk Scorer - Risk assessment
        self.risk_scorer = RiskScorer(self.config_manager)
        
        # Current task tracking
        self.current_task_id: Optional[str] = None
        self.total_cost: float = 0.0  # Accumulated cost tracking
        self.iteration_count: int = 0  # Total iteration count (for StateMachine)
    
    def execute(
        self,
        query: str,
        user_mode_override: Optional[str] = None,
        stream_thinking: bool = False
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Execute task (PEVL mode)
        
        Args:
            query: User query
            user_mode_override: User manual mode override (overrides R1 judgment)
            stream_thinking: Whether to stream thinking process (debug mode)
            
        Yields:
            Execution steps and results
        """
        # ============ Initialize Memory System ============
        self.current_task_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        task_id, task_file = self.memory_manager.create_task_memory(query, self.current_task_id)
        self.episodic_memory = EpisodicMemory(task_id)
        self.episodic_memory.load_or_create(query)
        self.working_memory.clear()
        
        logger.info(f"[PEVL] Task memory created: {task_file}")
        
        # ============ Search for Similar Historical Tasks ============
        self.similar_tasks_context = ""
        try:
            similar_tasks = self.vector_search.search_similar_tasks(query, top_k=3)
            if similar_tasks:
                logger.info(f"Found {len(similar_tasks)} similar historical tasks")
                self.episodic_memory.add_finding(
                    f"Found {len(similar_tasks)} similar historical tasks",
                    category="reference"
                )
                
                # Debug output
                if stream_thinking:
                    yield {
                        "type": "debug",
                        "content": f"📚 Loaded {len(similar_tasks)} similar tasks from history"
                    }
                
                # Format historical tasks for planning (efficient: use pre-extracted failure reasons)
                self.similar_tasks_context = "\n\n## 📚 Historical Experience\n\n"
                self.similar_tasks_context += "Similar tasks from history (learn from past experiences and avoid repeating mistakes):\n\n"
                for i, task in enumerate(similar_tasks, 1):
                    # Handle both tuple and dict formats
                    if isinstance(task, tuple):
                        task_id = task[0]
                        similarity_score = task[1]
                        description = task[2][:200]  # First 200 chars
                        failure_reason = None
                    else:
                        task_id = task.get('task_id', 'unknown')
                        similarity_score = task.get('similarity', 0.0)
                        description = task.get('description', '')[:200]
                        failure_reason = task.get('failure_reason')  # Pre-extracted from metadata
                    
                    self.similar_tasks_context += f"**Task {i}** (Similarity: {similarity_score:.2f}):\n"
                    self.similar_tasks_context += f"  Description: {description}\n"
                    
                    # Add failure reason if available (already extracted, no need to parse file!)
                    if failure_reason:
                        self.similar_tasks_context += f"  ⚠️ Failed: {failure_reason}\n"
                    
                    self.similar_tasks_context += "\n"
                
                logger.info(f"[PEVL] Loaded {len(similar_tasks)} historical tasks for context")
        except Exception as e:
            logger.warning(f"Failed to search similar tasks: {e}")
            self.similar_tasks_context = ""
        
        # ============ Phase 0: Task Analysis (R1, one-time) ============
        if not user_mode_override or user_mode_override == "auto":
            yield {
                "type": "phase",
                "phase": "analysis",
                "content": "Phase 0: Task Analysis & Mode Selection (DeepSeek-R1)..."
            }
            
            # Stream thinking process
            if stream_thinking:
                yield {"type": "thinking_start", "content": "R1 analyzing task in depth..."}
                
                # Build prompt
                prompt = self._build_analysis_prompt(query)
                
                # Stream generation
                analysis_result = ""
                for chunk in self.analyzer_agent.generate_stream(prompt):
                    analysis_result += chunk
                    yield {"type": "thinking_chunk", "content": chunk}
                
                yield {"type": "thinking_end"}
                
                # Parse result
                analysis = self._parse_task_analysis(analysis_result, query)
            else:
                analysis = self._phase0_analysis(query)
            
            yield {
                "type": "analysis_result",
                "content": f"Complexity: {analysis.complexity}, Uncertainty: {analysis.uncertainty}, Mode: {analysis.recommended_mode}",
                "analysis": analysis
            }
            
            self.episodic_memory.add_finding(
                f"Task analysis: {analysis.complexity}, mode: {analysis.recommended_mode}",
                category="analysis"
            )
            
            # Select mode based on analysis result
            if analysis.recommended_mode == "direct":
                # Very simple task, execute directly
                yield from self._direct_execute(query)
                return
            elif analysis.recommended_mode == "fast":
                # Simple deterministic task, fast Plan-Execute
                yield from self._fast_plan_execute(query, stream_thinking=stream_thinking)
                return
            # Otherwise enter PEVL loop
        else:
            # User manually specified mode, skip analysis
            analysis = None
            
            # Route to corresponding mode
            if user_mode_override == "direct":
                yield from self._direct_execute(query)
                return
            elif user_mode_override == "fast":
                yield from self._fast_plan_execute(query, stream_thinking=stream_thinking)
                return
            elif user_mode_override == "explore":
                # TODO: Implement explore mode or fallback to ReAct
                logger.warning("Explore mode not yet implemented in PEVL, using hybrid PEVL")
            # Otherwise continue to full PEVL loop (hybrid mode)
        
        # ============ PEVL Loop (max 3 rounds) ============
        context = []  # Accumulated context (failure info)
        
        for round_num in range(1, self.max_rounds + 1):
            # Internal round tracking (no UI display)
            self.episodic_memory.update_step(f"Round {round_num} started", "in_progress")
            self.episodic_memory.update_progress(
                f"round_{round_num}",
                f"Round {round_num}/{self.max_rounds}"
            )
            
            # Phase 1: Planning (R1)
            yield {
                "type": "phase",
                "phase": "planning",
                "content": f"Phase 1: Deep Planning (DeepSeek-R1)..."
            }
            
            # Stream planning thinking
            plan = None
            for event in self._phase1_planning(query, context, round_num, stream_thinking=stream_thinking):
                if isinstance(event, dict):
                    yield event
                else:
                    plan = event
            
            if not plan or plan.total_steps == 0:
                yield {"type": "error", "content": "Planning failed: No valid plan generated"}
                break
            
            yield {
                "type": "plan",
                "content": plan.to_markdown(),
                "plan": plan
            }
            
            self.episodic_memory.add_finding(
                f"Round {round_num} plan: {plan.total_steps} steps",
                category="plan"
            )
            
            # Phase 2: Execution (Chat)
            yield {
                "type": "phase",
                "phase": "execution",
                "content": f"Phase 2: Guided Execution (Qwen/Chat)..."
            }
            
            results = yield from self._phase2_execution(plan)
            
            # ============ OPTIMIZATION: Check if execution failed ============
            has_failure = any(not r.get('success', False) for r in results)
            
            if has_failure:
                # Skip verification, extract failure info and replan directly
                if round_num < self.max_rounds:
                    failed_steps = [r for r in results if not r.get('success', False)]
                    failure_info = {
                        "has_failures": True,
                        "failed_steps": [r.get('tool', 'unknown') for r in failed_steps],
                        "error_messages": [r.get('output', '')[:200] for r in failed_steps],
                        "root_cause": failed_steps[-1].get('output', 'Unknown error')[:300] if failed_steps else "Unknown"
                    }
                    
                    yield {
                        "type": "execution_failed",
                        "content": f"🔄 Adjusting plan based on the issue..."
                    }
                    
                    # Add failure info to context
                    context.append({
                        "round": round_num,
                        "plan": plan,
                        "results": results,
                        "failure_diagnosis": failure_info,
                        "suggested_changes": []
                    })
                    
                    self.episodic_memory.add_finding(
                        f"Round {round_num} execution failed: {failure_info['root_cause'][:100]}",
                        category="error"
                    )
                    
                    continue  # Next round
                else:
                    # Reached max rounds
                    yield {
                        "type": "error",
                        "content": f"Execution failed in final round {round_num}"
                    }
                    break
            
            # All steps succeeded, do quick verification
            yield {
                "type": "phase",
                "phase": "verification",
                "content": f"Quick Verification..."
            }
            
            # Simple verification without streaming
            verification = None
            for event in self._phase3_verification(plan, results, stream_thinking=False):
                if isinstance(event, dict):
                    yield event
                else:
                    verification = event
            
            if verification.success:
                # Successfully completed - Generate intelligent summary
                yield {
                    "type": "verification_result",
                    "content": f"✓ Task goal achieved",
                    "verification": verification
                }
                
                summary_text = self._generate_completion_summary(query, plan, results)
                
                self.episodic_memory.update_step(f"Task completed in round {round_num}", "done")
                self._complete_task(success=True, summary=f"Completed in {round_num} rounds")
                
                yield {
                    "type": "complete",
                    "content": f"Task completed in Round {round_num}",
                    "rounds": round_num,
                    "task_file": str(self.episodic_memory.get_file_path()),
                    "stats": self.working_memory.get_stats(),
                    "summary": summary_text
                }
                return
            
            # Verification failed - treat as execution failure, continue to next round
            if round_num < self.max_rounds:
                # Extract failure info from verification
                failure_info = {
                    "has_failures": False,
                    "verification_failed": True,
                    "root_cause": verification.diagnosis.get('root_cause', 'Task goal not achieved') if hasattr(verification, 'diagnosis') and verification.diagnosis else 'Task goal not achieved',
                    "failed_steps": verification.failed_steps if hasattr(verification, 'failed_steps') else []
                }
                
                yield {
                    "type": "execution_failed",
                    "content": f"🔄 Task goal not achieved, adjusting plan..."
                }
                
                # Add failure info to context for next round
                context.append({
                    "round": round_num,
                    "plan": plan,
                    "results": results,
                    "failure_diagnosis": failure_info,
                    "suggested_changes": []
                })
                
                self.episodic_memory.add_finding(
                    f"Round {round_num} verification failed: {failure_info['root_cause'][:100]}",
                    category="error"
                )
                
                continue  # Next round
            else:
                # Reached maximum rounds
                yield {
                    "type": "error",
                    "content": f"Task goal not achieved after {round_num} rounds"
                }
                break
        
        # Failed completion
        self.episodic_memory.update_step("Task failed after retries", "error")
        self._complete_task(success=False, summary=f"Failed after {round_num} rounds")
        
        yield {
            "type": "failed",
            "content": f"Task failed after {round_num} rounds",
            "rounds": round_num,
            "task_file": str(self.episodic_memory.get_file_path()),
            "stats": self.working_memory.get_stats()
        }
    
    def _phase0_analysis(self, query: str) -> TaskAnalysis:
        """Phase 0: Use R1 to analyze task and select mode"""
        prompt = f"""Analyze this task and select the optimal execution mode.

Task: {query}

Please perform deep analysis:

1. Complexity Assessment
   - Estimated steps: ?
   - Technology stack involved: ?
   - Has subtasks: ?
   
2. Uncertainty Assessment  
   - Environment dependencies: (ports, permissions, paths, versions, etc.)
   - Possible error points: ?
   - Key verification points: ?

3. Task Type Identification
   - Category: file_ops | code_gen | deployment | git | exploration | other
   - Requires creativity: ?
   - Has standard process: ?

4. Mode Recommendation

Based on the above analysis, recommend the optimal solution from the following options:

**Option A: Direct Execute** (1 Chat call)
  - Suitable for: Single-step task, extremely simple, no dependencies
  - Cost: Low, Speed: Very fast
  - Examples: "Create a file", "Read file content"
  
**Option B: Fast Plan-Execute** (Chat planning + blind execution)  
  - Suitable for: 2-3 steps, highly deterministic, no environment dependencies
  - Cost: Low, Speed: Fast
  - Examples: "Create project structure", "Simple Git commit"
  
**Option C: Hybrid PEVL** (R1 planning + Chat execution + R1 verification)
  - Suitable for: 3-6 steps, has uncertainty or verification requirements
  - Cost: Medium, Speed: Medium, Quality: High
  - Examples: "Deploy Flask service", "Docker containerization"
  
**Option D: Explore ReAct** (Chat free exploration)
  - Suitable for: Exploratory, information gathering, unclear goals
  - Cost: Medium, Speed: Slow, Flexibility: High
  - Examples: "Analyze this project", "Investigate why failed"

Please select the optimal solution and fully explain the reasoning.

Return JSON format:
```json
{{
  "complexity": "trivial|simple|medium|complex",
  "uncertainty": "low|medium|high",
  "task_type": "file_ops|code_gen|deployment|git|explore|other",
  "estimated_steps": 3,
  "recommended_mode": "direct|fast|hybrid|explore",
  "reasoning": "Detailed reasoning process...",
  "model_config": {{
    "planner": "deepseek-r1|deepseek-chat",
    "executor": "qwen-2.5-coder|deepseek-chat",
    "verifier": "deepseek-r1|deepseek-chat|none"
  }}
}}
```
"""
        
        try:
            response = self.analyzer_agent.generate(prompt)
            
            # Parse JSON
            import re
            json_match = re.search(r'```json\s*\n(.*?)\n```', response, re.DOTALL)
            if not json_match:
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
            
            if json_match:
                data = json.loads(json_match.group(1) if json_match.lastindex else json_match.group(0))
                
                return TaskAnalysis(
                    complexity=data.get('complexity', 'medium'),
                    uncertainty=data.get('uncertainty', 'medium'),
                    task_type=data.get('task_type', 'other'),
                    estimated_steps=data.get('estimated_steps', 4),
                    recommended_mode=data.get('recommended_mode', 'hybrid'),
                    reasoning=data.get('reasoning', ''),
                    model_config=data.get('model_config', {
                        'planner': 'deepseek-r1',
                        'executor': 'deepseek-chat',
                        'verifier': 'deepseek-r1'
                    })
                )
        except Exception as e:
            logger.error(f"Task analysis failed: {e}")
            # Fallback to default config
            return TaskAnalysis(
                complexity='medium',
                uncertainty='medium',
                task_type='other',
                estimated_steps=4,
                recommended_mode='hybrid',
                reasoning=f'Analysis failed, using default: {e}',
                model_config={
                    'planner': 'deepseek-r1',
                    'executor': 'deepseek-chat',
                    'verifier': 'deepseek-r1'
                }
            )
    
    def _explore_environment_readonly(self, query: str) -> Generator[str, None, None]:
        """
        Phase 1.1: Explore environment with read-only tools
        
        Args:
            query: User query
            
        Yields:
            Progress updates
            
        Returns:
            Exploration findings as formatted text
        """
        logger.info("[PEVL] Starting read-only exploration")
        
        # Track exploration attempts to detect loops
        exploration_tracker = {
            'attempts': [],  # List of (tool, params) tuples
            'results': [],   # List of result summaries
            'loop_count': 0
        }
        
        def is_repeated_attempt(tool, params):
            """Check if this exact attempt was made before"""
            signature = (tool, json.dumps(params, sort_keys=True))
            return signature in exploration_tracker['attempts']
        
        def is_similar_failure(result_summary):
            """Check if we got similar failure/truncation before"""
            if not exploration_tracker['results']:
                return False
            # Check last 2 results
            recent = exploration_tracker['results'][-2:]
            return result_summary in recent
        
        def suggest_alternative_tool(failed_tool):
            """Suggest alternative tool when one fails or loops"""
            alternatives = {
                'list_files': 'grep',      # If list fails, try direct search
                'file_tree': 'grep',       # If tree fails, try direct search
                'grep': 'read_file',       # If grep fails, try reading specific files
                'read_file': 'list_files'  # If read fails, try listing
            }
            return alternatives.get(failed_tool, 'file_tree')
        
        # Read-only tools for exploration
        readonly_tools = [
            'read_file', 'list_files', 'file_tree', 'grep', 'search_files',
            'git_status', 'git_log', 'git_diff', 'git_branch',
            'codebase_search', 'find_definition', 'find_references', 'get_symbols',
            'system_info', 'check_command', 'get_env'
        ]
        
        exploration_prompt = f"""You are exploring the environment to gather context for planning.

**Task**: {query}

**Available Read-Only Tools**: {', '.join(readonly_tools)}

**Smart Exploration Strategy**:
1. **Be Direct**: If looking for specific patterns (like TODO), use grep directly
2. **Avoid Redundancy**: Don't repeat the same tool with same params
3. **Handle Truncation**: If output is truncated, use more specific queries
4. **Stop Early**: Stop as soon as you have enough context (3-5 steps max)

**Tool Selection Priority** (use most direct tool first):
- Looking for patterns/keywords? → Use `grep` directly
- Need file list? → Use `list_files` (not file_tree if you just need names)
- Need file content? → Use `read_file` on specific files
- Need directory structure? → Use `file_tree` with max_depth=2

**Output Format** - For each step, output JSON:
```json
{{
  "reasoning": "Why I'm exploring this (be specific)",
  "tool": "tool_name",
  "params": {{"param": "value"}},
  "done": false
}}
```

When done: `{{"done": true, "summary": "What I learned"}}`

**IMPORTANT**: 
- Don't repeat failed attempts
- If output is truncated, try more specific query
- Use the most direct tool for your goal

Start exploring:
"""
        
        def is_truncated(output):
            """Detect if output is truncated"""
            if not output:
                return False
            truncation_indicators = [
                '...',
                'truncated',
                '(truncated)',
                'output truncated',
                '... (more)',
            ]
            output_lower = output.lower()
            return any(indicator in output_lower for indicator in truncation_indicators)
        
        def handle_truncation(tool, params, output):
            """Suggest better approach when output is truncated"""
            if tool == 'list_files':
                # Try grep directly instead
                return ('grep', {
                    'pattern': 'TODO',  # Assuming we're looking for TODOs
                    'path': params.get('path', '.'),
                    'max_results': 50
                })
            elif tool == 'file_tree':
                # Try with smaller max_depth
                new_params = params.copy()
                new_params['max_depth'] = min(params.get('max_depth', 3) - 1, 1)
                return (tool, new_params)
            elif tool == 'grep':
                # Add max_results limit
                new_params = params.copy()
                new_params['max_results'] = 20
                return (tool, new_params)
            return None
        
        findings = []
        max_steps = 5
        
        yield {"type": "info", "content": f"🔍 Starting exploration (max {max_steps} steps)"}
        
        for i in range(max_steps):
            # Progress indication
            yield {"type": "progress", "content": f"📊 Exploration step {i+1}/{max_steps}"}
            
            try:
                # Generate exploration action
                import time
                start_time = time.time()
                
                response = self.executor_agent.generate(exploration_prompt)
                
                elapsed = time.time() - start_time
                if elapsed > 20:
                    yield {"type": "warning", "content": f"⚠️ Step took {elapsed:.1f}s (slower than expected)"}
                
                
                # Parse JSON
                import re
                json_match = re.search(r'```json\s*\n(.*?)\n```', response, re.DOTALL)
                if not json_match:
                    # Try without code block
                    json_match = re.search(r'\{.*"done".*\}', response, re.DOTALL)
                    if not json_match:
                        logger.warning("[PEVL] Could not parse exploration response")
                        break
                
                data = json.loads(json_match.group(0) if not json_match.groups() else json_match.group(1))
                
                # Check if done
                if data.get('done'):
                    summary = data.get('summary', 'Exploration complete')
                    logger.info(f"[PEVL] Exploration done: {summary}")
                    findings.append(f"**Summary**: {summary}")
                    break
                
                # Execute tool
                tool_name = data.get('tool')
                tool_params = data.get('params', {})
                reasoning = data.get('reasoning', '')
                
                # Check for repeated attempts (loop detection)
                if is_repeated_attempt(tool_name, tool_params):
                    exploration_tracker['loop_count'] += 1
                    logger.warning(f"[PEVL] Detected repeated attempt: {tool_name}")
                    
                    yield {"type": "warning", "content": f"⚠️ Loop detected! Tried {tool_name} before. Forcing strategy change..."}
                    
                    # Force alternative tool
                    alternative = suggest_alternative_tool(tool_name)
                    yield {"type": "info", "content": f"💡 Switching to {alternative} instead"}
                    
                    # Update exploration prompt to force different approach
                    exploration_prompt += f"\n\n**IMPORTANT**: {tool_name} was already tried and didn't work. Use {alternative} instead.\n\nNext:"
                    continue
                
                # Record attempt
                signature = (tool_name, json.dumps(tool_params, sort_keys=True))
                exploration_tracker['attempts'].append(signature)
                
                yield {"type": "step_start", "content": f"🔍 Exploring: {reasoning}"}
                
                # Execute with timeout
                try:
                    result = self.tool_executor.execute(tool_name, tool_params)
                except Exception as e:
                    if "timeout" in str(e).lower():
                        logger.warning(f"[PEVL] Tool {tool_name} timed out")
                        yield {"type": "warning", "content": f"⏱️ {tool_name} timed out. Trying alternative..."}
                        
                        # Suggest alternative
                        alternative = suggest_alternative_tool(tool_name)
                        exploration_prompt += f"\n\n**Timeout**: {tool_name} timed out. Try {alternative} with simpler params.\n\nNext:"
                        continue
                    else:
                        raise
                
                if result.success:
                    # Check for truncation
                    output_truncated = is_truncated(result.output)
                    
                    finding = f"**{i+1}. {reasoning}**\n"
                    finding += f"Tool: `{tool_name}`\n"
                    finding += f"Result: {result.output[:300]}...\n"
                    
                    if output_truncated:
                        finding += f"⚠️ Output was truncated\n"
                    
                    findings.append(finding)
                    exploration_tracker['results'].append(result.output[:100])
                    
                    if output_truncated:
                        yield {"type": "warning", "content": f"⚠️ Output truncated. Adjusting strategy..."}
                        
                        # Suggest better approach
                        alternative_approach = handle_truncation(tool_name, tool_params, result.output)
                        if alternative_approach:
                            alt_tool, alt_params = alternative_approach
                            yield {"type": "info", "content": f"💡 Try {alt_tool} for more specific results"}
                            
                            # Update prompt with suggestion
                            exploration_prompt += f"\n\n**Step {i+1}**: Output was truncated. Try {alt_tool} with params {alt_params} for more specific results.\n\nNext:"
                        else:
                            yield {"type": "step_result", "content": f"✓ Found (truncated): {result.output[:100]}...", "success": True}
                            exploration_prompt += f"\n\n**Step {i+1}**:\n{reasoning}\nResult (truncated): {result.output[:200]}\n\nNext:"
                    else:
                        yield {"type": "step_result", "content": f"✓ Found: {result.output[:100]}...", "success": True}
                        
                        # Update prompt
                        exploration_prompt += f"\n\n**Step {i+1}**:\n{reasoning}\nResult: {result.output[:200]}\n\nNext:"
                else:
                    yield {"type": "step_result", "content": f"✗ Error: {result.error[:100]}", "success": False}
                    exploration_prompt += f"\n\n**Step {i+1}**: Failed - {result.error[:100]}\n\nNext:"
                
            except Exception as e:
                logger.error(f"[PEVL] Exploration error: {e}")
                break
        
        # Format findings with summary
        if findings:
            exploration_report = "## 🔍 Environment Exploration\n\n"
            exploration_report += "\n\n".join(findings)
            
            # Add statistics
            exploration_report += f"\n\n**Exploration Statistics**:\n"
            exploration_report += f"- Total steps: {len(findings)}\n"
            exploration_report += f"- Loops detected: {exploration_tracker['loop_count']}\n"
            exploration_report += f"- Tools used: {len(set(t for t, _ in exploration_tracker['attempts']))}\n"
            
            yield {"type": "info", "content": f"✓ Exploration complete: {len(findings)} steps, {exploration_tracker['loop_count']} loops avoided"}
            
            return exploration_report
        else:
            yield {"type": "warning", "content": "⚠️ Exploration completed with no findings"}
            return ""
    
    def _phase1_planning(
        self,
        query: str,
        context: List[Dict[str, Any]],
        round_num: int,
        stream_thinking: bool = False
    ) -> Generator[Optional[ExecutionPlan], None, None]:
        """
        Phase 1: Strategic planning with read-only exploration
        
        Phase 1.1: Read-only exploration (if round 1)
        Phase 1.2: Strategic guidance generation
        
        Args:
            query: Original query
            context: Failure information from previous rounds
            round_num: Current round number
            stream_thinking: Whether to stream thinking process
            
        Yields:
            ExecutionPlan object (via final yield/return)
        """
        # Phase 1.1: Read-only exploration (only in round 1)
        exploration_findings = ""
        if round_num == 1:
            yield {"type": "info", "content": "🔍 Phase 1.1: Exploring environment with read-only tools..."}
            
            exploration_findings = yield from self._explore_environment_readonly(query)
            
            if exploration_findings:
                yield {"type": "info", "content": f"✓ Exploration complete. Found relevant context."}
        
        # Build planning prompt with full context
        context_text = ""
        if context:
            context_text = "\n\n## 🔄 Previous Attempts\n\n"
            
            for ctx in context:
                round_num_ctx = ctx['round']
                plan = ctx.get('plan')
                results = ctx.get('results', [])
                failure_diagnosis = ctx.get('failure_diagnosis', {})
                
                context_text += f"### Round {round_num_ctx}\n\n"
                
                # Show what was attempted
                if plan and hasattr(plan, 'steps'):
                    context_text += "**Steps attempted:**\n"
                    for step in plan.steps:
                        context_text += f"- Step {step.id}: {step.description}\n"
                    context_text += "\n"
                
                # Show what succeeded and what failed
                if results:
                    succeeded = [r for r in results if r.get('success', False)]
                    failed = [r for r in results if not r.get('success', False)]
                    
                    if succeeded:
                        context_text += f"**✓ Completed ({len(succeeded)} steps):**\n"
                        for r in succeeded:
                            tool = r.get('tool', 'unknown')
                            params = r.get('params', {})
                            # Show key info about what was done
                            if tool == 'write_file':
                                context_text += f"  - Created file: {params.get('path', 'unknown')}\n"
                            elif tool == 'edit_file':
                                context_text += f"  - Modified file: {params.get('path', 'unknown')}\n"
                            elif tool == 'execute_command':
                                cmd = params.get('command', '')[:60]
                                context_text += f"  - Executed: {cmd}...\n"
                            else:
                                context_text += f"  - {tool}\n"
                        context_text += "\n"
                    
                    if failed:
                        context_text += f"**✗ Failed ({len(failed)} steps):**\n"
                        for r in failed:
                            tool = r.get('tool', 'unknown')
                            error = r.get('output', '')[:100]
                            context_text += f"  - {tool}: {error}\n"
                        context_text += "\n"
                
                # Show failure reason
                root_cause = failure_diagnosis.get('root_cause', 'Unknown')
                context_text += f"**Failure reason:** {root_cause}\n\n"
            
            context_text += "**IMPORTANT:** \n"
            context_text += "- DO NOT repeat steps that already succeeded\n"
            context_text += "- Build on existing work (files created, dependencies installed, etc.)\n"
            context_text += "- Focus ONLY on fixing the failure and completing remaining work\n"
            context_text += "- If files exist, use edit_file instead of write_file\n\n"
        
        # Add historical context if available
        historical_context = ""
        if hasattr(self, 'similar_tasks_context') and self.similar_tasks_context:
            historical_context = self.similar_tasks_context
        
        # Add working memory state (what's been done in current task)
        working_state = ""
        if round_num > 1:  # Only add for replanning
            working_state = "\n\n## 📋 Current Task State\n\n"
            
            # Files that have been created/modified
            if self.working_memory.files_written:
                working_state += "**Files created/modified:**\n"
                for f in self.working_memory.files_written:
                    working_state += f"- {f}\n"
                working_state += "\n"
            
            # Commands that have been executed
            if self.working_memory.commands_run:
                working_state += "**Recent commands executed:**\n"
                for cmd_info in self.working_memory.commands_run[-5:]:  # Last 5
                    cmd = cmd_info.get('cmd', '')[:60]
                    success = cmd_info.get('success', False)
                    status = "✓" if success else "✗"
                    working_state += f"{status} {cmd}...\n"
                working_state += "\n"
            
            # Known facts
            if self.working_memory.known_facts:
                working_state += "**Known facts:**\n"
                for fact in self.working_memory.known_facts[-5:]:  # Last 5 facts
                    working_state += f"- {fact}\n"
                working_state += "\n"
        
        # Add exploration findings to context
        exploration_context = ""
        if exploration_findings:
            exploration_context = f"\n{exploration_findings}\n"
        
        prompt = f"""You are a strategic task planner. Generate HIGH-LEVEL guidance based on environment exploration.

Task: {query}

This is round {round_num} of planning.
{exploration_context}
{context_text}
{working_state}
{historical_context}

Please perform deep analysis and planning:

## 1. Task Decomposition
Break down the task into 3-5 clear steps, each with:
- Clear goal
- Success criteria
- Possible risks
- Mitigation strategy

## 2. Tool Selection
Select appropriate tools and parameters for each step

Available tools and their parameters:
{self._get_tool_descriptions(max_tools=20)}

**CRITICAL**: Use EXACT parameter names:
- edit_file: path, old_content, new_content (NOT file_path, NOT content)
- write_file: path, content (NOT file_path)
- read_file: path (NOT file_path)
- execute_command: command (NOT cmd)

## 3. Dependency Analysis
- Dependencies between steps
- Required working directory

## 4. Verification Strategy
- How to verify each step's success
- How to determine overall task completion

Output JSON:
```json
{{
  "working_directory": "/path/to/work",
  "steps": [
    {{
      "id": 1,
      "goal": "Step goal description",
      "success_criteria": "Success criteria",
      "tool": "tool_name",
      "params": {{"param1": "value1"}},
      "risks": ["risk1", "risk2"],
      "mitigation": "Mitigation strategy",
      "estimated_risk": "low|medium|high"
    }}
  ],
  "final_verification": "How to verify overall task completion",
  "risks": ["overall_risk1", "overall_risk2"]
}}
```
"""
        
        try:
            # Stream thinking if enabled
            if stream_thinking:
                yield {"type": "thinking_start", "content": "R1 planning in depth..."}
                
                response = ""
                for chunk in self.planner_agent.generate_stream(prompt):
                    response += chunk
                    yield {"type": "thinking_chunk", "content": chunk}
                
                yield {"type": "thinking_end", "content": ""}
            else:
                response = self.planner_agent.generate(prompt)
            
            logger.debug(f"Planning response received, length: {len(response)}")
            
            # Parse plan
            plan = self._parse_plan_response(response, query)
            
            if plan:
                logger.info(f"[PEVL] Round {round_num} plan generated: {plan.total_steps} steps")
            
            yield plan  # Yield the final result
            
        except Exception as e:
            logger.error(f"Planning failed in round {round_num}: {e}")
            yield None  # Yield None on error
    
    def _phase2_execution(
        self,
        plan: ExecutionPlan
    ) -> Generator[List[Dict[str, Any]], None, None]:
        """
        Phase 2: Guided execution using Chat
        
        Args:
            plan: Execution plan
            
        Yields:
            Execution process events
            
        Returns:
            List of execution results
        """
        results = []
        
        # Set working directory
        if plan.working_directory:
            self.working_dir_manager.change_directory(plan.working_directory)
            yield {
                "type": "debug",
                "content": f"📁 Working directory: {plan.working_directory}"
            }
        
        # Execute plan based on format
        if plan.is_strategic:
            # Strategic plan: Enter ReAct mode immediately with guidance
            logger.info(f"[PEVL] Strategic plan detected, entering ReAct mode with {len(plan.step_guidance)} guidance steps")
            
            yield {
                "type": "info",
                "content": f"📋 Strategic plan ready. Entering ReAct mode with {len(plan.step_guidance)} goals..."
            }
            
            # Build guidance context
            guidance_context = self._build_strategic_context(plan)
            
            # Enter ReAct mode from the start
            react_results = yield from self._execute_with_react_guidance(
                plan=plan,
                guidance_context=guidance_context
            )
            
            return react_results
        
        elif plan.is_adaptive:
            # Adaptive plan: execute first step, then let ReAct handle rest
            steps_to_execute = [plan.first_step]
        else:
            # Legacy plan: execute all steps
            steps_to_execute = plan.steps
        
        for step in steps_to_execute:
            self.iteration_count += 1
            
            # ============ State Machine Detection ============
            state_advice = self.state_machine.detect_state(self.iteration_count, self.working_memory)
            
            if state_advice.is_urgent:
                logger.warning(f"[PEVL] Urgent state: {state_advice.message}")
                yield {
                    "type": "warning",
                    "content": f"Warning: {state_advice.message}"
                }
                
                # If severe loop detected, end this round early
                if state_advice.state == TaskState.STUCK:
                    logger.error(f"[PEVL] Loop detected in Phase 2, ending this round")
                    yield {
                        "type": "error",
                        "content": "Loop detected, ending current round"
                    }
                    break
            
            # ============ Risk Scoring ============
            tool_name = step.tool
            tool_params = step.params
            
            risk_score = self.risk_scorer.score_tool_operation(tool_name, tool_params)
            
            if risk_score > 80:
                logger.warning(f"[PEVL] High risk operation: {tool_name} (score: {risk_score})")
                yield {
                    "type": "warning",
                    "content": f"Warning: High risk operation: {tool_name} (risk score: {risk_score})"
                }
            
            yield {
                "type": "step_start",
                "step_id": step.id,
                "content": f"▶ Step {step.id}/{plan.total_steps}: {step.description}",
                "tool": step.tool,
                "params": step.params
            }
            
            # Execute step (with retry)
            step_result = self._execute_step_with_chat(step)
            results.append(step_result)
            
            # Add debug info
            logger.debug(f"[PEVL] Step {step.id} result: success={step_result.get('success')}, tool={step_result.get('tool')}")
            
            # ============ Simplified output display ============
            output = step_result.get('output', '')
            success = step_result.get('success', False)
            
            # For failed steps, show full error message (up to 1000 chars)
            # For successful steps, truncate long output
            if not success:
                display_output = output[:1000] if len(output) > 1000 else output
            else:
                if len(output) > 500:
                    display_output = output[:500] + "... (truncated)"
                else:
                    display_output = output
            
            yield {
                "type": "step_result",
                "step_id": step.id,
                "content": display_output,
                "success": success
            }
            
            # ============ Full Memory Integration (aligned with ReAct) ============
            tool_name = step_result.get('tool', 'unknown')
            tool_params = step_result.get('params', {})
            success = step_result.get('success', False)
            output = step_result.get('output', '')
            
            # Tool counting
            self.working_memory.increment_tool(tool_name)
            
            # File read tracking
            if tool_name == 'read_file':
                file_path = tool_params.get('path', '')
                if file_path:
                    is_new = self.working_memory.add_file_read(file_path)
                    if not is_new:
                        logger.warning(f"[PEVL] Duplicate file read: {file_path}")
            
            # File write tracking
            elif tool_name in ('write_file', 'edit_file', 'search_replace'):
                file_path = tool_params.get('path', '')
                if file_path:
                    self.working_memory.add_file_written(file_path)
                    self.working_memory.add_known_fact(f"File {file_path} modified")
                    self.episodic_memory.update_step(f"Modified: {file_path}", "done")
                    
                    # Debug output
                    yield {
                        "type": "debug",
                        "content": f"💾 Remembered: {file_path} modified"
                    }
            
            # Command execution tracking
            elif tool_name == 'execute_command':
                command = tool_params.get('command', '')
                if command:
                    self.working_memory.add_command(command, success, output)
                    self.episodic_memory.add_finding(
                        f"Command: {command[:100]}...",
                        category="command"
                    )
                    
                    # Debug output
                    status = "✓" if success else "✗"
                    cmd_short = command[:50] + "..." if len(command) > 50 else command
                    yield {
                        "type": "debug",
                        "content": f"📝 Logged command {status}: {cmd_short}"
                    }
            
            # Directory operation tracking
            elif tool_name == 'file_tree':
                path = tool_params.get('path', '')
                self.working_memory.add_known_fact(f"Listed directory: {path}")
            
            # Record results to episodic memory
            if success:
                preview = output[:150] if output else "Success"
                self.episodic_memory.add_finding(
                    f"Step {step.id}: {preview}",
                    category="result"
                )
            else:
                error = output[:150] if output else "Failed"
                self.episodic_memory.add_finding(
                    f"Step {step.id} failed: {error}",
                    category="error"
                )
                
                # ============ CRITICAL: Stop execution immediately on failure ============
                logger.warning(f"[PEVL] Step {step.id} failed, stopping execution")
                yield {
                    "type": "execution_stopped",
                    "content": f"⚠️ Execution stopped at step {step.id} due to failure",
                    "failed_step": step.id
                }
                break
        
        # ============ Adaptive Plan: Continue with ReAct ============
        if plan.is_adaptive and results and results[-1].get('success'):
            logger.info(f"[PEVL] First step completed, continuing with ReAct mode for remaining {len(plan.next_steps_guidance)} guidance steps")
            
            yield {
                "type": "info",
                "content": f"✓ First step completed. Continuing with ReAct mode for {len(plan.next_steps_guidance)} remaining goals..."
            }
            
            # Build guidance context for ReAct
            guidance_context = "\n**Remaining Goals:**\n"
            for i, guidance in enumerate(plan.next_steps_guidance, 1):
                guidance_context += f"\n{i}. **Goal**: {guidance.goal}\n"
                guidance_context += f"   **Success Criteria**: {guidance.success_criteria}\n"
                if guidance.backup_strategy:
                    guidance_context += f"   **Backup**: {guidance.backup_strategy}\n"
            
            guidance_context += f"\n**Overall Goal**: {plan.overall_goal}\n"
            
            # Continue with ReAct mode
            react_results = yield from self._continue_with_react(
                plan=plan,
                first_step_results=results,
                guidance_context=guidance_context
            )
            
            # Merge results
            results.extend(react_results)
        
        return results
    
    def _execute_step_with_chat(self, step: PlanStep, max_attempts: int = 2) -> Dict[str, Any]:
        """
        Execute a single step using Chat with lightweight reasoning and retry
        
        Args:
            step: Plan step
            max_attempts: Maximum number of attempts
            
        Returns:
            Execution result dictionary
        """
        context = ""
        
        for attempt in range(1, max_attempts + 1):
            try:
                # Directly use planned tool and params (no re-reasoning to avoid tool name errors)
                tool_name = step.tool
                tool_params = step.params
                
                logger.debug(f"[PEVL] Executing step {step.id} attempt {attempt}: {tool_name} with params {tool_params}")
                
                # Execute tool
                result = self.tool_executor.execute(tool_name, tool_params)
                
                # Return result directly (simple verification based on tool execution result)
                if result.success:
                    return {
                        'tool': tool_name,
                        'params': tool_params,
                        'output': result.output,
                        'success': True,
                        'attempts': attempt
                    }
                else:
                    # If failed and have more attempts, try again
                    if attempt < max_attempts:
                        logger.warning(f"[PEVL] Step {step.id} attempt {attempt} failed: {result.error[:200]}")
                        continue
                    
                    # Return failure after all attempts
                    return {
                        'tool': tool_name,
                        'params': tool_params,
                        'output': result.error,
                        'success': False,
                        'attempts': attempt
                    }
                
            except Exception as e:
                logger.error(f"Step {step.id} execution error: {e}")
                if attempt < max_attempts:
                    context += f"\nAttempt {attempt} exception: {e}\n"
                    continue
                
                return {
                    'tool': step.tool,
                    'params': step.params,
                    'output': str(e),
                    'success': False,
                    'attempts': attempt
                }
        
        # All attempts failed
        return {
            'tool': step.tool,
            'params': step.params,
            'output': 'All attempts failed',
            'success': False,
            'attempts': max_attempts
        }
    
    def _build_strategic_context(self, plan: ExecutionPlan) -> str:
        """
        Build context from strategic plan
        
        Args:
            plan: Strategic execution plan
            
        Returns:
            Formatted context string
        """
        context = f"**Task**: {plan.query}\n\n"
        context += f"**Overall Goal**: {plan.overall_goal}\n\n"
        
        # Recommended tools
        if plan.recommended_tools:
            context += "**Recommended Tools**:\n"
            for tool_rec in plan.recommended_tools:
                context += f"- **{tool_rec.tool}**: {tool_rec.reason}\n"
                context += f"  Typical use: {tool_rec.typical_use}\n"
            context += "\n"
        
        # Step guidance
        if plan.step_guidance:
            context += "**Step-by-Step Guidance**:\n"
            for i, guidance in enumerate(plan.step_guidance, 1):
                context += f"\n**Step {i}: {guidance.goal}**\n"
                context += f"Success criteria: {guidance.success_criteria}\n"
                if guidance.considerations:
                    context += "Considerations:\n"
                    for consideration in guidance.considerations:
                        context += f"  - {consideration}\n"
                if guidance.backup_strategy:
                    context += f"Backup: {guidance.backup_strategy}\n"
            context += "\n"
        
        # Lessons learned
        if plan.lessons_learned:
            context += "**Lessons Learned**:\n"
            for lesson in plan.lessons_learned:
                context += f"- {lesson}\n"
            context += "\n"
        
        # Risks
        if plan.risks:
            context += "**Risks to Consider**:\n"
            for risk in plan.risks:
                context += f"- {risk}\n"
            context += "\n"
        
        return context
    
    def _execute_with_react_guidance(
        self,
        plan: ExecutionPlan,
        guidance_context: str
    ) -> Generator[List[Dict[str, Any]], None, None]:
        """
        Execute task with ReAct mode from the start, guided by strategic plan
        
        Args:
            plan: Strategic execution plan
            guidance_context: Formatted guidance
            
        Yields:
            Progress updates
            
        Returns:
            List of execution results
        """
        logger.info("[PEVL] Starting ReAct execution with strategic guidance")
        
        # Create ReAct prompt with strategic guidance
        react_prompt = f"""You are executing a task with strategic guidance. Use ReAct pattern: Reasoning → Action → Observation.

{guidance_context}

**Available Tools**: {', '.join([t.name for t in self.tools])}

**ReAct Instructions**:
1. For each step, first REASON about what to do
2. Then take an ACTION (call a tool)
3. OBSERVE the result
4. Decide next action or if goal is achieved

**Important Guidelines**:
- Follow the recommended tools, but you can use others if needed
- Pay attention to considerations and backup strategies
- Do NOT use complex Python inline scripts in execute_command
- If you need complex processing, create a temporary file first
- Focus on achieving goals, not following rigid steps
- You can trigger mini-reasoning/mini-planning for complex sub-tasks

**Current Step**: Start with Step 1

Your reasoning and action:
"""
        
        # Use executor agent for ReAct
        max_iterations = len(plan.step_guidance) * 5  # Allow 5 iterations per guidance step
        results = []
        current_step = 1
        
        for iteration in range(1, max_iterations + 1):
            self.iteration_count += 1
            
            try:
                # State machine check
                state_advice = self.state_machine.detect_state(self.iteration_count, self.working_memory)
                if state_advice.is_urgent and state_advice.state == TaskState.STUCK:
                    logger.error(f"[PEVL] Loop detected in ReAct, stopping")
                    yield {
                        "type": "error",
                        "content": "Loop detected in ReAct mode"
                    }
                    break
                
                # Generate next action with reasoning
                yield {
                    "type": "step_start",
                    "content": f"▶ ReAct Iteration {iteration} (Step {current_step}/{len(plan.step_guidance)})"
                }
                
                response = self.executor_agent.generate(react_prompt)
                
                # Parse tool call from response
                tool_call = self._parse_tool_call_from_response(response)
                
                if not tool_call:
                    logger.warning("[PEVL] No tool call found in ReAct response, trying to extract from text")
                    # Try to continue or break
                    if "goal achieved" in response.lower() or "task complete" in response.lower():
                        logger.info("[PEVL] Task appears complete")
                        yield {
                            "type": "info",
                            "content": "✓ Task appears complete"
                        }
                        break
                    else:
                        logger.warning("[PEVL] Cannot parse action, skipping iteration")
                        continue
                
                # Execute tool
                result = self.tool_executor.execute(
                    tool_call['tool'],
                    tool_call['params']
                )
                
                results.append({
                    'tool': tool_call['tool'],
                    'params': tool_call['params'],
                    'output': result.output if result.success else result.error,
                    'success': result.success,
                    'iteration': iteration
                })
                
                # Update working memory
                if result.success:
                    self.working_memory.add_known_fact(f"Iteration {iteration}: {tool_call['tool']} succeeded")
                    self.episodic_memory.add_finding(
                        f"ReAct {iteration}: {result.output[:100]}",
                        category="result"
                    )
                else:
                    self.working_memory.add_known_fact(f"Iteration {iteration}: {tool_call['tool']} failed")
                    self.episodic_memory.add_finding(
                        f"ReAct {iteration} failed: {result.error[:100]}",
                        category="error"
                    )
                
                yield {
                    "type": "step_result",
                    "content": result.output[:300] if result.success else result.error[:300],
                    "success": result.success
                }
                
                # Update prompt with result
                react_prompt += f"\n\n**Iteration {iteration}**:\n"
                react_prompt += f"Reasoning: {response[:200]}...\n"
                react_prompt += f"Action: {tool_call['tool']} with {tool_call['params']}\n"
                react_prompt += f"Observation: {result.output[:300] if result.success else result.error[:300]}\n"
                react_prompt += f"\n**Next Step**: Continue with current step or move to next\n\nYour reasoning and action:"
                
                # Check if current step goal is achieved
                if len(plan.step_guidance) > current_step - 1:
                    current_guidance = plan.step_guidance[current_step - 1]
                    if self._check_step_goal_completion(current_guidance, results[-3:]):
                        logger.info(f"[PEVL] Step {current_step} goal achieved")
                        yield {
                            "type": "info",
                            "content": f"✓ Step {current_step} completed: {current_guidance.goal}"
                        }
                        current_step += 1
                        
                        # Check if all steps done
                        if current_step > len(plan.step_guidance):
                            logger.info("[PEVL] All guidance steps completed")
                            yield {
                                "type": "info",
                                "content": "✓ All guidance steps completed!"
                            }
                            break
                
            except Exception as e:
                logger.error(f"[PEVL] Error in ReAct iteration {iteration}: {e}")
                yield {
                    "type": "error",
                    "content": f"Error in iteration {iteration}: {str(e)[:100]}"
                }
                # Continue to next iteration instead of breaking
                continue
        
        return results
    
    def _check_step_goal_completion(
        self,
        guidance: 'StepGuidance',
        recent_results: List[Dict[str, Any]]
    ) -> bool:
        """
        Check if a step goal is completed
        
        Args:
            guidance: Step guidance
            recent_results: Recent execution results
            
        Returns:
            True if goal appears completed
        """
        # Simple heuristic: check if recent results are successful
        if not recent_results:
            return False
        
        # Check if recent results are successful
        recent_successes = sum(1 for r in recent_results if r.get('success'))
        return recent_successes >= len(recent_results) // 2
    
    def _continue_with_react(
        self,
        plan: ExecutionPlan,
        first_step_results: List[Dict[str, Any]],
        guidance_context: str
    ) -> Generator[List[Dict[str, Any]], None, None]:
        """
        Continue execution with ReAct mode after first step
        
        Args:
            plan: Execution plan with guidance
            first_step_results: Results from first step
            guidance_context: Formatted guidance for ReAct
            
        Yields:
            Progress updates
            
        Returns:
            List of execution results
        """
        logger.info("[PEVL] Entering ReAct mode with guidance")
        
        # Build context from first step
        first_step_output = first_step_results[0].get('output', '') if first_step_results else ''
        
        # Create ReAct prompt with guidance
        react_prompt = f"""Continue the task based on the first step results and guidance.

**Task**: {plan.query}

**First Step Completed**:
Tool: {first_step_results[0].get('tool', 'N/A')}
Output: {first_step_output[:500]}...

{guidance_context}

**Instructions**:
1. Review the first step output
2. Work through each remaining goal in order
3. Use the success criteria to verify completion
4. Apply backup strategies if primary approach fails
5. Keep track of progress towards the overall goal

**Available Tools**: {', '.join([t.name for t in self.tools])}

**Important**:
- Do NOT use complex Python inline scripts in execute_command
- Prefer simple shell commands or built-in tools
- If you need complex processing, create a temporary Python file first
- Focus on achieving the goals, not following a rigid plan

Continue with the next goal:
"""
        
        # Use executor agent for ReAct
        max_iterations = len(plan.next_steps_guidance) * 3  # Allow 3 iterations per guidance
        results = []
        
        for iteration in range(max_iterations):
            try:
                # Generate next action
                response = self.executor_agent.generate(react_prompt)
                
                # Parse tool call from response
                tool_call = self._parse_tool_call_from_response(response)
                
                if not tool_call:
                    logger.warning("[PEVL] No tool call found in ReAct response")
                    break
                
                # Execute tool
                yield {
                    "type": "step_start",
                    "content": f"▶ ReAct Step {iteration + 1}: {tool_call.get('description', 'Continuing task')}"
                }
                
                result = self.tool_executor.execute(
                    tool_call['tool'],
                    tool_call['params']
                )
                
                results.append({
                    'tool': tool_call['tool'],
                    'params': tool_call['params'],
                    'output': result.output if result.success else result.error,
                    'success': result.success
                })
                
                yield {
                    "type": "step_result",
                    "content": result.output[:200] if result.success else result.error[:200],
                    "success": result.success
                }
                
                # Update prompt with result
                react_prompt += f"\n\n**Action {iteration + 1}**:\nTool: {tool_call['tool']}\nResult: {result.output[:300] if result.success else result.error[:300]}\n\nNext action:"
                
                # Check if overall goal is achieved
                if self._check_goal_completion(plan.overall_goal, results):
                    logger.info("[PEVL] Overall goal achieved in ReAct mode")
                    yield {
                        "type": "info",
                        "content": "✓ Overall goal achieved!"
                    }
                    break
                
            except Exception as e:
                logger.error(f"[PEVL] Error in ReAct iteration {iteration}: {e}")
                break
        
        return results
    
    def _parse_tool_call_from_response(self, response: str) -> Optional[Dict[str, Any]]:
        """
        Parse tool call from LLM response
        
        Args:
            response: LLM response text
            
        Returns:
            Tool call dict or None
        """
        # Try to extract JSON tool call
        import re
        json_match = re.search(r'```json\s*\n(.*?)\n```', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except:
                pass
        
        # Try to extract tool name and params from text
        # This is a simple fallback - can be improved
        tool_match = re.search(r'Tool:\s*(\w+)', response)
        if tool_match:
            tool_name = tool_match.group(1)
            # Try to find params
            params_match = re.search(r'Params:\s*({.*?})', response, re.DOTALL)
            if params_match:
                try:
                    params = json.loads(params_match.group(1))
                    return {'tool': tool_name, 'params': params}
                except:
                    pass
        
        return None
    
    def _check_goal_completion(self, goal: str, results: List[Dict[str, Any]]) -> bool:
        """
        Check if goal is completed based on results
        
        Args:
            goal: Goal description
            results: Execution results
            
        Returns:
            True if goal appears to be completed
        """
        # Simple heuristic: check if we have successful results
        # In a more sophisticated implementation, this would use LLM to verify
        if not results:
            return False
        
        # Check if recent results are successful
        recent_successes = sum(1 for r in results[-3:] if r.get('success'))
        return recent_successes >= 2
    
    def _phase3_verification(
        self,
        plan: ExecutionPlan,
        results: List[Dict[str, Any]],
        stream_thinking: bool = False
    ) -> Generator[Verification, None, None]:
        """
        Phase 3: Use R1 for deep verification and diagnosis
        
        Args:
            plan: Execution plan
            results: List of execution results
            stream_thinking: Whether to stream thinking process
            
        Yields:
            Verification object (via final yield/return)
        """
        # Format execution report
        report = f"Task: {plan.query}\n\n"
        report += "Execution Status:\n\n"
        
        for i, (step, result) in enumerate(zip(plan.steps, results), 1):
            report += f"Step {i}: {step.description}\n"
            report += f"  Tool: {result.get('tool')}\n"
            report += f"  Success: {result.get('success')}\n"
            report += f"  Output: {result.get('output', '')[:200]}...\n\n"
        
        prompt = f"""{report}

Please perform deep verification and diagnosis:

## 1. Step-by-Step Check
Check each step individually:
- Was the step goal achieved?
- Does the output match expectations?
- Are there any hidden issues?

## 2. Overall Assessment
- Did all steps truly succeed?
- Was the core task objective achieved?
- Are there any omissions or errors?

## 3. Failure Diagnosis (if any failures)
Please analyze the root cause of failure in depth:
- Is it a planning issue? (missing steps, wrong order, improper parameters)
- Is it an execution issue? (tool failure, command error)
- Is it an environment issue? (port occupied, insufficient permissions, missing dependencies)

## 4. Replanning Suggestions
- Can this failure be resolved through replanning?
- If replanning, how should it be adjusted?

Return JSON:
```json
{{
  "success": true|false,
  "failed_steps": [1, 3],
  "diagnosis": {{
    "root_cause": "Detailed failure reason",
    "is_plan_issue": true|false,
    "is_execution_issue": true|false,
    "is_environment_issue": true|false
  }},
  "should_replan": true|false,
  "replan_suggestion": "Specific suggestions if replanning...",
  "reasoning": "Deep analysis reasoning process"
}}
```
"""
        
        try:
            # Stream thinking if enabled
            if stream_thinking:
                yield {"type": "thinking_start", "content": "R1 verifying in depth..."}
                
                response = ""
                for chunk in self.verifier_agent.generate_stream(prompt):
                    response += chunk
                    yield {"type": "thinking_chunk", "content": chunk}
                
                yield {"type": "thinking_end", "content": ""}
            else:
                response = self.verifier_agent.generate(prompt)
            
            # Parse verification result
            import re
            json_match = re.search(r'```json\s*\n(.*?)\n```', response, re.DOTALL)
            if not json_match:
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
            
            if json_match:
                data = json.loads(json_match.group(1) if json_match.lastindex else json_match.group(0))
                
                yield Verification(
                    success=data.get('success', False),
                    failed_steps=data.get('failed_steps', []),
                    diagnosis=data.get('diagnosis', {}),
                    should_replan=data.get('should_replan', False),
                    replan_suggestion=data.get('replan_suggestion', ''),
                    reasoning=data.get('reasoning', '')
                )
                return
        except Exception as e:
            logger.error(f"Verification parsing failed: {e}")
        
        # Fallback: simple judgment
        all_success = all(r.get('success', False) for r in results)
        yield Verification(
            success=all_success,
            failed_steps=[],
            diagnosis={'root_cause': 'Verification failed, simple check used'},
            should_replan=not all_success,
            replan_suggestion='',
            reasoning='Fallback verification'
        )
    
    def _should_replan(
        self,
        verification: Verification,
        round_num: int,
        context: List[Dict[str, Any]]
    ) -> ReplanDecision:
        """
        Use R1 to determine whether replanning should occur
        
        Args:
            verification: Verification result
            round_num: Current round number
            context: Historical context
            
        Returns:
            ReplanDecision object
        """
        prompt = f"""Round {round_num} execution failed. Please determine if replanning is worthwhile.

Failure Diagnosis:
{json.dumps(verification.diagnosis, ensure_ascii=False, indent=2)}

Please analyze in depth:

1. **Nature of Failure**: 
   - Can this failure be resolved by adjusting the plan?
   - Or is it an environment issue that cannot be changed through planning?
   
2. **Success Probability**:
   - If replanning, what is the likelihood of success? (give a 0-1 probability)
   - Why this confidence level?

3. **Cost-Benefit**:
   - Replanning will add ~$15-20 cost and 20-30 seconds of time
   - Is this investment worthwhile?
   
4. **Specific Adjustments**:
   - If replanning, how should the plan be adjusted?
   - List 2-3 key changes

Return JSON:
```json
{{
  "decision": true|false,
  "confidence": 0.75,
  "reasoning": "Detailed reasoning...",
  "suggested_changes": [
    "Change 1: Add port check step",
    "Change 2: Use alternative port",
    "Change 3: Add error handling"
  ]
}}
```
"""
        
        try:
            response = self.planner_agent.generate(prompt)
            
            # Parse decision
            import re
            json_match = re.search(r'```json\s*\n(.*?)\n```', response, re.DOTALL)
            if not json_match:
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
            
            if json_match:
                data = json.loads(json_match.group(1) if json_match.lastindex else json_match.group(0))
                
                return ReplanDecision(
                    decision=data.get('decision', False),
                    confidence=data.get('confidence', 0.0),
                    reasoning=data.get('reasoning', ''),
                    suggested_changes=data.get('suggested_changes', [])
                )
        except Exception as e:
            logger.error(f"Replan decision parsing failed: {e}")
        
        # Fallback: conservative decision (no retry)
        return ReplanDecision(
            decision=False,
            confidence=0.0,
            reasoning='Decision parsing failed, conservative choice',
            suggested_changes=[]
        )
    
    def _parse_plan_response(self, response: str, query: str) -> Optional[ExecutionPlan]:
        """
        Parse LLM plan response
        
        Args:
            response: LLM response text
            query: Original query
            
        Returns:
            ExecutionPlan object or None
        """
        import re
        import os
        
        # Try to extract JSON
        json_match = re.search(r'```json\s*\n(.*?)\n```', response, re.DOTALL)
        if not json_match:
            json_match = re.search(r'```\s*\n(.*?)\n```', response, re.DOTALL)
        
        if json_match:
            try:
                json_str = json_match.group(1)
                
                # Fix common JSON escape issues in shell commands
                # LLMs often generate regex patterns with backslashes that aren't properly escaped for JSON
                # We need to be careful not to break valid escapes like \n, \t, etc.
                # Strategy: Replace invalid escape sequences while preserving valid ones
                
                # First, protect valid escape sequences by temporarily replacing them
                valid_escapes = {
                    r'\"': '\x00QUOTE\x00',
                    r'\\': '\x00BACKSLASH\x00',
                    r'\/': '\x00SLASH\x00',
                    r'\b': '\x00BACKSPACE\x00',
                    r'\f': '\x00FORMFEED\x00',
                    r'\n': '\x00NEWLINE\x00',
                    r'\r': '\x00RETURN\x00',
                    r'\t': '\x00TAB\x00',
                }
                
                for escape, placeholder in valid_escapes.items():
                    json_str = json_str.replace(escape, placeholder)
                
                # Now fix remaining backslashes (these are the problematic ones)
                json_str = json_str.replace('\\', '\\\\')
                
                # Restore valid escape sequences
                for escape, placeholder in valid_escapes.items():
                    json_str = json_str.replace(placeholder, escape)
                
                data = json.loads(json_str)
                
                # Build ExecutionPlan
                plan = ExecutionPlan(
                    query=query,
                    working_directory=data.get('working_directory', os.getcwd()),
                    risks=data.get('risks', [])
                )
                
                # Parse steps
                for step_data in data.get('steps', []):
                    step = PlanStep(
                        id=step_data['id'],
                        description=step_data.get('goal', step_data.get('description', '')),
                        tool=step_data['tool'],
                        params=step_data['params'],
                        working_directory=step_data.get('working_directory'),
                        verify_with=step_data.get('success_criteria'),
                        depends_on=step_data.get('depends_on', []),
                        estimated_risk=step_data.get('estimated_risk', 'low')
                    )
                    
                    # Add extra attributes (risks, mitigation)
                    if 'risks' in step_data:
                        step.risks = step_data['risks']
                    if 'mitigation' in step_data:
                        step.mitigation = step_data['mitigation']
                    
                    plan.steps.append(step)
                
                plan.total_steps = len(plan.steps)
                
                # Validate plan
                if plan.total_steps == 0:
                    logger.error("Plan has no steps")
                    return None
                
                return plan
                
            except Exception as e:
                logger.error(f"Failed to parse plan JSON: {e}")
                return None
        
        logger.warning("Could not find JSON in plan response")
        return None
    
    def _direct_execute(self, query: str) -> Generator[Dict[str, Any], None, None]:
        """
        Direct execute mode (very simple tasks)
        Now with basic verification!
        
        Args:
            query: User query
            
        Yields:
            Execution events
        """
        yield {
            "type": "mode_selected",
            "content": "Direct Execute Mode (Chat)"
        }
        
        # Use Fast mode instead (which has proper planning and verification)
        # Direct mode is now just a wrapper to Fast mode with simplified output
        logger.info("[PEVL] Direct mode redirecting to Fast mode for better reliability")
        
        # Execute with Fast mode
        yield from self._fast_plan_execute(query, stream_thinking=False)
        
        # Note: We keep the "Direct execute completed" message for UX consistency
        # but internally use Fast mode for reliability
    
    def _fast_plan_execute(self, query: str, stream_thinking: bool = False) -> Generator[Dict[str, Any], None, None]:
        """
        Fast Plan-Execute mode (Chat planning + execution)
        
        Args:
            query: User query
            stream_thinking: Whether to stream thinking process (debug mode)
            
        Yields:
            Execution events
        """
        yield {
            "type": "mode_selected",
            "content": "Fast Mode (Chat Plan-Execute)"
        }
        
        # Phase 1: Fast planning (use Chat model to quickly generate plan)
        yield {
            "type": "phase",
            "phase": "fast_planning",
            "content": "Fast Planning (Chat)..."
        }
        
        try:
            # Stream planning output in debug mode
            if stream_thinking:
                yield {"type": "thinking_start", "content": "Fast planning with Chat model..."}
                
                # Collect streaming response
                prompt = self._build_fast_planning_prompt(query)
                response = ""
                for chunk in self.executor_agent.generate_stream(prompt):
                    response += chunk
                    yield {"type": "thinking_chunk", "content": chunk}
                
                yield {"type": "thinking_end"}
                
                # Parse the response to get plan
                plan = self._parse_fast_planning_response(response, query)
            else:
                plan = self._fast_planning(query)
            
            if not plan or plan.total_steps == 0:
                yield {"type": "error", "content": "Fast planning failed: No valid plan generated"}
                self._complete_task(success=False, summary="Fast planning failed")
                return
            
            yield {
                "type": "plan",
                "content": f"Plan generated: {plan.total_steps} steps",
                "plan": plan
            }
            
            # Phase 2: Execution (use Chat model)
            yield {
                "type": "phase",
                "phase": "fast_execution",
                "content": "Fast Execution (Chat)..."
            }
            
            results = yield from self._phase2_execution(plan)
            
            # Check if execution was stopped due to failure
            has_failure = any(not r.get('success', False) for r in results)
            
            if has_failure:
                # ============ OPTIMIZATION: Skip verification, go directly to replanning ============
                # Extract failure information from results
                failed_steps = [r for r in results if not r.get('success', False)]
                failure_info = {
                    "has_failures": True,
                    "failed_steps": [r.get('tool', 'unknown') for r in failed_steps],
                    "error_messages": [r.get('output', '')[:200] for r in failed_steps],
                    "root_cause": failed_steps[-1].get('output', 'Unknown error')[:300] if failed_steps else "Unknown"
                }
                
                yield {
                    "type": "execution_failed",
                    "content": f"🔄 Adjusting plan to address the issue...",
                    "failure_info": failure_info
                }
                
                # Enter full PEVL loop starting from round 2
                context = [{
                    "round": 1,
                    "plan": plan,
                    "results": results,
                    "failure_diagnosis": failure_info,
                    "suggested_changes": []
                }]
                
                # Continue with PEVL rounds 2-3
                for round_num in range(2, self.max_rounds + 1):
                    # Internal round tracking (no UI display)
                    
                    # Phase 1: Replanning (R1)
                    yield {
                        "type": "phase",
                        "phase": "planning",
                        "content": f"Phase 1: Deep Planning (DeepSeek-R1)..."
                    }
                    
                    # Stream planning thinking
                    new_plan = None
                    for event in self._phase1_planning(query, context, round_num, stream_thinking=stream_thinking):
                        if isinstance(event, dict):
                            yield event
                        else:
                            new_plan = event
                    
                    if not new_plan or new_plan.total_steps == 0:
                        yield {"type": "error", "content": "Replanning failed: No valid plan generated"}
                        break
                    
                    yield {
                        "type": "plan",
                        "content": new_plan.to_markdown(),
                        "plan": new_plan
                    }
                    
                    # Phase 2: Execution
                    yield {
                        "type": "phase",
                        "phase": "execution",
                        "content": f"Phase 2: Guided Execution (Qwen/Chat)..."
                    }
                    
                    new_results = yield from self._phase2_execution(new_plan)
                    
                    # Check if execution failed again
                    has_new_failure = any(not r.get('success', False) for r in new_results)
                    
                    if has_new_failure:
                        # Skip verification, update context for next round
                        failed_steps = [r for r in new_results if not r.get('success', False)]
                        failure_info = {
                            "has_failures": True,
                            "failed_steps": [r.get('tool', 'unknown') for r in failed_steps],
                            "error_messages": [r.get('output', '')[:200] for r in failed_steps],
                            "root_cause": failed_steps[-1].get('output', 'Unknown error')[:300] if failed_steps else "Unknown"
                        }
                        
                        context.append({
                            "round": round_num,
                            "plan": new_plan,
                            "results": new_results,
                            "failure_diagnosis": failure_info,
                            "suggested_changes": []
                        })
                        continue
                    
                    # All steps succeeded, do quick verification
                    yield {
                        "type": "phase",
                        "phase": "verification",
                        "content": f"Quick Verification..."
                    }
                    
                    # Simple verification without streaming
                    new_verification = None
                    for event in self._phase3_verification(new_plan, new_results, stream_thinking=False):
                        if isinstance(event, dict):
                            yield event
                        else:
                            new_verification = event
                    
                    if new_verification.success:
                        # Success!
                        yield {
                            "type": "verification_result",
                            "content": f"✓ Task goal achieved",
                            "verification": new_verification
                        }
                        
                        # Generate completion summary
                        summary_text = self._generate_completion_summary(query, new_plan, new_results)
                        
                        yield {
                            "type": "complete",
                            "content": f"Task completed in Round {round_num}",
                            "rounds": round_num,
                            "stats": self.working_memory.get_stats(),
                            "summary": summary_text
                        }
                        self._complete_task(success=True, summary=f"Completed in {round_num} rounds (upgraded from fast mode)")
                        return
                    
                    # Verification failed - treat as execution failure for next round
                    failure_info = {
                        "has_failures": False,
                        "verification_failed": True,
                        "root_cause": new_verification.diagnosis.get('root_cause', 'Task goal not achieved') if hasattr(new_verification, 'diagnosis') and new_verification.diagnosis else 'Task goal not achieved',
                        "failed_steps": new_verification.failed_steps if hasattr(new_verification, 'failed_steps') else []
                    }
                    
                    context.append({
                        "round": round_num,
                        "plan": new_plan,
                        "results": new_results,
                        "failure_diagnosis": failure_info,
                        "suggested_changes": []
                    })
                
                # Exhausted all rounds
                yield {
                    "type": "failed",
                    "content": f"Task failed after {self.max_rounds} rounds",
                    "rounds": self.max_rounds
                }
                self._complete_task(success=False, summary=f"Failed after {self.max_rounds} rounds")
            
            else:
                # ============ All steps succeeded: Do quick verification ============
                # Quick check only - if fails, treat as execution failure and replan
                yield {
                    "type": "phase",
                    "phase": "fast_verification",
                    "content": "Quick Verification..."
                }
                
                # Simple verification without streaming (we may need to replan)
                verification = None
                for event in self._phase3_verification(plan, results, stream_thinking=False):
                    if isinstance(event, dict):
                        yield event
                    else:
                        verification = event
                
                if verification.success:
                    # Success: generate completion summary
                    yield {
                        "type": "verification_result",
                        "content": f"✓ Task goal achieved",
                        "verification": verification
                    }
                    
                    summary_text = self._generate_completion_summary(query, plan, results)
                    
                    yield {
                        "type": "complete",
                        "content": f"Fast mode completed ({plan.total_steps} steps succeeded)",
                        "rounds": 1,
                        "stats": self.working_memory.get_stats(),
                        "summary": summary_text
                    }
                    self._complete_task(success=True, summary=f"Fast mode: {plan.total_steps} steps completed")
                else:
                    # Verification failed - treat as execution failure, replan directly without detailed diagnosis
                    # Extract simple failure info from verification
                    failure_info = {
                        "has_failures": False,  # Steps succeeded
                        "verification_failed": True,
                        "root_cause": verification.diagnosis.get('root_cause', 'Task goal not achieved') if hasattr(verification, 'diagnosis') and verification.diagnosis else 'Task goal not achieved',
                        "failed_steps": verification.failed_steps if hasattr(verification, 'failed_steps') else []
                    }
                    
                    yield {
                        "type": "execution_failed",
                        "content": f"🔄 Task goal not achieved, adjusting plan..."
                    }
                    
                    # Enter full PEVL loop starting from round 2
                    context = [{
                        "round": 1,
                        "plan": plan,
                        "results": results,
                        "failure_diagnosis": failure_info,
                        "suggested_changes": []
                    }]
                    
                    # Continue with PEVL rounds 2-3
                    for round_num in range(2, self.max_rounds + 1):
                        # Internal round tracking (no UI display)
                        
                        # Phase 1: Replanning (R1)
                        yield {
                            "type": "phase",
                            "phase": "planning",
                            "content": f"Phase 1: Deep Planning (DeepSeek-R1)..."
                        }
                        
                        # Stream planning thinking
                        new_plan = None
                        for event in self._phase1_planning(query, context, round_num, stream_thinking=stream_thinking):
                            if isinstance(event, dict):
                                yield event
                            else:
                                new_plan = event
                        
                        if not new_plan or new_plan.total_steps == 0:
                            yield {"type": "error", "content": "Replanning failed: No valid plan generated"}
                            break
                        
                        yield {
                            "type": "plan",
                            "content": new_plan.to_markdown(),
                            "plan": new_plan
                        }
                        
                        # Phase 2: Execution
                        yield {
                            "type": "phase",
                            "phase": "execution",
                            "content": f"Phase 2: Guided Execution (Qwen/Chat)..."
                        }
                        
                        new_results = yield from self._phase2_execution(new_plan)
                        
                        # Check if execution failed again
                        has_new_failure = any(not r.get('success', False) for r in new_results)
                        
                        if has_new_failure:
                            # Skip verification, update context for next round
                            failed_steps = [r for r in new_results if not r.get('success', False)]
                            failure_info = {
                                "has_failures": True,
                                "failed_steps": [r.get('tool', 'unknown') for r in failed_steps],
                                "error_messages": [r.get('output', '')[:200] for r in failed_steps],
                                "root_cause": failed_steps[-1].get('output', 'Unknown error')[:300] if failed_steps else "Unknown"
                            }
                            
                            context.append({
                                "round": round_num,
                                "plan": new_plan,
                                "results": new_results,
                                "failure_diagnosis": failure_info,
                                "suggested_changes": []
                            })
                            continue
                        
                        # All steps succeeded, do verification
                        yield {
                            "type": "phase",
                            "phase": "verification",
                            "content": f"Phase 3: Deep Verification (DeepSeek-R1)..."
                        }
                        
                        # Stream verification thinking
                        new_verification = None
                        for event in self._phase3_verification(new_plan, new_results, stream_thinking=stream_thinking):
                            if isinstance(event, dict):
                                yield event
                            else:
                                new_verification = event
                        
                        yield {
                            "type": "verification_result",
                            "content": f"Verification: {'Success' if new_verification.success else 'Failed'}",
                            "verification": new_verification
                        }
                        
                        if new_verification.success:
                            # Generate completion summary
                            summary_text = self._generate_completion_summary(query, new_plan, new_results)
                            
                            yield {
                                "type": "complete",
                                "content": f"Task completed in Round {round_num}",
                                "rounds": round_num,
                                "stats": self.working_memory.get_stats(),
                                "summary": summary_text
                            }
                            self._complete_task(success=True, summary=f"Completed in {round_num} rounds (from fast mode)")
                            return
                        
                        # Verification failed, update context for next round
                        context.append({
                            "round": round_num,
                            "plan": new_plan,
                            "results": new_results,
                            "failure_diagnosis": new_verification.diagnosis,
                            "suggested_changes": []
                        })
                    
                    # Exhausted all rounds
                    yield {
                        "type": "failed",
                        "content": f"Task failed after {self.max_rounds} rounds",
                        "rounds": self.max_rounds
                    }
                    self._complete_task(success=False, summary=f"Failed after {self.max_rounds} rounds")
                
        except Exception as e:
            logger.error(f"Fast plan-execute failed: {e}")
            yield {
                "type": "error",
                "content": f"Fast mode exception: {str(e)}"
            }
            self._complete_task(success=False, summary=f"Fast mode exception: {str(e)}")
    
    def _get_tool_descriptions(self, max_tools: int = 20) -> str:
        """Get tool descriptions with parameter names"""
        descriptions = []
        for tool in self.tools[:max_tools]:
            params = tool.parameters.get('properties', {})
            param_names = list(params.keys())
            descriptions.append(f"  - {tool.name}: {', '.join(param_names)}")
        return '\n'.join(descriptions)
    
    def _build_fast_planning_prompt(self, query: str) -> str:
        """Build fast planning prompt"""
        # Add historical context if available
        historical_context = ""
        if hasattr(self, 'similar_tasks_context') and self.similar_tasks_context:
            historical_context = self.similar_tasks_context + "\n\n**IMPORTANT**: Learn from past failures above! If similar tasks failed due to specific issues (e.g., port conflicts, missing dependencies), avoid those mistakes in your plan.\n\n"
        
        return f"""You are a task planning expert. Quickly generate a concise execution plan for the following task.

Task: {query}

{historical_context}Requirements:
- Break down task into 2-4 clear steps
- Select appropriate tools for each step
- Keep the plan concise and practical
- **CRITICAL**: Use EXACT parameter names from tool definitions below
- **LEARN FROM HISTORY**: If historical tasks above show failures (e.g., port 5000 occupied), avoid repeating those mistakes

Available tools and their parameters:
{self._get_tool_descriptions(max_tools=30)}

**IMPORTANT PARAMETER NAMES** (most common mistakes):
- edit_file: path, old_content, new_content (NOT file_path, NOT content)
- write_file: path, content (NOT file_path)
- read_file: path (NOT file_path)
- execute_command: command, working_directory (NOT cmd, NOT cwd)
- list_files: path (NOT directory)

**CRITICAL TOOL SELECTION RULES**:

1. **edit_file vs write_file**:
   - Use write_file: Creating NEW file, or COMPLETE rewrite
   - Use edit_file: Modifying PART of existing file
   - NEVER use edit_file with empty old_content!
   - If you want to rewrite entire file → use write_file

2. **edit_file requirements**:
   - MUST read the file first (add read_file step before edit_file)
   - old_content MUST be exact content from read_file output
   - Include enough context to make old_content unique

3. **search_replace vs edit_file**:
   - Prefer search_replace for simple changes (port numbers, variable names)
   - Use edit_file only for complex structural changes

4. **Port consistency**:
   - If you read a file and see port=X, use port X in ALL subsequent steps
   - OR add a step to change the port in the file first

Output JSON:
```json
{{
  "working_directory": "/path/to/work",
  "steps": [
    {{
      "id": 1,
      "description": "Step description",
      "tool": "tool_name",
      "params": {{"param": "value"}},
      "verify_with": "Verification method",
      "estimated_risk": "low"
    }}
  ],
  "risks": ["Risk description"]
}}
```
"""
    
    def _parse_fast_planning_response(self, response: str, query: str) -> Optional[ExecutionPlan]:
        """Parse fast planning response to ExecutionPlan"""
        try:
            logger.info(f"[PEVL Fast Planning] Response: {len(response)} chars")
            logger.debug(f"[PEVL Fast Planning] Full response:\n{response}")
            
            # Parse JSON
            import re
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                plan_data = json.loads(json_match.group(1))
            else:
                # Try direct parsing
                plan_data = json.loads(response)
            
            # Build ExecutionPlan
            steps = []
            for step_data in plan_data.get("steps", []):
                # Compatible with old/new field names
                description = step_data.get("description") or step_data.get("goal", "Execute step")
                verify_with = step_data.get("verify_with") or step_data.get("success_criteria", "")
                
                step = PlanStep(
                    id=step_data["id"],
                    description=description,
                    tool=step_data["tool"],
                    params=step_data.get("params", {}),
                    working_directory=plan_data.get("working_directory", "."),
                    verify_with=verify_with,
                    estimated_risk=step_data.get("estimated_risk", "low")
                )
                steps.append(step)
            
            plan = ExecutionPlan(
                query=query,
                working_directory=plan_data.get("working_directory", "."),
                steps=steps,
                total_steps=len(steps),
                risks=plan_data.get("risks", [])
            )
            
            logger.info(f"[PEVL Fast] Plan generated: {plan.total_steps} steps")
            self.episodic_memory.add_finding(
                f"Fast plan: {plan.total_steps} steps",
                category="plan"
            )
            
            return plan
            
        except json.JSONDecodeError as e:
            logger.error(f"[PEVL Fast Planning] Failed to parse JSON: {e}")
            logger.error(f"[PEVL Fast Planning] Response was: {response[:1000]}")
            return None
        except Exception as e:
            logger.error(f"[PEVL Fast Planning] Exception: {e}", exc_info=True)
            return None
    
    def _fast_planning(self, query: str) -> Optional[ExecutionPlan]:
        """
        Fast planning mode (Chat model, non-streaming)
        
        Args:
            query: User query
            
        Returns:
            ExecutionPlan object
        """
        try:
            # Build prompt and generate response
            prompt = self._build_fast_planning_prompt(query)
            response = self.executor_agent.generate(prompt)
            
            # Parse response to plan
            return self._parse_fast_planning_response(response, query)
            
        except Exception as e:
            logger.error(f"[PEVL Fast Planning] Exception: {e}", exc_info=True)
            return None
    
    def _generate_completion_summary(
        self, 
        query: str, 
        plan: ExecutionPlan, 
        results: List[Dict[str, Any]]
    ) -> str:
        """
        Generate task completion summary (similar to Cursor/Claude style)
        
        Args:
            query: Original user query
            plan: Execution plan
            results: List of execution results
            
        Returns:
            Summary text
        """
        try:
            # Build execution summary
            successful_steps = sum(1 for r in results if r.get('success', False))
            failed_steps = len(results) - successful_steps
            
            # Collect key operations
            actions_summary = []
            for i, (step, result) in enumerate(zip(plan.steps, results), 1):
                if result.get('success'):
                    actions_summary.append(f"✓ {step.description}")
            
            actions_text = "\n".join(actions_summary[:5])  # Display up to 5
            
            # Build prompt
            prompt = f"""Based on the following task execution information, generate a concise and professional completion summary (2-3 sentences):

**User Task**: {query}

**Execution Status**:
- Total steps: {len(results)}
- Successful: {successful_steps}
- Failed: {failed_steps}

**Main Operations**:
{actions_text}

Please summarize the task completion status in a concise, professional, and friendly tone. Focus on:
1. What was completed
2. Main work done
3. Final result

Requirements:
- 2-3 sentences
- Use English
- No Markdown formatting
- Natural and professional tone"""

            # Use executor (chat) model to generate summary
            summary = self.executor_agent.generate(prompt).strip()
            
            # If generation fails or too short, use default summary
            if not summary or len(summary) < 20:
                summary = f"Task completed successfully: {query}. Executed {successful_steps} steps, all operations completed."
            
            return summary
            
        except Exception as e:
            logger.warning(f"[PEVL] Failed to generate completion summary: {e}")
            # Fallback to simple summary
            return f"Task completed. Successfully executed {len(results)} steps."
    
    def _complete_task(self, success: bool, summary: str):
        """
        Complete task and update memory
        
        Args:
            success: Whether succeeded
            summary: Task summary
        """
        if not self.episodic_memory or not self.current_task_id:
            return
        
        self.episodic_memory.update_next_action(
            f"Completed: {summary}" if success else f"Failed: {summary}"
        )
        
        # Extract failure reason for failed tasks (max 100 chars)
        failure_reason = None
        if not success:
            # Extract concise failure reason from summary
            failure_reason = summary[:100].strip()
        
        self.memory_manager.complete_task(
            self.current_task_id,
            success=success,
            failure_reason=failure_reason
        )
        
        # Index task (both success and failure)
        try:
            if self.episodic_memory.task_file and self.episodic_memory.task_file.exists():
                task_content = self.episodic_memory.task_file.read_text(encoding='utf-8')[:500]
                metadata = {
                    'status': 'completed' if success else 'failed',
                    'mode': 'pevl'
                }
                if failure_reason:
                    metadata['failure_reason'] = failure_reason
                
                self.vector_search.index_task(
                    self.current_task_id,
                    task_content,
                    metadata=metadata
                )
                logger.info(f"[PEVL] Task indexed: {self.current_task_id}")
        except Exception as e:
            logger.warning(f"Failed to index task: {e}")
        
        stats = self.working_memory.get_stats()
        logger.info(f"[PEVL] Task completed. Stats: {stats}")
    
    def _build_analysis_prompt(self, query: str) -> str:
        """
        Build task analysis prompt
        
        Args:
            query: User query
            
        Returns:
            Prompt text
        """
        # Reuse prompt from _phase0_analysis (avoid code duplication)
        return f"""Analyze this task and select the optimal execution mode.

Task: {query}

## Complexity Assessment Guidelines

**Simple** (direct/fast mode):
- Single file operation (read, write, edit ONE file)
- Single command execution
- Simple git operation (status, diff, commit)
- NO multi-step dependencies

**Medium** (fast/hybrid mode):
- Multiple files (2-5 files)
- Multiple steps with dependencies
- Service deployment with configuration
- Code analysis with categorization
- Data processing and report generation

**Complex** (hybrid mode):
- Many files (5+ files)
- Complex dependencies
- Multi-stage workflows
- Requires exploration or research

## Uncertainty Assessment

**Low**: Clear requirements, known tools, deterministic
**Medium**: Some ambiguity, may need adjustments
**High**: Unclear requirements, exploration needed

## Mode Selection

- **direct**: ONLY for trivial single-step tasks (read one file, run one command)
- **fast**: Simple tasks with 2-4 steps, clear dependencies
- **hybrid**: Medium/complex tasks, or when verification is critical
- **explore**: Research, investigation, unclear requirements

## CRITICAL Rules

1. If task mentions "create multiple files" → complexity = medium (NOT simple)
2. If task mentions "analyze and report" → complexity = medium (NOT simple)
3. If task mentions "test and verify" → use fast/hybrid (NOT direct)
4. Direct mode should be RARE (< 10% of tasks)

Return JSON:
{{
  "complexity": "simple|medium|complex",
  "uncertainty": "low|medium|high",
  "recommended_mode": "direct|fast|hybrid|explore",
  "reasoning": "...",
  "model_config": {{"planner": "...", "executor": "...", "verifier": "..."}}
}}
"""
    
    def _parse_task_analysis(self, response: str, query: str) -> TaskAnalysis:
        """
        Parse task analysis response
        
        Args:
            response: LLM response
            query: Original query
            
        Returns:
            TaskAnalysis object
        """
        import re
        
        json_match = re.search(r'```json\s*\n(.*?)\n```', response, re.DOTALL)
        if not json_match:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
        
        if json_match:
            try:
                data = json.loads(json_match.group(1) if json_match.lastindex else json_match.group(0))
                
                return TaskAnalysis(
                    complexity=data.get('complexity', 'medium'),
                    uncertainty=data.get('uncertainty', 'medium'),
                    task_type=data.get('task_type', 'other'),
                    estimated_steps=data.get('estimated_steps', 4),
                    recommended_mode=data.get('recommended_mode', 'hybrid'),
                    reasoning=data.get('reasoning', ''),
                    model_config=data.get('model_config', {
                        'planner': 'deepseek-r1',
                        'executor': 'deepseek-chat',
                        'verifier': 'deepseek-r1'
                    })
                )
            except Exception as e:
                logger.error(f"Analysis JSON parsing failed: {e}")
        
        return self._get_default_task_analysis(query)
    
    def _get_default_task_analysis(self, query: str) -> TaskAnalysis:
        """Get default analysis result (fallback)"""
        query_lower = query.lower()
        
        if any(w in query_lower for w in ['flask', 'django', 'docker', 'deploy']):
            complexity, steps = 'medium', 4
        elif any(w in query_lower for w in ['create', 'write', 'read']):
            complexity, steps = 'simple', 2
        else:
            complexity, steps = 'medium', 3
        
        uncertainty = 'high' if any(w in query_lower for w in ['port', 'service', 'server']) else 'low'
        mode = 'fast' if complexity == 'simple' and uncertainty == 'low' else 'hybrid'
        
        return TaskAnalysis(
            complexity=complexity,
            uncertainty=uncertainty,
            task_type='other',
            estimated_steps=steps,
            recommended_mode=mode,
            reasoning='Fallback heuristic analysis',
            model_config={
                'planner': 'deepseek-r1',
                'executor': 'deepseek-chat',
                'verifier': 'deepseek-r1'
            }
        )
