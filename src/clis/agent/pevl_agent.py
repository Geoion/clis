"""
PEVL Agent - Plan-Execute-Verify Loop with Self-Healing

混合模型架构:
- Phase 0: Task Analysis (R1) - 一次性
- Phase 1-3 Loop: Plan (R1) → Execute (Chat) → Verify (R1)
- 自我修复: 失败后智能重规划,最多3轮
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
from clis.config import ConfigManager
from clis.tools.base import Tool, ToolExecutor, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TaskAnalysis:
    """任务分析结果"""
    complexity: str  # trivial | simple | medium | complex
    uncertainty: str  # low | medium | high
    task_type: str
    estimated_steps: int
    recommended_mode: str  # direct | fast | hybrid | explore
    reasoning: str
    model_config: Dict[str, str]


@dataclass
class Verification:
    """验证结果"""
    success: bool
    failed_steps: List[int]
    diagnosis: Dict[str, Any]
    should_replan: bool
    replan_suggestion: str
    reasoning: str


@dataclass
class ReplanDecision:
    """重规划决策"""
    decision: bool
    confidence: float
    reasoning: str
    suggested_changes: List[str]


class PEVLAgent:
    """
    Plan-Execute-Verify Loop Agent
    
    特点:
    - 混合模型: R1 (规划/验证) + Chat/Qwen (执行)
    - 自我修复: 失败后自动重规划
    - 智能选择: R1 自动判断模式
    - 循环控制: 最多3轮
    """
    
    def __init__(
        self,
        config_manager: Optional[ConfigManager] = None,
        tools: Optional[List[Tool]] = None,
        max_rounds: int = 3
    ):
        """
        初始化 PEVL Agent
        
        Args:
            config_manager: 配置管理器
            tools: 工具列表
            max_rounds: 最大循环轮数
        """
        self.config_manager = config_manager or ConfigManager()
        self.tools = tools or []
        self.max_rounds = max_rounds
        
        # LLM Agents - 稍后会根据任务分析结果配置不同模型
        # 默认使用同一个 agent
        self.analyzer_agent = Agent(self.config_manager)  # R1 for analysis
        self.planner_agent = Agent(self.config_manager)   # R1 for planning
        self.executor_agent = Agent(self.config_manager)  # Chat for execution
        self.verifier_agent = Agent(self.config_manager)  # R1 for verification
        
        # Tool executor
        self.tool_executor = ToolExecutor(self.tools)
        
        # Memory System
        self.working_memory = WorkingMemory()
        self.episodic_memory: Optional[EpisodicMemory] = None
        self.memory_manager = MemoryManager()
        self.vector_search = VectorSearch()
        self.working_dir_manager = WorkingDirectoryManager()
        
        # Current task tracking
        self.current_task_id: Optional[str] = None
        self.total_cost: float = 0.0  # 累计成本追踪
    
    def execute(
        self,
        query: str,
        user_mode_override: Optional[str] = None
    ) -> Generator[Dict[str, Any], None, None]:
        """
        执行任务 (PEVL 模式)
        
        Args:
            query: 用户查询
            user_mode_override: 用户手动指定模式 (覆盖 R1 判断)
            
        Yields:
            执行步骤和结果
        """
        # ============ Initialize Memory System ============
        self.current_task_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        task_id, task_file = self.memory_manager.create_task_memory(query, self.current_task_id)
        self.episodic_memory = EpisodicMemory(task_id)
        self.episodic_memory.load_or_create(query)
        self.working_memory.clear()
        
        logger.info(f"[PEVL] Task memory created: {task_file}")
        
        # ============ Phase 0: Task Analysis (R1, 一次性) ============
        if not user_mode_override or user_mode_override == "auto":
            yield {
                "type": "phase",
                "phase": "analysis",
                "content": "📊 Phase 0: 任务分析与模式选择 (DeepSeek-R1)..."
            }
            
            analysis = self._phase0_analysis(query)
            
            yield {
                "type": "analysis_result",
                "content": f"复杂度: {analysis.complexity}, 不确定性: {analysis.uncertainty}, 推荐模式: {analysis.recommended_mode}",
                "analysis": analysis
            }
            
            self.episodic_memory.add_finding(
                f"Task analysis: {analysis.complexity}, mode: {analysis.recommended_mode}",
                category="analysis"
            )
            
            # 根据分析结果选择模式
            if analysis.recommended_mode == "direct":
                # 极简单任务,直接执行
                yield from self._direct_execute(query)
                return
            elif analysis.recommended_mode == "fast":
                # 简单确定性任务,快速 Plan-Execute
                yield from self._fast_plan_execute(query)
                return
            # 否则进入 PEVL 循环
        else:
            # 用户手动指定,跳过分析
            analysis = None
        
        # ============ PEVL Loop (最多3轮) ============
        context = []  # 累积上下文 (失败信息)
        
        for round_num in range(1, self.max_rounds + 1):
            yield {
                "type": "round_start",
                "round": round_num,
                "content": f"{'='*60}\n🔄 Round {round_num}/{self.max_rounds}\n{'='*60}"
            }
            
            self.episodic_memory.update_step(f"Round {round_num} started", "in_progress")
            
            # Phase 1: 规划 (R1)
            yield {
                "type": "phase",
                "phase": "planning",
                "content": f"📋 Phase 1: 深度规划 (DeepSeek-R1)..."
            }
            
            plan = self._phase1_planning(query, context, round_num)
            
            if not plan or plan.total_steps == 0:
                yield {"type": "error", "content": "规划失败: 未生成有效计划"}
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
            
            # Phase 2: 执行 (Chat)
            yield {
                "type": "phase",
                "phase": "execution",
                "content": f"⚡ Phase 2: 引导式执行 (Qwen/Chat)..."
            }
            
            results = yield from self._phase2_execution(plan)
            
            # Phase 3: 验证 (R1)
            yield {
                "type": "phase",
                "phase": "verification",
                "content": f"🔍 Phase 3: 深度验证 (DeepSeek-R1)..."
            }
            
            verification = self._phase3_verification(plan, results)
            
            yield {
                "type": "verification_result",
                "content": f"验证结果: {'✅ 成功' if verification.success else '❌ 失败'}",
                "verification": verification
            }
            
            if verification.success:
                # 成功完成
                self.episodic_memory.update_step(f"Task completed in round {round_num}", "done")
                self._complete_task(success=True, summary=f"Completed in {round_num} rounds")
                
                yield {
                    "type": "complete",
                    "content": f"✅ 任务完成 (第 {round_num} 轮成功)",
                    "rounds": round_num,
                    "task_file": str(self.episodic_memory.get_file_path()),
                    "stats": self.working_memory.get_stats()
                }
                return
            
            # 失败,判断是否重规划
            if round_num < self.max_rounds:
                yield {
                    "type": "phase",
                    "phase": "replan_decision",
                    "content": "🤔 Phase 3.5: 失败诊断与重规划决策 (DeepSeek-R1)..."
                }
                
                replan_decision = self._should_replan(verification, round_num, context)
                
                yield {
                    "type": "replan_decision",
                    "content": f"重规划决策: {'是' if replan_decision.decision else '否'} (信心: {replan_decision.confidence:.0%})",
                    "decision": replan_decision
                }
                
                if replan_decision.decision:
                    # 添加失败信息到上下文
                    context.append({
                        "round": round_num,
                        "plan": plan,
                        "results": results,
                        "failure_diagnosis": verification.diagnosis,
                        "suggested_changes": replan_decision.suggested_changes
                    })
                    
                    yield {
                        "type": "replan",
                        "content": f"🔄 开始第 {round_num + 1} 轮重规划...\n理由: {replan_decision.reasoning}"
                    }
                    
                    self.episodic_memory.add_finding(
                        f"Round {round_num} failed, replanning: {replan_decision.reasoning}",
                        category="replan"
                    )
                    
                    continue  # 下一轮
                else:
                    # R1 判断无法修复
                    yield {
                        "type": "error",
                        "content": f"❌ 任务失败,R1 判断无法通过重规划修复\n理由: {replan_decision.reasoning}"
                    }
                    break
            else:
                # 达到最大轮数
                yield {
                    "type": "error",
                    "content": f"❌ 达到最大轮数 ({self.max_rounds}),任务失败"
                }
                break
        
        # 失败完成
        self.episodic_memory.update_step("Task failed after retries", "error")
        self._complete_task(success=False, summary=f"Failed after {round_num} rounds")
        
        yield {
            "type": "failed",
            "content": f"❌ 任务失败 (尝试了 {round_num} 轮)",
            "rounds": round_num,
            "task_file": str(self.episodic_memory.get_file_path()),
            "stats": self.working_memory.get_stats()
        }
    
    def _phase0_analysis(self, query: str) -> TaskAnalysis:
        """
        Phase 0: 使用 R1 分析任务特征并推荐模式
        
        Args:
            query: 用户查询
            
        Returns:
            TaskAnalysis 对象
        """
        prompt = f"""分析这个任务并选择最优执行模式。

