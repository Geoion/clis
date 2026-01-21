"""
两阶段 Agent - Plan-Execute 模式

灵感来自 Claude Code 和 Cursor Agent:
- Phase 1: Planning（只读探索，生成计划）
- Phase 2: Execution（按计划执行，严格控制）
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
    两阶段执行 Agent
    
    Phase 1: Planning
    - 只使用只读工具（~15个）
    - 生成结构化计划
    - 明确工作目录和依赖关系
    
    Phase 2: Execution  
    - 使用所有工具（~40个）
    - 严格按计划执行
    - 每步验证结果
    """
    
    def __init__(
        self,
        config_manager: Optional[ConfigManager] = None,
        tools: Optional[List[Tool]] = None
    ):
        """
        初始化两阶段 Agent
        
        Args:
            config_manager: 配置管理器
            tools: 工具列表
        """
        self.config_manager = config_manager or ConfigManager()
        self.tools = tools or []
        self.llm_agent = Agent(self.config_manager)
        
        # 规划器
        self.planner = TaskPlanner(self.llm_agent, self.tools)
        
        # ============ Memory System (与 InteractiveAgent 对齐) ============
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
        
        # 工作目录管理器
        self.working_dir_manager = WorkingDirectoryManager()
        
        # 执行 Agent（用于简单任务的回退）
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
        执行任务（两阶段模式）
        
        Args:
            query: 用户查询
            auto_approve_plan: 自动批准计划（不需要用户审查）
            skip_planning: 跳过规划阶段（直接执行）
            
        Yields:
            执行步骤和结果
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
        
        # 评估复杂度
        complexity = self.planner.assess_complexity(query)
        
        self.episodic_memory.add_finding(f"Task complexity: {complexity}", category="assessment")
        
        yield {
            "type": "complexity_assessment",
            "complexity": complexity,
            "content": f"任务复杂度: {complexity}"
        }
        
        # 简单任务：跳过规划，直接执行
        if complexity == "simple" or skip_planning:
            yield {
                "type": "info",
                "content": "任务简单，直接执行（跳过规划阶段）"
            }
            
            self.episodic_memory.update_step("Fallback to ReAct mode (simple task)", "in_progress")
            
            # 使用标准 InteractiveAgent
            for step in self.executor.execute(query):
                yield step
            return
        
        # ============ Phase 1: Planning ============
        yield {
            "type": "phase",
            "phase": "planning",
            "content": "📋 阶段 1: 制定执行计划（只读探索）..."
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
            
            # 显示计划
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
                "content": f"计划生成失败: {e}"
            }
            import traceback
            traceback.print_exc()
            
            # Complete task as failed
            self._complete_task(success=False, summary=f"Planning failed: {e}")
            return
        
        # 等待用户批准（除非自动批准）
        if not auto_approve_plan:
            yield {
                "type": "plan_approval_needed",
                "content": "请审查计划。批准后将执行。"
            }
            # 这里需要 CLI 处理用户输入
            # 暂时假设批准
        
        # ============ Phase 2: Execution ============
        yield {
            "type": "phase",
            "phase": "execution",
            "content": f"⚡ 阶段 2: 执行计划（{plan.total_steps} 个步骤）..."
        }
        
        self.episodic_memory.update_step("Phase 2: Execution", "in_progress")
        
        # 设置工作目录
        if plan.working_directory:
            self.working_dir_manager.change_directory(plan.working_directory)
            self.working_memory.add_known_fact(f"Working directory: {plan.working_directory}")
            self.episodic_memory.add_finding(
                f"Set working directory: {plan.working_directory}",
                category="directory"
            )
            yield {
                "type": "directory_change",
                "content": f"切换到工作目录: {plan.working_directory}"
            }
        
        # 执行每个步骤
        for step in plan.steps:
            # 检查依赖
            if step.depends_on:
                # TODO: 检查依赖步骤是否完成
                pass
            
            # 切换到步骤特定的目录（如果有）
            if step.working_directory:
                self.working_dir_manager.change_directory(step.working_directory)
            
            # 执行步骤
            yield {
                "type": "step_start",
                "step_id": step.id,
                "content": f"执行步骤 {step.id}/{plan.total_steps}: {step.description}"
            }
            
            self.episodic_memory.update_step(f"Step {step.id}: {step.description}", "in_progress")
            
            # ============ 直接执行工具（不用 InteractiveAgent）============
            # 这样可以避免 Agent 自由探索和重复操作
            try:
                from clis.tools.base import ToolExecutor
                
                # 创建临时 ToolExecutor
                tool_executor = ToolExecutor(self.tools)
                
                # 切换到步骤的工作目录（如果指定）
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
                            "content": f"无法切换到目录 {step.working_directory}: {e}"
                        }
                        continue
                
                # ============ Update Working Memory (Before Execution) ============
                self.working_memory.increment_tool(step.tool)
                
                # 直接执行工具
                result = tool_executor.execute(step.tool, step.params)
                
                # 恢复目录
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
                
                # 返回结果
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
                    "content": f"步骤 {step.id} 执行失败: {e}"
                }
                step_result = None
            
            # 验证结果（如果有验证步骤）
            if step.verify_with and step_result and step_result.success:
                yield {
                    "type": "verification_start",
                    "content": f"🔍 验证: {step.verify_with}"
                }
                
                # 执行验证逻辑
                verification_passed = self._verify_step_result(step, step_result)
                
                if verification_passed:
                    yield {
                        "type": "verification_result",
                        "content": "✓ 验证通过",
                        "success": True
                    }
                else:
                    yield {
                        "type": "verification_result",
                        "content": f"✗ 验证失败: 输出不符合预期\n期望: {step.verify_with}\n实际: {step_result.output[:200]}...",
                        "success": False
                    }
        
        # ============ Complete Task ============
        self.episodic_memory.update_step("All steps completed", "done")
        summary = f"Plan-Execute completed: {plan.total_steps} steps executed"
        self._complete_task(success=True, summary=summary)
        
        # 完成
        yield {
            "type": "complete",
            "content": f"所有 {plan.total_steps} 个步骤已完成",
            "task_file": str(self.episodic_memory.get_file_path()),
            "stats": self.working_memory.get_stats()
        }
    
    def _verify_step_result(self, step: PlanStep, result) -> bool:
        """
        验证步骤执行结果
        
        Args:
            step: 计划步骤
            result: 执行结果
            
        Returns:
            验证是否通过
        """
        if not step.verify_with or not result or not result.output:
            return False
        
        verify_text = step.verify_with.lower()
        output_text = result.output.lower()
        
        # 简单的文本匹配验证
        # 支持多种验证模式:
        # 1. "Check if ... returns 'xxx'" - 检查输出包含特定文本
        # 2. "Verify ... contains xxx" - 检查输出包含特定文本
        # 3. "Ensure ... exits with code 0" - 检查退出码
        
        # 提取期望的内容
        import re
        
        # 模式 1: "returns 'xxx'" 或 "returns xxx"
        match = re.search(r"returns?\s+['\"]([^'\"]+)['\"]", verify_text)
        if match:
            expected = match.group(1).lower()
            return expected in output_text
        
        # 模式 2: "contains xxx"
        match = re.search(r"contains?\s+['\"]?([^'\"]+)['\"]?", verify_text)
        if match:
            expected = match.group(1).lower()
            return expected in output_text
        
        # 模式 3: "exits with code 0" 或成功标志
        if "exit" in verify_text and "0" in verify_text:
            return result.success
        
        if "success" in verify_text:
            return result.success
        
        # 默认: 检查执行是否成功
        return result.success
    
    def _format_similar_tasks(self, similar_tasks) -> str:
        """
        格式化相似任务为文本
        
        Args:
            similar_tasks: 相似任务列表 (List[Tuple[task_id, similarity, description]])
            
        Returns:
            格式化的文本
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
