"""
Task Analyzer - 使用 R1 分析任务特征并推荐执行策略

核心功能:
- 分析任务复杂度
- 评估不确定性
- 识别任务类型
- 推荐执行模式
- 推荐模型组合
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
import json
import re

from clis.agent.agent import Agent
from clis.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TaskAnalysis:
    """任务分析结果"""
    complexity: str  # trivial | simple | medium | complex
    uncertainty: str  # low | medium | high
    task_type: str  # file_ops | code_gen | deployment | git | explore | other
    estimated_steps: int
    recommended_mode: str  # direct | fast | hybrid | explore
    reasoning: str
    model_config: Dict[str, str]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'complexity': self.complexity,
            'uncertainty': self.uncertainty,
            'task_type': self.task_type,
            'estimated_steps': self.estimated_steps,
            'recommended_mode': self.recommended_mode,
            'reasoning': self.reasoning,
            'model_config': self.model_config
        }


class TaskAnalyzer:
    """
    任务分析器
    
    使用 DeepSeek-R1 的推理能力分析任务特征并推荐最优执行策略
    """
    
    # 分析提示词模板
    ANALYSIS_PROMPT_TEMPLATE = """分析这个任务并选择最优执行模式。

任务: {query}

请进行**深度分析**:

## 1. 复杂度评估
- 预计步骤数: 多少步能完成?
- 涉及的技术栈: (Python, Flask, Git, Docker, etc)
- 是否有子任务或依赖: ?
- 每步的复杂度: (简单工具调用 vs 复杂逻辑)

## 2. 不确定性评估  
- **环境依赖**: 是否依赖端口、权限、路径、版本等?
- **可能的错误**: 哪些地方容易出错?
- **验证需求**: 需要验证哪些关键点?
- **风险等级**: 高风险操作 (删除、部署) 还是低风险 (读取、查询)?

## 3. 任务类型识别
- **主要类别**: 
  - file_ops: 文件读写、目录操作
  - code_gen: 代码生成、项目创建
  - deployment: 服务部署、容器化
  - git: Git 版本控制操作
  - explore: 信息探索、调查分析
  - other: 其他
  
- **特点**:
  - 是否需要创造性? (生成代码 vs 标准操作)
  - 是否有标准流程? (部署流程 vs 自由探索)
  - 是否需要交互? (探索未知 vs 执行已知)

## 4. 模式推荐

基于深度分析,从以下4个选项中选择**最优方案**:

### Option A: Direct Execute (单次 Chat 调用)
- **适用条件**: 
  - 步骤数 = 1
  - 复杂度 = trivial
  - 不确定性 = low
  - 标准工具调用
  
- **成本**: $0.8
- **速度**: 极快 (5s)
- **成功率**: 90%

- **示例**: 
  - "创建一个空文件"
  - "读取文件内容"
  - "查看当前目录"

### Option B: Fast Plan-Execute (Chat 规划+盲目执行)
- **适用条件**:
  - 步骤数 = 2-3
  - 复杂度 = simple
  - 不确定性 = low
  - 确定性强,不需验证
  
- **成本**: $3
- **速度**: 快 (10s)
- **成功率**: 85%

- **示例**:
  - "创建项目目录结构"
  - "简单的 Git add+commit"
  - "读取多个文件"

### Option C: Hybrid PEVL (R1 规划 + Chat 执行 + R1 验证)
- **适用条件**:
  - 步骤数 = 3-6
  - 复杂度 = medium|complex
  - 不确定性 = medium|high
  - 需要验证和错误处理
  
- **成本**: $15-25
- **速度**: 中 (25-40s)
- **成功率**: 90-95%

- **示例**:
  - "部署 Flask 服务"
  - "创建 Django 项目"
  - "Docker 容器化应用"

### Option D: Explore ReAct (Chat 自由探索)
- **适用条件**:
  - 探索性任务
  - 目标不明确
  - 需要信息收集
  
- **成本**: $10-20
- **速度**: 慢 (30-60s)
- **成功率**: 70-80%

- **示例**:
  - "分析这个项目的架构"
  - "调查为什么测试失败"
  - "找到性能瓶颈"

## 5. 模型配置推荐

基于任务特点,推荐模型组合:

- **Planner**: 
  - 复杂任务 → deepseek-r1
  - 简单任务 → deepseek-chat