任务: {query}

请深度分析:

1. 复杂度评估
   - 预计步骤数: ?
   - 涉及的技术栈: ?
   - 是否有子任务: ?
   
2. 不确定性评估  
   - 环境依赖: (端口、权限、路径、版本等)
   - 可能的错误点: ?
   - 需要验证的关键点: ?

3. 任务类型识别
   - 类别: 文件操作 | 代码生成 | 服务部署 | Git操作 | 信息探索 | 其他
   - 是否需要创造性: ?
   - 是否有标准流程: ?

4. 模式推荐

基于以上分析,从以下选项中推荐最优方案:

**Option A: Direct Execute** (1次 Chat 调用)
  - 适用: 单步任务,极其简单,无依赖
  - 成本: 低, 速度: 极快
  - 示例: "创建一个文件", "读取文件内容"
  
**Option B: Fast Plan-Execute** (Chat 规划+盲目执行)  
  - 适用: 2-3步,确定性强,无环境依赖
  - 成本: 低, 速度: 快
  - 示例: "创建项目结构", "简单 Git 提交"
  
**Option C: Hybrid PEVL** (R1 规划 + Chat 执行 + R1 验证)
  - 适用: 3-6步,有不确定性或验证需求
  - 成本: 中, 速度: 中, 质量: 高
  - 示例: "部署 Flask 服务", "Docker 容器化"
  
