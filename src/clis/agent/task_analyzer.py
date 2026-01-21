"""
Task Analyzer - Use R1 to analyze task characteristics and recommend execution strategies

Core features:
- Analyze task complexity
- Assess uncertainty
- Identify task type
- Recommend execution mode
- Recommend model combination
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
    """Task analysis result"""
    complexity: str  # trivial | simple | medium | complex
    uncertainty: str  # low | medium | high
    task_type: str  # file_ops | code_gen | deployment | git | explore | other
    estimated_steps: int
    recommended_mode: str  # direct | fast | hybrid | explore
    reasoning: str
    model_config: Dict[str, str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
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
    Task Analyzer
    
    Uses DeepSeek-R1's reasoning capabilities to analyze task characteristics and recommend optimal execution strategies
    """
    
    # Analysis prompt template
    ANALYSIS_PROMPT_TEMPLATE = """Analyze this task and select the optimal execution mode.

Task: {query}

Please perform **deep analysis**:

## 1. Complexity Assessment
- Estimated number of steps: How many steps to complete?
- Technology stack involved: (Python, Flask, Git, Docker, etc)
- Are there subtasks or dependencies?
- Complexity of each step: (simple tool calls vs complex logic)

## 2. Uncertainty Assessment  
- **Environment dependencies**: Does it depend on ports, permissions, paths, versions, etc?
- **Possible errors**: Where are errors likely to occur?
- **Verification requirements**: What key points need verification?
- **Risk level**: High-risk operations (delete, deploy) or low-risk (read, query)?

## 3. Task Type Identification
- **Main categories**: 
  - file_ops: File read/write, directory operations
  - code_gen: Code generation, project creation
  - deployment: Service deployment, containerization
  - git: Git version control operations
  - explore: Information exploration, investigation analysis
  - other: Other
  
- **Characteristics**:
  - Does it require creativity? (code generation vs standard operations)
  - Is there a standard process? (deployment process vs free exploration)
  - Does it require interaction? (explore unknown vs execute known)

## 4. Mode Recommendation

Based on deep analysis, select the **optimal solution** from the following 4 options:

### Option A: Direct Execute (single Chat call)
- **Applicable conditions**: 
  - Number of steps = 1
  - Complexity = trivial
  - Uncertainty = low
  - Standard tool calls
  
- **Cost**: $0.8
- **Speed**: Very fast (5s)
- **Success rate**: 90%

- **Examples**: 
  - "Create an empty file"
  - "Read file content"
  - "View current directory"

### Option B: Fast Plan-Execute (Chat planning + blind execution)
- **Applicable conditions**:
  - Number of steps = 2-3
  - Complexity = simple
  - Uncertainty = low
  - High certainty, no verification needed
  
- **Cost**: $3
- **Speed**: Fast (10s)
- **Success rate**: 85%

- **Examples**:
  - "Create project directory structure"
  - "Simple Git add+commit"
  - "Read multiple files"

### Option C: Hybrid PEVL (R1 planning + Chat execution + R1 verification)
- **Applicable conditions**:
  - Number of steps = 3-6
  - Complexity = medium|complex
  - Uncertainty = medium|high
  - Requires verification and error handling
  
- **Cost**: $15-25
- **Speed**: Medium (25-40s)
- **Success rate**: 90-95%

- **Examples**:
  - "Deploy Flask service"
  - "Create Django project"
  - "Docker containerize application"

### Option D: Explore ReAct (Chat free exploration)
- **Applicable conditions**:
  - Exploratory tasks
  - Unclear objectives
  - Requires information gathering
  
- **Cost**: $10-20
- **Speed**: Slow (30-60s)
- **Success rate**: 70-80%

- **Examples**:
  - "Analyze this project's architecture"
  - "Investigate why tests failed"
  - "Find performance bottlenecks"

## 5. Model Configuration Recommendation

Based on task characteristics, recommend model combination:

- **Planner**: 
  - Complex tasks → deepseek-r1
  - Simple tasks → deepseek-chat

- **Executor**:
  - Heavy code generation → qwen-2.5-coder-32b
  - General tasks → deepseek-chat
  
- **Verifier**:
  - Critical tasks → deepseek-r1
  - Simple tasks → none (skip)

## Final Decision

Please reason thoroughly, considering comprehensively:
- Task characteristics
- Cost-effectiveness
- User expectations (fast vs reliable)

Return JSON:
```json
{{
  "complexity": "trivial|simple|medium|complex",
  "uncertainty": "low|medium|high",
  "task_type": "file_ops|code_gen|deployment|git|explore|other",
  "estimated_steps": 3,
  "recommended_mode": "direct|fast|hybrid|explore",
  "reasoning": "Detailed reasoning process, explaining why this mode was chosen...",
  "model_config": {{
    "planner": "deepseek-r1|deepseek-chat",
    "executor": "qwen-2.5-coder-32b|deepseek-chat",
    "verifier": "deepseek-r1|deepseek-chat|none"
  }}
}}
```

Please perform deep reasoning and provide the optimal recommendation.
"""
    
    def __init__(self, agent: Agent):
        """
        Initialize analyzer
        
        Args:
            agent: LLM Agent (should be configured as DeepSeek-R1)
        """
        self.agent = agent
    
    def analyze(self, query: str) -> TaskAnalysis:
        """
        Analyze task and recommend execution strategy
        
        Args:
            query: User query
            
        Returns:
            TaskAnalysis object
        """
        prompt = self.ANALYSIS_PROMPT_TEMPLATE.format(query=query)
        
        try:
            logger.info("[TaskAnalyzer] Analyzing task with R1...")
            response = self.agent.generate(prompt)
            logger.debug(f"Analysis response length: {len(response)}")
            
            # Parse JSON response
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
        
        # Fallback to default configuration
        logger.warning("Using default analysis due to parsing failure")
        return self._get_default_analysis(query)
    
    def _parse_response(self, response: str) -> Optional[TaskAnalysis]:
        """
        Parse R1 analysis response
        
        Args:
            response: LLM response text
            
        Returns:
            TaskAnalysis object or None
        """
        # Try to extract JSON
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
        Get default analysis result (fallback solution)
        
        Args:
            query: User query
            
        Returns:
            Default TaskAnalysis
        """
        # Simple heuristic rules
        query_lower = query.lower()
        
        # Determine complexity
        if any(word in query_lower for word in ['flask', 'django', 'docker', 'deploy']):
            complexity = 'medium'
            estimated_steps = 4
        elif any(word in query_lower for word in ['create', 'write', 'read', 'list']):
            complexity = 'simple'
            estimated_steps = 2
        else:
            complexity = 'medium'
            estimated_steps = 3
        
        # Determine uncertainty
        if any(word in query_lower for word in ['port', 'service', 'server', 'deploy']):
            uncertainty = 'high'
        else:
            uncertainty = 'low'
        
        # Recommend mode
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