- **Executor**:
  - 代码生成多 → qwen-2.5-coder-32b
  - 通用任务 → deepseek-chat
  
- **Verifier**:
  - 关键任务 → deepseek-r1
  - 简单任务 → none (跳过)

## 最终决策

请充分推理,综合考虑:
- 任务特点
- 成本效益
- 用户期望 (快速 vs 可靠)

返回 JSON:
```json
{{
  "complexity": "trivial|simple|medium|complex",
  "uncertainty": "low|medium|high",
  "task_type": "file_ops|code_gen|deployment|git|explore|other",
  "estimated_steps": 3,
  "recommended_mode": "direct|fast|hybrid|explore",
  "reasoning": "详细推理过程,说明为什么选择这个模式...",
  "model_config": {{
    "planner": "deepseek-r1|deepseek-chat",
    "executor": "qwen-2.5-coder-32b|deepseek-chat",
    "verifier": "deepseek-r1|deepseek-chat|none"
  }}
}}
```

请进行深度推理,给出最优推荐。
"""
    
    def __init__(self, agent: Agent):
        """
        初始化分析器
        
        Args:
            agent: LLM Agent (应该配置为 DeepSeek-R1)
        """
        self.agent = agent
    
    def analyze(self, query: str) -> TaskAnalysis:
        """
        分析任务并推荐执行策略
        
        Args:
            query: 用户查询
            
        Returns:
            TaskAnalysis 对象
        """
        prompt = self.ANALYSIS_PROMPT_TEMPLATE.format(query=query)
        
        try:
            logger.info("[TaskAnalyzer] Analyzing task with R1...")
            response = self.agent.generate(prompt)
            logger.debug(f"Analysis response length: {len(response)}")
            
            # 解析 JSON 响应
            analysis = self._parse_response(response)
            
            if analysis:
                logger.info(
                    f"[TaskAnalyzer] Result: {analysis.recommended_mode} mode, "
                    f"{analysis.estimated_steps} steps, "
                    f"complexity={analysis.complexity}, "
                    f"uncertainty={analysis.uncertainty}"
                )
                return analysis
            
        except Exception as e:
            logger.error(f"Task analysis failed: {e}")
        
        # 降级到默认配置
        logger.warning("Using default analysis due to parsing failure")
        return self._get_default_analysis(query)
    
    def _parse_response(self, response: str) -> Optional[TaskAnalysis]:
        """
        解析 R1 的分析响应
        
        Args:
            response: LLM 响应文本
            
        Returns:
            TaskAnalysis 对象或 None
        """
        # 尝试提取 JSON
        json_match = re.search(r'```json\s*\n(.*?)\n```', response, re.DOTALL)
        if not json_match:
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
        
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
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing failed: {e}")
                logger.debug(f"JSON content: {json_match.group(0)[:500]}")
                return None
        
        logger.warning("No valid JSON found in analysis response")
        return None
    
    def _get_default_analysis(self, query: str) -> TaskAnalysis:
        """
        获取默认分析结果 (降级方案)
        
        Args:
            query: 用户查询
            
        Returns:
            默认的 TaskAnalysis
        """
        # 简单的启发式规则
        query_lower = query.lower()
        
        # 判断复杂度
        if any(word in query_lower for word in ['flask', 'django', 'docker', 'deploy']):
            complexity = 'medium'
            estimated_steps = 4
        elif any(word in query_lower for word in ['create', 'write', 'read', 'list']):
            complexity = 'simple'
            estimated_steps = 2
        else:
            complexity = 'medium'
            estimated_steps = 3
        
        # 判断不确定性
        if any(word in query_lower for word in ['port', 'service', 'server', 'deploy']):
            uncertainty = 'high'
        else:
            uncertainty = 'low'
        
        # 推荐模式
        if complexity == 'simple' and uncertainty == 'low' and estimated_steps <= 2:
            recommended_mode = 'fast'
        else:
            recommended_mode = 'hybrid'
        
        return TaskAnalysis(
            complexity=complexity,
            uncertainty=uncertainty,
            task_type='other',
            estimated_steps=estimated_steps,
            recommended_mode=recommended_mode,
            reasoning='Fallback heuristic analysis',
            model_config={
                'planner': 'deepseek-r1',
                'executor': 'deepseek-chat',
                'verifier': 'deepseek-r1'
            }
        )
