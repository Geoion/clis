"""
Task Planner - Planning phase for two-phase execution mode

Based on Claude Code and Cursor design principles:
1. Plan first (read-only exploration)
2. Execute next (act according to plan)
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
    """A single step in the execution plan"""
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
    """Complete execution plan"""
    query: str
    working_directory: str
    steps: List[PlanStep] = field(default_factory=list)
    total_steps: int = 0
    estimated_time: str = "unknown"
    risks: List[str] = field(default_factory=list)
    
    def to_markdown(self) -> str:
        """
        Convert to Markdown format (editable)
        
        Returns:
            Plan in Markdown format
        """
        md = f"""**Task**

{self.query}

**Working Directory**

{self.working_directory}

**Steps ({self.total_steps})**

"""
        for step in self.steps:
            deps = f" (depends on: {step.depends_on})" if step.depends_on else ""
            
            # Format params as indented JSON
            params_json = json.dumps(step.params, ensure_ascii=False, indent=2)
            # Indent each line of the JSON for better readability
            params_lines = params_json.split('\n')
            params_formatted = '\n   '.join(params_lines)
            
            md += f"""**Step {step.id}: {step.description}**{deps}

 • **Tool**: `{step.tool}`
 
 • **Params**:
   ```json
   {params_formatted}
   ```
"""
            
            # Add optional fields only if present
            if step.working_directory:
                md += f" • **Directory**: `{step.working_directory}`\n"
            
            if step.verify_with:
                md += f" • **Verify**: {step.verify_with}\n"
            
            md += f" • **Risk**: {step.estimated_risk}\n\n"
        
        # Risk warnings
        if self.risks:
            md += f"**⚠️ Risk Warnings**\n\n"
            for risk in self.risks:
                md += f" • {risk}\n"
        
        return md
    
    @classmethod
    def from_markdown(cls, md: str) -> 'ExecutionPlan':
        """
        Parse execution plan from Markdown
        
        Args:
            md: Plan in Markdown format
            
        Returns:
            ExecutionPlan object
        """
        # Simple parsing (can be improved later)
        lines = md.split('\n')
        plan = cls(query="", working_directory="")
        
        # TODO: Implement complete Markdown parsing
        return plan


class TaskPlanner:
    """
    Task Planner
    
    Features:
    1. Analyze task complexity
    2. Generate structured execution plan
    3. Use only read-only tools for exploration
    """
    
    def __init__(self, agent, tools):
        """
        Initialize planner
        
        Args:
            agent: LLM Agent
            tools: List of all available tools
        """
        self.agent = agent
        self.all_tools = tools
        
        # Read-only tools (for Planning phase)
        self.readonly_tools = self._get_readonly_tools()
    
    def _get_readonly_tools(self) -> List:
        """Get list of read-only tools"""
        readonly_names = {
            'read_file', 'list_files', 'file_tree', 'search_files', 'grep',
            'git_status', 'git_log', 'git_diff', 'git_branch',
            'system_info', 'check_command', 'get_env', 'list_processes',
            'codebase_search', 'find_definition', 'find_references', 'get_symbols',
            'execute_command',  # Can be used for exploration (read-only commands)
            'docker_ps', 'docker_logs', 'docker_inspect', 'docker_stats', 'docker_images',
            'http_request', 'check_port'
        }
        
        return [t for t in self.all_tools if t.name in readonly_names]
    
    def assess_complexity(self, query: str) -> str:
        """
        Assess task complexity
        
        Args:
            query: User query
            
        Returns:
            "simple", "medium", or "complex"
        """
        query_lower = query.lower()
        
        # Simple task indicators (single action)
        simple_patterns = [
            # Single file operation
            r'^(create|write|read|show|display)\s+.*\s+(file|txt|py)$',
            r'^list\s+',
            r'^check\s+',
            r'^show\s+',
            # Single query
            r'^(what|where|how)\s+',
        ]
        
        # Complex task indicators (explicit multi-step)
        complex_patterns = [
            r'(create|build|setup).*project',  # Create project
            r'(refactor|migrate|restructure)',  # Refactor/migrate
            r'(and|then).*and',  # Multiple "and" (3+ steps)
            r'\d+\.\s+.*\d+\.',  # Numbered list (1. xxx 2. xxx)
        ]
        
        # Medium task indicators
        medium_keywords = ['create', 'setup', 'install', 'configure', 'test']
        
        # Check simple tasks
        if any(re.search(p, query_lower) for p in simple_patterns):
            return "simple"
        
        # Check complex tasks
        if any(re.search(p, query_lower) for p in complex_patterns):
            return "complex"
        
        # Check step count
        # Count separators: and, then, comma
        separators = query_lower.count(' and ') + query_lower.count(' then ') + query_lower.count('，')
        if separators >= 3:
            return "complex"
        elif separators >= 1:
            return "medium"
        
        # Check keywords
        if any(k in query_lower for k in medium_keywords):
            return "medium"
        
        # Default simple (bias towards simple)
        return "simple"
    
    def generate_plan(self, query: str, similar_tasks_text: str = "") -> ExecutionPlan:
        """
        Generate execution plan
        
        Args:
            query: User query
            similar_tasks_text: Similar historical task text (optional)
            
        Returns:
            ExecutionPlan object
        """
        # Prompt: Request Agent to generate structured plan
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
        
        # Call LLM to generate plan
        try:
            response = self.agent.generate(prompt)
            logger.debug(f"LLM response received, length: {len(response)}")
            
            # Parse JSON response
            plan = self._parse_plan_response(response, query)
            logger.debug(f"Plan parsed successfully, {plan.total_steps} steps")
            
            return plan
        except Exception as e:
            logger.error(f"Error in generate_plan: {e}")
            raise
    
    def _parse_plan_response(self, response: str, query: str) -> ExecutionPlan:
        """
        Parse LLM plan response
        
        Args:
            response: LLM response text
            query: Original query
            
        Returns:
            ExecutionPlan object
        """
        # Try to extract JSON
        json_match = re.search(r'```json\s*\n(.*?)\n```', response, re.DOTALL)
        if not json_match:
            json_match = re.search(r'```\s*\n(.*?)\n```', response, re.DOTALL)
        
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                
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
        
        # Fallback: create simple plan
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
