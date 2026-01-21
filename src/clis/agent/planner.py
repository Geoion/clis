"""
任务规划器 - 两阶段执行模式的 Planning 阶段

基于 Claude Code 和 Cursor 的设计理念：
1. 先计划（只读探索）
2. 再执行（按计划行动）
"""

import json
import os
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from clis.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PlanStep:
    """执行计划中的单个步骤"""
    id: int
    description: str
    tool: str
    params: Dict[str, Any]
    working_directory: Optional[str] = None
    verify_with: Optional[str] = None
    depends_on: List[int] = field(default_factory=list)
    estimated_risk: str = "low"  # low, medium, high


@dataclass
class ExecutionPlan:
    """完整的执行计划"""
    query: str
    working_directory: str
    steps: List[PlanStep] = field(default_factory=list)
    total_steps: int = 0
    estimated_time: str = "unknown"
    risks: List[str] = field(default_factory=list)
    
    def to_markdown(self) -> str:
        """
        转换为 Markdown 格式（可编辑）
        
        Returns:
            Markdown 格式的计划
        """
        md = f"""**执行计划**

**任务**

{self.query}

**工作目录**

`{self.working_directory}`

**步骤 ({self.total_steps} 个)**

"""
        for step in self.steps:
            deps = f" (依赖: {step.depends_on})" if step.depends_on else ""
            wd = f"\n • 目录: `{step.working_directory}`" if step.working_directory else ""
            verify = f"\n • 验证: {step.verify_with}" if step.verify_with else ""
            
            # 先生成 JSON 字符串，避免 f-string 中的花括号冲突
            params_json = json.dumps(step.params, ensure_ascii=False)
            
            md += f"""**步骤 {step.id}: {step.description}**{deps}

 • 工具: `{step.tool}`
 • 参数: `{params_json}`{wd}{verify}
 • 风险: {step.estimated_risk}

"""
        
        # 风险提示
        if self.risks:
            md += f"**⚠️ 风险提示**\n\n"
            for risk in self.risks:
                md += f" • {risk}\n"
        
        return md
    
    @classmethod
    def from_markdown(cls, md: str) -> 'ExecutionPlan':
        """
        从 Markdown 解析执行计划
        
        Args:
            md: Markdown 格式的计划
            
        Returns:
            ExecutionPlan 对象
        """
        # 简单解析（可以后续改进）
        lines = md.split('\n')
        plan = cls(query="", working_directory="")
        
        # TODO: 实现完整的 Markdown 解析
        return plan