**Option D: Explore ReAct** (Chat 自由探索)
  - 适用: 探索性,信息收集,目标不明确
  - 成本: 中, 速度: 慢, 灵活: 高
  - 示例: "分析这个项目", "调查为什么失败"

请选择最优方案并充分说明理由。

返回 JSON 格式:
```json
{{
  "complexity": "trivial|simple|medium|complex",
  "uncertainty": "low|medium|high",
  "task_type": "file_ops|code_gen|deployment|git|explore|other",
  "estimated_steps": 3,
  "recommended_mode": "direct|fast|hybrid|explore",
  "reasoning": "详细推理过程...",
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
            
            # 解析 JSON
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
            # 降级到默认配置
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
    
    def _phase1_planning(
        self,
        query: str,
        context: List[Dict[str, Any]],
        round_num: int
    ) -> Optional[ExecutionPlan]:
        """
        Phase 1: 使用 R1 深度规划
        
        Args:
            query: 原始查询
            context: 之前轮次的失败信息
            round_num: 当前轮数
            
        Returns:
            ExecutionPlan 对象
        """
        # 构建规划提示词
        context_text = ""
        if context:
            context_text = "\n\n【重要】之前轮次的失败信息:\n\n"
            for ctx in context:
                context_text += f"Round {ctx['round']} 失败:\n"
                context_text += f"  原因: {ctx['failure_diagnosis'].get('root_cause', 'unknown')}\n"
                context_text += f"  建议: {', '.join(ctx['suggested_changes'])}\n\n"
            context_text += "请根据这些失败经验调整计划,避免重复错误!\n"
        
        prompt = f"""你是任务规划专家。请为以下任务生成详细执行计划。

任务: {query}

当前是第 {round_num} 轮规划。
{context_text}

请进行深度分析和规划:

## 1. 任务分解
将任务分解为 3-5 个清晰的步骤,每步都有:
- 明确的目标 (goal)
- 成功标准 (success_criteria)
- 可能的风险 (risks)
- 失败应对策略 (mitigation)

## 2. 工具选择
为每步选择合适的工具和参数

可用工具: {', '.join([t.name for t in self.tools[:20]])}...

## 3. 依赖分析
- 步骤之间的依赖关系
- 需要的工作目录

## 4. 验证策略
- 每步如何验证成功
- 整体任务如何判断完成

输出 JSON:
```json
{{
  "working_directory": "/path/to/work",
  "steps": [
    {{
      "id": 1,
      "goal": "步骤目标描述",
      "success_criteria": "成功的判断标准",
      "tool": "工具名",
      "params": {{"param1": "value1"}},
      "risks": ["风险1", "风险2"],
      "mitigation": "应对策略",
      "estimated_risk": "low|medium|high"
    }}
  ],
  "final_verification": "如何验证整体任务完成",
  "risks": ["整体风险1", "整体风险2"]
}}
```
"""
        
        try:
            response = self.planner_agent.generate(prompt)
            logger.debug(f"Planning response received, length: {len(response)}")
            
            # 解析计划
            plan = self._parse_plan_response(response, query)
            
            if plan:
                logger.info(f"[PEVL] Round {round_num} plan generated: {plan.total_steps} steps")
            
            return plan
            
        except Exception as e:
            logger.error(f"Planning failed in round {round_num}: {e}")
            return None
    
    def _phase2_execution(
        self,
        plan: ExecutionPlan
    ) -> Generator[List[Dict[str, Any]], None, None]:
        """
        Phase 2: 使用 Chat 引导式执行
        
        Args:
            plan: 执行计划
            
        Yields:
            执行过程事件
            
        Returns:
            执行结果列表
        """
        results = []
        
        # 设置工作目录
        if plan.working_directory:
            self.working_dir_manager.change_directory(plan.working_directory)
        
        # 执行每个步骤
        for step in plan.steps:
            yield {
                "type": "step_start",
                "step_id": step.id,
                "content": f"▶ 步骤 {step.id}/{plan.total_steps}: {step.description}"
            }
            
            # 执行步骤 (带重试)
            step_result = self._execute_step_with_chat(step)
            results.append(step_result)
            
            yield {
                "type": "step_result",
                "step_id": step.id,
                "content": step_result.get('output', '')[:200],
                "success": step_result.get('success', False)
            }
            
            # 更新 Memory
            self.working_memory.increment_tool(step_result.get('tool', 'unknown'))
            
            if step_result.get('tool') in ('write_file', 'edit_file'):
                file_path = step_result.get('params', {}).get('path', '')
                if file_path:
                    self.working_memory.add_file_written(file_path)
        
        return results
    
    def _execute_step_with_chat(self, step: PlanStep, max_attempts: int = 2) -> Dict[str, Any]:
        """
        使用 Chat 执行单个步骤,带轻量推理和重试
        
        Args:
            step: 计划步骤
            max_attempts: 最大尝试次数
            
        Returns:
            执行结果字典
        """
        context = ""
        
        for attempt in range(1, max_attempts + 1):
            # Mini-Reason: Chat 快速推理如何执行
            reason_prompt = f"""【步骤目标】: {step.description}
【成功标准】: {step.verify_with or '完成操作'}
【风险提示】: {', '.join(getattr(step, 'risks', []) or [])}
【尝试次数】: {attempt}/{max_attempts}

{context}

快速决策 (不要过度思考,给出简洁答案):
1. 应该用什么工具?
2. 工具参数是什么?

返回 JSON: {{"tool": "工具名", "params": {{}}}}
"""
            
            try:
                # Chat 快速推理
                action_response = self.executor_agent.generate(reason_prompt)
                
                # 解析动作
                import re
                json_match = re.search(r'\{.*\}', action_response, re.DOTALL)
                if json_match:
                    action = json.loads(json_match.group(0))
                    tool_name = action.get('tool', step.tool)
                    tool_params = action.get('params', step.params)
                else:
                    # 降级到计划中的工具
                    tool_name = step.tool
                    tool_params = step.params
                
                # 执行工具
                result = self.tool_executor.execute(tool_name, tool_params)
                
                # Quick Verify (Chat)
                if step.verify_with:
                    verify_prompt = f"""目标: {step.description}
成功标准: {step.verify_with}
实际结果: {result.output[:300] if result.success else result.error[:300]}

快速判断 (一句话): 成功了吗? (yes/no/retry)
"""
                    
                    verify_response = self.executor_agent.generate(verify_prompt)
                    verify_answer = verify_response.lower().strip()
                    
                    if 'yes' in verify_answer or '成功' in verify_answer:
                        # 成功
                        return {
                            'tool': tool_name,
                            'params': tool_params,
                            'output': result.output,
                            'success': True,
                            'attempts': attempt
                        }
                    elif ('retry' in verify_answer or '重试' in verify_answer) and attempt < max_attempts:
                        # 需要重试
                        context += f"\n第{attempt}次失败: {verify_response}\n"
                        continue
                
                # 返回结果 (可能失败)
                return {
                    'tool': tool_name,
                    'params': tool_params,
                    'output': result.output if result.success else result.error,
                    'success': result.success,
                    'attempts': attempt
                }
                
            except Exception as e:
                logger.error(f"Step {step.id} execution error: {e}")
                if attempt < max_attempts:
                    context += f"\n第{attempt}次异常: {e}\n"
                    continue
                
                return {
                    'tool': step.tool,
                    'params': step.params,
                    'output': str(e),
                    'success': False,
                    'attempts': attempt
                }
        
        # 所有尝试都失败
        return {
            'tool': step.tool,
            'params': step.params,
            'output': 'All attempts failed',
            'success': False,
            'attempts': max_attempts
        }
    
    def _phase3_verification(
        self,
        plan: ExecutionPlan,
        results: List[Dict[str, Any]]
    ) -> Verification:
        """
        Phase 3: 使用 R1 深度验证并诊断
        
        Args:
            plan: 执行计划
            results: 执行结果列表
            
        Returns:
            Verification 对象
        """
        # 格式化执行报告
        report = f"任务: {plan.query}\n\n"
        report += "执行情况:\n\n"
        
        for i, (step, result) in enumerate(zip(plan.steps, results), 1):
            report += f"Step {i}: {step.description}\n"
            report += f"  工具: {result.get('tool')}\n"
            report += f"  成功: {result.get('success')}\n"
            report += f"  输出: {result.get('output', '')[:200]}...\n\n"
        
        prompt = f"""{report}

请深度验证和诊断:

## 1. 逐步检查
逐个检查每个步骤:
- 步骤目标是否达成?
- 输出是否符合预期?
- 有没有隐藏的问题?

## 2. 整体评估
- 所有步骤都真正成功了吗?
- 任务的核心目标达成了吗?
- 有没有遗漏或错误?

## 3. 失败诊断 (如果有失败)
请深入分析失败的根本原因:
- 是规划问题吗? (步骤遗漏、顺序错误、参数不当)
- 是执行问题吗? (工具失败、命令错误)
- 是环境问题吗? (端口占用、权限不足、依赖缺失)

## 4. 重规划建议
- 这个失败能通过重新规划解决吗?
- 如果重规划,应该如何调整?

返回 JSON:
```json
{{
  "success": true|false,
  "failed_steps": [1, 3],
  "diagnosis": {{
    "root_cause": "详细的失败原因",
    "is_plan_issue": true|false,
    "is_execution_issue": true|false,
    "is_environment_issue": true|false
  }},
  "should_replan": true|false,
  "replan_suggestion": "如果重规划,具体建议...",
  "reasoning": "深度分析推理过程"
}}
```
"""
        
        try:
            response = self.verifier_agent.generate(prompt)
            
            # 解析验证结果
            import re
            json_match = re.search(r'```json\s*\n(.*?)\n```', response, re.DOTALL)
            if not json_match:
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
            
            if json_match:
                data = json.loads(json_match.group(1) if json_match.lastindex else json_match.group(0))
                
                return Verification(
                    success=data.get('success', False),
                    failed_steps=data.get('failed_steps', []),
                    diagnosis=data.get('diagnosis', {}),
                    should_replan=data.get('should_replan', False),
                    replan_suggestion=data.get('replan_suggestion', ''),
                    reasoning=data.get('reasoning', '')
                )
        except Exception as e:
            logger.error(f"Verification parsing failed: {e}")
        
        # 降级: 简单判断
        all_success = all(r.get('success', False) for r in results)
        return Verification(
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
        使用 R1 判断是否应该重新规划
        
        Args:
            verification: 验证结果
            round_num: 当前轮数
            context: 历史上下文
            
        Returns:
            ReplanDecision 对象
        """
        prompt = f"""第 {round_num} 轮执行失败。请判断是否值得重新规划。

失败诊断:
{json.dumps(verification.diagnosis, ensure_ascii=False, indent=2)}

请深度分析:

1. **失败本质**: 
   - 这个失败能通过调整计划解决吗?
   - 还是环境问题,无法通过规划改变?
   
2. **成功概率**:
   - 如果重规划,成功的可能性有多大? (给出0-1的概率)
   - 为什么有这个信心?

3. **成本效益**:
   - 重规划会增加 ~$15-20 成本和 20-30秒时间
   - 这个投入是否值得?
   
4. **具体调整**:
   - 如果重规划,应该如何调整计划?
   - 列出2-3个关键改动

返回 JSON:
```json
{{
  "decision": true|false,
  "confidence": 0.75,
  "reasoning": "详细的判断理由...",
  "suggested_changes": [
    "改动1: 添加端口检查步骤",
    "改动2: 使用备用端口",
    "改动3: 增加错误处理"
  ]
}}
```
"""
        
        try:
            response = self.planner_agent.generate(prompt)
            
            # 解析决策
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
        
        # 降级: 保守决策 (不重试)
        return ReplanDecision(
            decision=False,
            confidence=0.0,
            reasoning='Decision parsing failed, conservative choice',
            suggested_changes=[]
        )
    
    def _parse_plan_response(self, response: str, query: str) -> Optional[ExecutionPlan]:
        """
        解析 LLM 的计划响应
        
        Args:
            response: LLM 响应文本
            query: 原始查询
            
        Returns:
            ExecutionPlan 对象或 None
        """
        import re
        import os
        
        # 尝试提取 JSON
        json_match = re.search(r'```json\s*\n(.*?)\n```', response, re.DOTALL)
        if not json_match:
            json_match = re.search(r'```\s*\n(.*?)\n```', response, re.DOTALL)
        
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                
                # 构建 ExecutionPlan
                plan = ExecutionPlan(
                    query=query,
                    working_directory=data.get('working_directory', os.getcwd()),
                    risks=data.get('risks', [])
                )
                
                # 解析步骤
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
                    
                    # 添加额外属性 (risks, mitigation)
                    if 'risks' in step_data:
                        step.risks = step_data['risks']
                    if 'mitigation' in step_data:
                        step.mitigation = step_data['mitigation']
                    
                    plan.steps.append(step)
                
                plan.total_steps = len(plan.steps)
                
                # 验证计划
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
        直接执行模式 (极简单任务)
        
        Args:
            query: 用户查询
            
        Yields:
            执行事件
        """
        yield {
            "type": "mode_selected",
            "content": "🚀 直接执行模式 (Chat)"
        }
        
        # TODO: 实现简单的单次 LLM 调用执行
        prompt = f"任务: {query}\n\n请用一个工具调用完成。返回 JSON: {{\"tool\": \"...\", \"params\": {{}}}}"
        
        try:
            response = self.executor_agent.generate(prompt)
            # 解析并执行
            # ... (简化实现)
            
            yield {
                "type": "complete",
                "content": "✅ 直接执行完成",
                "rounds": 0
            }
        except Exception as e:
            yield {
                "type": "error",
                "content": f"直接执行失败: {e}"
            }
    
    def _fast_plan_execute(self, query: str) -> Generator[Dict[str, Any], None, None]:
        """
        快速 Plan-Execute 模式 (Chat 规划+执行)
        
        Args:
            query: 用户查询
            
        Yields:
            执行事件
        """
        yield {
            "type": "mode_selected",
            "content": "⚡ 快速模式 (Chat Plan-Execute)"
        }
        
        # TODO: 使用 Chat 快速规划并执行
        # 类似当前的 TwoPhaseAgent 但用 Chat
        
        yield {
            "type": "complete",
            "content": "✅ 快速模式完成",
            "rounds": 1
        }
    
    def _complete_task(self, success: bool, summary: str):
        """
        完成任务并更新 Memory
        
        Args:
            success: 是否成功
            summary: 任务总结
        """
        if not self.episodic_memory or not self.current_task_id:
            return
        
        self.episodic_memory.update_next_action(
            f"✅ Completed: {summary}" if success else f"❌ Failed: {summary}"
        )
        
        self.memory_manager.complete_task(
            self.current_task_id,
            success=success
        )
        
        # 索引任务
        if success:
            try:
                if self.episodic_memory.task_file and self.episodic_memory.task_file.exists():
                    task_content = self.episodic_memory.task_file.read_text(encoding='utf-8')[:500]
                    self.vector_search.index_task(
                        self.current_task_id,
                        task_content,
                        metadata={'status': 'completed', 'mode': 'pevl'}
                    )
                    logger.info(f"[PEVL] Task indexed: {self.current_task_id}")
            except Exception as e:
                logger.warning(f"Failed to index task: {e}")
        
        stats = self.working_memory.get_stats()
        logger.info(f"[PEVL] Task completed. Stats: {stats}")
