"""
Two-Phase Agent - Plan-Execute mode

Inspired by Claude Code and Cursor Agent:
- Phase 1: Planning (read-only exploration, generate plan)
- Phase 2: Execution (execute according to plan, strict control)
"""

from typing import Dict, Any, List, Optional, Generator
from pathlib import Path
from datetime import datetime

from clis.agent.agent import Agent
from clis.agent.planner import TaskPlanner, ExecutionPlan, PlanStep
from clis.agent.working_directory import WorkingDirectoryManager
from clis.agent.interactive_agent import InteractiveAgent
from clis.agent.working_memory import WorkingMemory
from clis.agent.episodic_memory import EpisodicMemory
from clis.agent.memory_manager import MemoryManager
from clis.agent.vector_search import VectorSearch
from clis.config import ConfigManager
from clis.tools.base import Tool
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class TwoPhaseAgent:
    """
    Two-phase execution Agent
    
    Phase 1: Planning
    - Use only read-only tools (~15)
    - Generate structured plan
    - Clarify working directory and dependencies
    
    Phase 2: Execution  
    - Use all tools (~40)
    - Execute strictly according to plan
    - Verify results at each step
    """
    
    def __init__(
        self,
        config_manager: Optional[ConfigManager] = None,
        tools: Optional[List[Tool]] = None
    ):
        """
        Initialize two-phase Agent
        
        Args:
            config_manager: Configuration manager
            tools: Tool list
        """
        self.config_manager = config_manager or ConfigManager()
        self.tools = tools or []
        self.llm_agent = Agent(self.config_manager)
        
        # Planner
        self.planner = TaskPlanner(self.llm_agent, self.tools)
        
        # ============ Memory System (aligned with InteractiveAgent) ============
        # Working memory (in-memory)
        self.working_memory = WorkingMemory()
        
        # Episodic memory (task documents) - created when task starts
        self.episodic_memory: Optional[EpisodicMemory] = None
        
        # Memory manager
        self.memory_manager = MemoryManager()
        
        # Vector search (semantic search for historical tasks)
        self.vector_search = VectorSearch()
        
        # Current task ID
        self.current_task_id: Optional[str] = None
        
        # Working directory manager
        self.working_dir_manager = WorkingDirectoryManager()
        
        # Execution Agent (for fallback on simple tasks)
        self.executor = InteractiveAgent(
            config_manager=self.config_manager,
            tools=self.tools
        )
    
    def execute(
        self,
        query: str,
        auto_approve_plan: bool = False,
        skip_planning: bool = False
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Execute task (two-phase mode)
        
        Args:
            query: User query
            auto_approve_plan: Auto-approve plan (no user review needed)
            skip_planning: Skip planning phase (execute directly)
            
        Yields:
            Execution steps and results
        """
        # ============ Initialize Memory System ============
        # Create task memory
        self.current_task_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        task_id, task_file = self.memory_manager.create_task_memory(query, self.current_task_id)
        self.episodic_memory = EpisodicMemory(task_id)
        self.episodic_memory.load_or_create(query)
        
        # Clear working memory
        self.working_memory.clear()
        
        logger.info(f"[Plan-Execute] Task memory created: {task_file}")
        
        # ============ Search for Similar Historical Tasks ============
        similar_tasks_text = ""
        try:
            similar_tasks = self.vector_search.search_similar_tasks(query, top_k=3)
            if similar_tasks:
                logger.info(f"Found {len(similar_tasks)} similar historical tasks")
                self.episodic_memory.add_finding(
                    f"Found {len(similar_tasks)} similar historical tasks",
                    category="reference"
                )
                similar_tasks_text = self._format_similar_tasks(similar_tasks)
        except Exception as e:
            logger.warning(f"Failed to search similar tasks: {e}")
        
        # Record in episodic memory
        self.episodic_memory.update_step("Plan-Execute mode started", "in_progress")
        
        # Assess complexity
        complexity = self.planner.assess_complexity(query)
        
        self.episodic_memory.add_finding(f"Task complexity: {complexity}", category="assessment")
        
        yield {
            "type": "complexity_assessment",
            "complexity": complexity,
            "content": f"Task complexity: {complexity}"
        }
        
        # Simple tasks: skip planning, execute directly
        if complexity == "simple" or skip_planning:
            yield {
                "type": "info",
                "content": "Task is simple, executing directly (skipping planning phase)"
            }
            
            self.episodic_memory.update_step("Fallback to ReAct mode (simple task)", "in_progress")
            
            # Use standard InteractiveAgent
            for step in self.executor.execute(query):
                yield step
            return
        
        # ============ Phase 1: Planning ============
        yield {
            "type": "phase",
            "phase": "planning",
            "content": "📋 Phase 1: Creating execution plan (read-only exploration)..."
        }
        
        self.episodic_memory.update_step("Phase 1: Planning", "in_progress")
        
        try:
            plan = self.planner.generate_plan(query, similar_tasks_text=similar_tasks_text)
            
            # Record plan in episodic memory
            self.episodic_memory.add_finding(
                f"Generated plan with {plan.total_steps} steps",
                category="plan"
            )
            for step in plan.steps:
                self.episodic_memory.add_finding(
                    f"Step {step.id}: {step.description} (tool: {step.tool})",
                    category="plan"
                )
            
            # Display plan
            plan_md = plan.to_markdown()
            yield {
                "type": "plan",
                "content": plan_md,
                "plan": plan
            }
            
            self.episodic_memory.update_step("Phase 1: Planning completed", "done")
            
        except Exception as e:
            self.episodic_memory.update_step(f"Planning failed: {e}", "error")
            yield {
                "type": "error",
                "content": f"Plan generation failed: {e}"
            }
            import traceback
            traceback.print_exc()
            
            # Complete task as failed
            self._complete_task(success=False, summary=f"Planning failed: {e}")
            return
        
        # Wait for user approval (unless auto-approved)
        if not auto_approve_plan:
            yield {
                "type": "plan_approval_needed",
                "content": "Please review the plan. Execution will proceed after approval."
            }
            # CLI needs to handle user input here
            # Assume approval for now
        
        # ============ Phase 2: Execution ============
        yield {
            "type": "phase",
            "phase": "execution",
            "content": f"⚡ Phase 2: Executing plan ({plan.total_steps} steps)..."
        }
        
        self.episodic_memory.update_step("Phase 2: Execution", "in_progress")
        
        # Set working directory
        if plan.working_directory:
            self.working_dir_manager.change_directory(plan.working_directory)
            self.working_memory.add_known_fact(f"Working directory: {plan.working_directory}")
            self.episodic_memory.add_finding(
                f"Set working directory: {plan.working_directory}",
                category="directory"
            )
            yield {
                "type": "directory_change",
                "content": f"Switching to working directory: {plan.working_directory}"
            }
        
        # Execute each step
        for step in plan.steps:
            # Check dependencies
            if step.depends_on:
                # TODO: Check if dependent steps are completed
                pass
            
            # Switch to step-specific directory (if any)
            if step.working_directory:
                self.working_dir_manager.change_directory(step.working_directory)
            
            # Execute step
            yield {
                "type": "step_start",
                "step_id": step.id,
                "content": f"Executing step {step.id}/{plan.total_steps}: {step.description}"
            }
            
            self.episodic_memory.update_step(f"Step {step.id}: {step.description}", "in_progress")
            
            # ============ Execute tool directly (not using InteractiveAgent) ============
            # This avoids Agent free exploration and duplicate operations
            try:
                from clis.tools.base import ToolExecutor
                
                # Create temporary ToolExecutor
                tool_executor = ToolExecutor(self.tools)
                
                # Switch to step's working directory (if specified)
                import os
                old_dir = None
                if step.working_directory and step.working_directory != str(self.working_dir_manager.current_dir):
                    old_dir = os.getcwd()
                    try:
                        os.chdir(step.working_directory)
                    except Exception as e:
                        self.episodic_memory.update_step(f"Failed to change directory: {e}", "error")
                        yield {
                            "type": "error",
                            "content": f"Failed to switch to directory {step.working_directory}: {e}"
                        }
                        continue
                
                # ============ Update Working Memory (Before Execution) ============
                self.working_memory.increment_tool(step.tool)
                
                # Execute tool directly
                result = tool_executor.execute(step.tool, step.params)
                
                # Restore directory
                if old_dir:
                    os.chdir(old_dir)
                
                # ============ Update Memory System (After Execution) ============
                # Record in working memory based on tool type
                if step.tool == 'read_file':
                    file_path = step.params.get('path', '')
                    is_new = self.working_memory.add_file_read(file_path)
                    if not is_new:
                        logger.warning(f"[Plan-Execute] Duplicate file read: {file_path}")
                
                elif step.tool in ('write_file', 'edit_file', 'search_replace'):
                    file_path = step.params.get('path', '')
                    self.working_memory.add_file_written(file_path)
                    self.working_memory.add_known_fact(f"File {file_path} modified")
                    self.episodic_memory.update_step(f"Modified file: {file_path}", "done")
                
                elif step.tool == 'execute_command':
                    command = step.params.get('command', '')
                    self.working_memory.add_command(command, result.success, result.output)
                    self.episodic_memory.add_finding(
                        f"Executed: {command[:100]}...",
                        category="command"
                    )
                
                elif step.tool == 'file_tree':
                    path = step.params.get('path', '')
                    self.working_memory.add_known_fact(f"Listed directory: {path}")
                
                # Record findings in episodic memory
                if result.success:
                    preview = result.output[:150] if result.output else "Success"
                    self.episodic_memory.add_finding(
                        f"Step {step.id}: {preview}",
                        category="result"
                    )
                else:
                    self.episodic_memory.add_finding(
                        f"Step {step.id} failed: {result.error[:150]}",
                        category="error"
                    )
                
                # Return result
                yield {
                    "type": "tool_call",
                    "tool": step.tool,
                    "params": step.params
                }
                
                yield {
                    "type": "tool_result",
                    "content": result.output if result.success else result.error,
                    "success": result.success
                }
                
                step_result = result
                self.episodic_memory.update_step(f"Step {step.id}: {step.description}", "done")
                
            except Exception as e:
                self.episodic_memory.update_step(f"Step {step.id} failed: {e}", "error")
                self.episodic_memory.add_finding(f"Exception: {e}", category="error")
                yield {
                    "type": "error",
                    "content": f"Step {step.id} execution failed: {e}"
                }
                step_result = None
            
            # Verify result (if verification step exists)
            if step.verify_with and step_result and step_result.success:
                yield {
                    "type": "verification_start",
                    "content": f"🔍 Verification: {step.verify_with}"
                }
                
                # Execute verification logic
                verification_passed = self._verify_step_result(step, step_result)
                
                if verification_passed:
                    yield {
                        "type": "verification_result",
                        "content": "✓ Verification passed",
                        "success": True
                    }
                else:
                    yield {
                        "type": "verification_result",
                        "content": f"✗ Verification failed: output does not match expectation\nExpected: {step.verify_with}\nActual: {step_result.output[:200]}...",
                        "success": False
                    }
        
        # ============ Complete Task ============
        self.episodic_memory.update_step("All steps completed", "done")
        summary = f"Plan-Execute completed: {plan.total_steps} steps executed"
        self._complete_task(success=True, summary=summary)
        
        # Complete
        yield {
            "type": "complete",
            "content": f"All {plan.total_steps} steps completed",
            "task_file": str(self.episodic_memory.get_file_path()),
            "stats": self.working_memory.get_stats()
        }
    
    def _verify_step_result(self, step: PlanStep, result) -> bool:
        """
        Verify step execution result
        
        Args:
            step: Plan step
            result: Execution result
            
        Returns:
            Whether verification passed
        """
        if not step.verify_with or not result or not result.output:
            return False
        
        verify_text = step.verify_with.lower()
        output_text = result.output.lower()
        
        # Simple text matching verification
        # Supports multiple verification patterns:
        # 1. "Check if ... returns 'xxx'" - Check if output contains specific text
        # 2. "Verify ... contains xxx" - Check if output contains specific text
        # 3. "Ensure ... exits with code 0" - Check exit code
        
        # Extract expected content
        import re
        
        # Pattern 1: "returns 'xxx'" or "returns xxx"
        match = re.search(r"returns?\s+['\"]([^'\"]+)['\"]", verify_text)
        if match:
            expected = match.group(1).lower()
            return expected in output_text
        
        # Pattern 2: "contains xxx"
        match = re.search(r"contains?\s+['\"]?([^'\"]+)['\"]?", verify_text)
        if match:
            expected = match.group(1).lower()
            return expected in output_text
        
        # Pattern 3: "exits with code 0" or success indicator
        if "exit" in verify_text and "0" in verify_text:
            return result.success
        
        if "success" in verify_text:
            return result.success
        
        # Default: Check if execution succeeded
        return result.success
    
    def _format_similar_tasks(self, similar_tasks) -> str:
        """
        Format similar tasks as text
        
        Args:
            similar_tasks: List of similar tasks (List[Tuple[task_id, similarity, description]])
            
        Returns:
            Formatted text
        """
        if not similar_tasks:
            return ""
        
        text = "\n📚 **Historical Similar Tasks** (for reference):\n\n"
        for i, task in enumerate(similar_tasks, 1):
            # Handle both tuple and dict formats
            if isinstance(task, tuple):
                task_id, similarity, query = task
                status = "unknown"
            else:
                task_id = task.get('task_id', 'unknown')
                similarity = task.get('similarity', 0.0)
                query = task.get('query', '')
                status = task.get('status', 'unknown')
            
            query = query[:100] if query else ""
            
            text += f"{i}. Task {task_id} (similarity: {similarity:.2f}, status: {status})\n"
            text += f"   Query: {query}...\n\n"
            
            # Try to load task memory
            try:
                task_memory = EpisodicMemory(task_id)
                if task_memory.exists():
                    task_content = task_memory.task_file.read_text(encoding='utf-8')
                    # Extract key findings
                    if "## 🔍 Key Findings" in task_content:
                        findings_section = task_content.split("## 🔍 Key Findings")[1]
                        findings_section = findings_section.split("##")[0]  # Stop at next section
                        findings_lines = [line.strip() for line in findings_section.split('\n') 
                                        if line.strip() and line.strip().startswith('-')][:3]
                        if findings_lines:
                            text += "   Key findings:\n"
                            for finding in findings_lines:
                                text += f"   {finding}\n"
            except Exception as e:
                logger.debug(f"Could not load task memory for {task_id}: {e}")
        
        return text
    
    def _complete_task(self, success: bool, summary: str):
        """
        Complete the task and update memory system
        
        Args:
            success: Whether task completed successfully
            summary: Task summary
        """
        if not self.episodic_memory or not self.current_task_id:
            return
        
        # Update episodic memory
        self.episodic_memory.update_next_action(f"✅ Completed: {summary}" if success else f"❌ Failed: {summary}")
        
        # Complete task in memory manager
        self.memory_manager.complete_task(
            self.current_task_id,
            success=success
        )
        
        # Index task for future reference
        if success:
            try:
                if self.episodic_memory.task_file and self.episodic_memory.task_file.exists():
                    task_content = self.episodic_memory.task_file.read_text(encoding='utf-8')[:500]
                    self.vector_search.index_task(
                        self.current_task_id,
                        task_content,
                        metadata={
                            'status': 'completed',
                            'mode': 'plan-execute'
                        }
                    )
                    logger.info(f"[Plan-Execute] Task indexed: {self.current_task_id}")
            except Exception as e:
                logger.warning(f"Failed to index task: {e}")
        
        # Log stats
        stats = self.working_memory.get_stats()
        logger.info(f"[Plan-Execute] Task completed. Stats: {stats}")