class TaskPlanner:
    """
    任务规划器
    
    功能：
    1. 分析任务复杂度
    2. 生成结构化执行计划
    3. 只使用只读工具探索
    """
    
    def __init__(self, agent, tools):
        """
        初始化规划器
        
        Args:
            agent: LLM Agent
            tools: 所有可用工具列表
        """
        self.agent = agent
        self.all_tools = tools
        
        # 只读工具（用于 Planning 阶段）
        self.readonly_tools = self._get_readonly_tools()
    
    def _get_readonly_tools(self) -> List:
        """获取只读工具列表"""
        readonly_names = {
            'read_file', 'list_files', 'file_tree', 'search_files', 'grep',
            'git_status', 'git_log', 'git_diff', 'git_branch',
            'system_info', 'check_command', 'get_env', 'list_processes',
            'codebase_search', 'find_definition', 'find_references', 'get_symbols',
            'execute_command',  # 可用于探索（只读命令）
            'docker_ps', 'docker_logs', 'docker_inspect', 'docker_stats', 'docker_images',
            'http_request', 'check_port'
        }
        
        return [t for t in self.all_tools if t.name in readonly_names]
    
    def assess_complexity(self, query: str) -> str:
        """
        评估任务复杂度
        
        Args:
            query: 用户查询
            
        Returns:
            "simple", "medium", or "complex"
        """
        query_lower = query.lower()
        
        # 简单任务标志（单一动作）
        simple_patterns = [
            # 单个文件操作
            r'^(create|write|read|show|display)\s+.*\s+(file|txt|py)$',
            r'^list\s+',
            r'^check\s+',
            r'^show\s+',
            # 单个查询
            r'^(what|where|how)\s+',
        ]
        
        # 复杂任务标志（明确的多步骤）
        complex_patterns = [
            r'(create|build|setup).*project',  # 创建项目
            r'(refactor|migrate|restructure)',  # 重构/迁移
            r'(and|then).*and',  # 多个 and（3+步骤）
            r'\d+\.\s+.*\d+\.',  # 编号列表（1. xxx 2. xxx）
        ]
        
        # 中等任务标志
        medium_keywords = ['create', 'setup', 'install', 'configure', 'test']
        
        # 检查简单任务
        if any(re.search(p, query_lower) for p in simple_patterns):
            return "simple"
        
        # 检查复杂任务
        if any(re.search(p, query_lower) for p in complex_patterns):
            return "complex"
        
        # 检查步骤数量
        # 统计分隔符：and, then, 逗号
        separators = query_lower.count(' and ') + query_lower.count(' then ') + query_lower.count('，')
        if separators >= 3:
            return "complex"
        elif separators >= 1:
            return "medium"
        
        # 检查关键词
        if any(k in query_lower for k in medium_keywords):
            return "medium"
        
        # 默认简单（偏向简单）
        return "simple"
    
    def generate_plan(self, query: str, similar_tasks_text: str = "") -> ExecutionPlan:
        """
        生成执行计划
        
        Args:
            query: 用户查询
            similar_tasks_text: 相似历史任务文本（可选）
            
        Returns:
            ExecutionPlan 对象
        """
        # 提示词：要求 Agent 生成结构化计划
        similar_context = ""
        if similar_tasks_text:
            similar_context = f"\n{similar_tasks_text}\n"
        
        prompt = f"""You are a task planner. Generate a detailed execution plan for the following task.

TASK: {query}
{similar_context}

OUTPUT FORMAT (JSON):
```json
{{
  "working_directory": "/path/to/work/dir",
  "steps": [
    {{
      "id": 1,
      "description": "Step description",
      "tool": "tool_name",
      "params": {{"param1": "value1"}},
      "working_directory": "/optional/specific/dir",
      "verify_with": "optional verification method",
      "estimated_risk": "low|medium|high"
    }}
  ],
  "risks": ["risk 1", "risk 2"]
}}
```

AVAILABLE TOOLS (readonly only for planning):
{', '.join([t.name for t in self.readonly_tools])}

GUIDELINES:
1. **KEEP IT SIMPLE**: Break task into 2-4 concrete steps (NOT 5-7!)
2. **MERGE OPERATIONS**: Combine related actions in one step
   - Example: mkdir + cd → execute_command("mkdir -p /tmp/dir && cd /tmp/dir")
   - Example: create files → use write_file for each, don't verify after each one
3. **NO EXCESSIVE VERIFICATION**: Only verify at the END
   - ❌ BAD: write_file → list_files → write_file → list_files (wasteful!)
   - ✅ GOOD: write_file → write_file → write_file → verify once
4. **USE SPECIFIC TOOLS**: Prefer write_file over echo >, prefer git_add over git add
5. **WORKING DIRECTORY**: Specify once for the whole plan, use absolute paths in params
6. **GIT OPERATIONS**: Always specify the repository directory
7. **AVOID REDUNDANCY**: Don't include "check if exists" steps - just create/do it

EXAMPLES OF GOOD PLANS:

Example 1: "Create Flask app"
```json
{{
  "working_directory": "/tmp/flask_app",
  "steps": [
    {{"id": 1, "tool": "execute_command", "params": {{"command": "mkdir -p /tmp/flask_app"}}}},
    {{"id": 2, "tool": "write_file", "params": {{"path": "/tmp/flask_app/app.py", "content": "..."}}}},
    {{"id": 3, "tool": "execute_command", "params": {{"command": "cd /tmp/flask_app && git init && git add . && git commit -m 'init'"}}}}
  ]
}}
```

Example 2: "Edit and commit"
```json
{{
  "working_directory": ".",
  "steps": [
    {{"id": 1, "tool": "edit_file", "params": {{"path": "config.py", "old_content": "...", "new_content": "..."}}}},
    {{"id": 2, "tool": "execute_command", "params": {{"command": "git add config.py && git commit -m 'update config'"}}}}
  ]
}}
```

Generate a SIMPLE plan (2-4 steps, NO verification steps):
"""
        
        # 调用 LLM 生成计划
        try:
            response = self.agent.generate(prompt)
            logger.debug(f"LLM response received, length: {len(response)}")
            
            # 解析 JSON 响应
            plan = self._parse_plan_response(response, query)
            logger.debug(f"Plan parsed successfully, {plan.total_steps} steps")
            
            return plan
        except Exception as e:
            logger.error(f"Error in generate_plan: {e}")
            raise
    
    def _parse_plan_response(self, response: str, query: str) -> ExecutionPlan:
        """
        解析 LLM 的计划响应
        
        Args:
            response: LLM 响应文本
            query: 原始查询
            
        Returns:
            ExecutionPlan 对象
        """
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
                        description=step_data['description'],
                        tool=step_data['tool'],
                        params=step_data['params'],
                        working_directory=step_data.get('working_directory'),
                        verify_with=step_data.get('verify_with'),
                        depends_on=step_data.get('depends_on', []),
                        estimated_risk=step_data.get('estimated_risk', 'low')
                    )
                    plan.steps.append(step)
                
                plan.total_steps = len(plan.steps)
                
                # Validate plan has at least one step
                if plan.total_steps == 0:
                    logger.error("Plan has no steps, using fallback")
                    raise ValueError("Empty plan generated")
                
                return plan
            
            except Exception as e:
                logger.error(f"Failed to parse plan JSON: {e}")
                import traceback
                traceback.print_exc()
        
        # 降级：创建简单计划
        logger.warning("Could not parse plan, creating simple plan")
        return ExecutionPlan(
            query=query,
            working_directory=os.getcwd(),
            steps=[
                PlanStep(
                    id=1,
                    description=query,
                    tool="execute_command",
                    params={"command": "echo 'Planning failed, manual execution needed'"}
                )
            ],
            total_steps=1
        )
