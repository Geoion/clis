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
class ToolRecommendation:
    """Tool recommendation (not prescription)"""
    tool: str
    reason: str
    typical_use: str


@dataclass
class StepGuidance:
    """Strategic guidance for a step (not detailed plan)"""
    goal: str
    success_criteria: str
    considerations: List[str] = field(default_factory=list)
    backup_strategy: Optional[str] = None


@dataclass
class ExecutionPlan:
    """
    Strategic execution plan with tool recommendations and high-level guidance
    
    Philosophy:
    - Phase 1.1: Read-only exploration to understand environment
    - Phase 1.2: Strategic guidance based on exploration findings
    - NO detailed steps with specific tools/params
    - Recommend useful tools, but ReAct decides when/how
    - Provide strategic guidance: goals, criteria, considerations
    - Learn from skills and historical experiences
    - Every step executed by ReAct with full autonomy
    """
    query: str
    working_directory: str
    
    # New strategic format
    exploration_findings: Optional[str] = None  # Results from read-only exploration
    recommended_tools: List[ToolRecommendation] = field(default_factory=list)
    step_guidance: List[StepGuidance] = field(default_factory=list)
    overall_goal: Optional[str] = None
    lessons_learned: List[str] = field(default_factory=list)
    
    # Legacy format (for backward compatibility)
    first_step: Optional[PlanStep] = None  # Old adaptive format
    next_steps_guidance: List = field(default_factory=list)  # Old adaptive format
    steps: List[PlanStep] = field(default_factory=list)  # Old detailed format
    total_steps: int = 0
    estimated_time: str = "unknown"
    
    risks: List[str] = field(default_factory=list)
    
    @property
    def is_strategic(self) -> bool:
        """Check if this is a strategic plan (new format)"""
        return len(self.recommended_tools) > 0 or len(self.step_guidance) > 0
    
    @property
    def is_adaptive(self) -> bool:
        """Check if this is an adaptive plan (old new format)"""
        return self.first_step is not None
    
    @property
    def guidance_count(self) -> int:
        """Number of guidance steps"""
        return len(self.step_guidance) if self.is_strategic else len(self.next_steps_guidance)
    
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

"""
        
        # Strategic format (newest)
        if self.is_strategic:
            # Show exploration findings if available
            if self.exploration_findings:
                md += f"""**🔍 Exploration Findings**

{self.exploration_findings}

"""
            
            md += f"""**🎯 Overall Goal**

{self.overall_goal}

**🛠️ Recommended Tools** ({len(self.recommended_tools)} tools)

"""
            for i, tool_rec in enumerate(self.recommended_tools, 1):
                md += f"""**{i}. {tool_rec.tool}**
 • **Why**: {tool_rec.reason}
 • **Typical Use**: {tool_rec.typical_use}

"""
            
            md += f"""**📋 Step Guidance** ({len(self.step_guidance)} steps)

"""
            for i, guidance in enumerate(self.step_guidance, 1):
                md += f"""**Step {i}: {guidance.goal}**

 • **Success Criteria**: {guidance.success_criteria}
"""
                if guidance.considerations:
                    md += " • **Considerations**:\n"
                    for consideration in guidance.considerations:
                        md += f"   - {consideration}\n"
                
                if guidance.backup_strategy:
                    md += f" • **Backup Strategy**: {guidance.backup_strategy}\n"
                md += "\n"
            
            if self.lessons_learned:
                md += f"""**💡 Lessons Learned**

"""
                for lesson in self.lessons_learned:
                    md += f" • {lesson}\n"
                md += "\n"
        
        # Adaptive format (old new)
        elif self.is_adaptive:
            md += f"""**🎯 First Step** (Detailed)

{self.first_step.description}

 • **Tool**: `{self.first_step.tool}`
 
 • **Params**:
   ```json
   {json.dumps(self.first_step.params, ensure_ascii=False, indent=2)}
   ```
 • **Expected Output**: {getattr(self.first_step, 'verify_with', 'N/A')}
 • **Risk**: {self.first_step.estimated_risk}

**📋 Next Steps Guidance** ({len(self.next_steps_guidance)} steps)

"""
            for i, guidance in enumerate(self.next_steps_guidance, 1):
                md += f"""**{i}. {guidance.goal}**

 • **Success Criteria**: {guidance.success_criteria}
"""
                if guidance.backup_strategy:
                    md += f" • **Backup Strategy**: {guidance.backup_strategy}\n"
                md += "\n"
            
            if self.overall_goal:
                md += f"""**🎯 Overall Goal**

{self.overall_goal}

"""
        
        # Legacy format (backward compatibility)
        else:
            md += f"""**Steps ({self.total_steps})**

"""
            for step in self.steps:
                deps = f" (depends on: {step.depends_on})" if step.depends_on else ""
                
                # Format params as indented JSON
                params_json = json.dumps(step.params, ensure_ascii=False, indent=2)
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
    
    def explore_environment(self, query: str, tool_executor) -> str:
        """
        Phase 1.1: Explore environment with read-only tools
        
        Args:
            query: User query
            tool_executor: Tool executor for running read-only tools
            
        Returns:
            Exploration findings as formatted text
        """
        logger.info("[Planner] Starting read-only exploration phase")
        
        exploration_prompt = f"""You are exploring the environment to gather context for planning.

**Task**: {query}

**Available Read-Only Tools**: {', '.join([t.name for t in self.readonly_tools])}

**Exploration Goals**:
1. Understand the current state (files, directories, git status, etc.)
2. Identify relevant files and their content
3. Check for existing patterns or structures
4. Gather any information that will help with planning

**Instructions**:
- Use ONLY read-only tools (no modifications)
- Explore systematically (start broad, then narrow down)
- Focus on information relevant to the task
- Stop when you have enough context

**Output Format**:
For each exploration step, output JSON:
```json
{{
  "reasoning": "Why I'm doing this",
  "tool": "tool_name",
  "params": {{"param": "value"}},
  "done": false
}}
```

When done exploring, output:
```json
{{
  "done": true,
  "findings": "Summary of what I discovered"
}}
```

Start exploring:
"""
        
        findings = []
        max_explorations = 5  # Limit exploration steps
        
        for i in range(max_explorations):
            try:
                response = self.agent.generate(exploration_prompt)
                
                # Parse response
                import re
                json_match = re.search(r'```json\s*\n(.*?)\n```', response, re.DOTALL)
                if not json_match:
                    logger.warning("[Planner] Could not parse exploration response")
                    break
                
                data = json.loads(json_match.group(1))
                
                # Check if done
                if data.get('done'):
                    findings_summary = data.get('findings', '')
                    logger.info(f"[Planner] Exploration complete: {findings_summary[:100]}...")
                    break
                
                # Execute tool
                tool_name = data.get('tool')
                tool_params = data.get('params', {})
                reasoning = data.get('reasoning', '')
                
                logger.info(f"[Planner] Exploration step {i+1}: {tool_name} - {reasoning}")
                
                result = tool_executor.execute(tool_name, tool_params)
                
                finding = f"**Step {i+1}**: {reasoning}\n"
                finding += f"Tool: {tool_name}\n"
                if result.success:
                    finding += f"Result: {result.output[:500]}...\n"
                else:
                    finding += f"Error: {result.error[:200]}\n"
                
                findings.append(finding)
                
                # Update prompt with result
                exploration_prompt += f"\n\n**Exploration {i+1}**:\n"
                exploration_prompt += f"Reasoning: {reasoning}\n"
                exploration_prompt += f"Tool: {tool_name}\n"
                exploration_prompt += f"Result: {result.output[:300] if result.success else result.error[:200]}\n"
                exploration_prompt += "\nNext exploration or done:"
                
            except Exception as e:
                logger.error(f"[Planner] Exploration error: {e}")
                break
        
        # Format findings
        exploration_report = "**Environment Exploration Findings**:\n\n"
        exploration_report += "\n".join(findings)
        
        return exploration_report
    
    def generate_plan(self, query: str, similar_tasks_text: str = "", exploration_findings: str = "") -> ExecutionPlan:
        """
        Generate execution plan with exploration findings
        
        Args:
            query: User query
            similar_tasks_text: Similar historical task text (optional)
            exploration_findings: Findings from read-only exploration (optional)
            
        Returns:
            ExecutionPlan object
        """
        # Prompt: Request Agent to generate structured plan
        similar_context = ""
        if similar_tasks_text:
            similar_context = f"\n**Similar Historical Tasks**:\n{similar_tasks_text}\n"
        
        exploration_context = ""
        if exploration_findings:
            exploration_context = f"\n{exploration_findings}\n"
        
        prompt = f"""You are a strategic task planner. Your job is to provide HIGH-LEVEL guidance and tool recommendations based on actual environment exploration.

TASK: {query}
{similar_context}
{exploration_context}

PLANNING PHILOSOPHY:
- Provide strategic guidance, NOT step-by-step instructions
- Recommend useful tools, but let ReAct decide when/how to use them
- Learn from skills and historical experiences
- Focus on WHAT to achieve, not HOW to do it
- Every step will be executed by ReAct with full decision-making power

OUTPUT FORMAT (JSON):
```json
{{
  "working_directory": "/path/to/work/dir",
  "recommended_tools": [
    {{
      "tool": "tool_name",
      "reason": "Why this tool might be useful",
      "typical_use": "Common usage pattern"
    }}
  ],
  "step_guidance": [
    {{
      "goal": "What to achieve",
      "success_criteria": "How to know it's done",
      "considerations": ["Thing to consider 1", "Thing to consider 2"],
      "backup_strategy": "What to try if primary approach fails"
    }}
  ],
  "overall_goal": "Final success criteria for the entire task",
  "lessons_learned": ["Lesson from skills/history 1", "Lesson 2"],
  "risks": ["potential risk 1", "potential risk 2"]
}}
```

AVAILABLE TOOLS:
{', '.join([t.name for t in self.readonly_tools])}

GUIDELINES:
1. **NO DETAILED STEPS**: Do NOT specify exact tools and parameters for each step
2. **RECOMMEND, DON'T PRESCRIBE**: Suggest useful tools, but ReAct will decide
3. **STRATEGIC GUIDANCE**: Focus on goals, success criteria, and considerations
4. **LEARN FROM EXPERIENCE**: Include lessons from skills and historical data
5. **BACKUP STRATEGIES**: Provide alternatives for common failure scenarios
6. **TRUST ReAct**: Every step will be executed by ReAct with full autonomy

EXAMPLES OF GOOD PLANS:

Example 1: "Analyze TODO comments in src/clis/agent/"
```json
{{
  "working_directory": ".",
  "recommended_tools": [
    {{
      "tool": "grep",
      "reason": "Efficiently search for TODO patterns in source files",
      "typical_use": "grep with pattern='TODO', context_lines for surrounding code"
    }},
    {{
      "tool": "read_file",
      "reason": "Read specific files if detailed analysis needed",
      "typical_use": "Read files identified by grep for deeper inspection"
    }},
    {{
      "tool": "write_file",
      "reason": "Create analysis script if complex processing needed",
      "typical_use": "Write Python script for categorization, then execute it"
    }}
  ],
  "step_guidance": [
    {{
      "goal": "Find all TODO comments in the target directory",
      "success_criteria": "Have a list of TODO comments with file locations and context",
      "considerations": [
        "Python files use # for comments",
        "May need to search recursively",
        "Context lines help understand priority"
      ],
      "backup_strategy": "If grep fails, try list_files + read_file for each"
    }},
    {{
      "goal": "Categorize TODOs by priority",
      "success_criteria": "Each TODO has a priority label (HIGH/MEDIUM/LOW/UNKNOWN)",
      "considerations": [
        "Look for keywords: urgent, critical, fix, bug (HIGH)",
        "Look for: should, consider, improve (MEDIUM)",
        "Default to LOW or UNKNOWN if no keywords",
        "Avoid complex inline Python scripts"
      ],
      "backup_strategy": "If automated categorization fails, present raw TODOs with context"
    }},
    {{
      "goal": "Display top 3 highest priority TODOs",
      "success_criteria": "Show 3 TODOs with file:line, priority, and description",
      "considerations": [
        "Sort by priority (HIGH > MEDIUM > LOW)",
        "If fewer than 3, show all available",
        "Format should be clear and actionable"
      ],
      "backup_strategy": "If sorting fails, show first 3 found"
    }}
  ],
  "overall_goal": "Display top 3 TODO comments from src/clis/agent/ categorized by priority",
  "lessons_learned": [
    "Avoid complex Python inline scripts in execute_command",
    "Create temporary files for complex processing",
    "Simple grep + text processing often works better than complex scripts"
  ],
  "risks": ["No TODO comments found", "Priority keywords may be ambiguous", "File encoding issues"]
}}
```

Example 2: "Create Flask app"
```json
{{
  "working_directory": "/tmp/flask_app",
  "recommended_tools": [
    {{
      "tool": "execute_command",
      "reason": "Create directories and run git commands",
      "typical_use": "mkdir -p, git init, git add, git commit"
    }},
    {{
      "tool": "write_file",
      "reason": "Create application files with content",
      "typical_use": "Write app.py, requirements.txt, README.md"
    }},
    {{
      "tool": "file_tree",
      "reason": "Verify directory structure",
      "typical_use": "Check created files and structure"
    }}
  ],
  "step_guidance": [
    {{
      "goal": "Set up project directory structure",
      "success_criteria": "Directory exists and is accessible",
      "considerations": [
        "Check if directory already exists",
        "Ensure write permissions",
        "Use absolute path to avoid confusion"
      ],
      "backup_strategy": "If mkdir fails, try different directory or check permissions"
    }},
    {{
      "goal": "Create Flask application files",
      "success_criteria": "app.py, requirements.txt, README.md exist with proper content",
      "considerations": [
        "app.py should have basic Flask structure",
        "requirements.txt should list Flask and dependencies",
        "README.md should explain how to run",
        "Use write_file for each file"
      ],
      "backup_strategy": "If write fails, check disk space and permissions"
    }},
    {{
      "goal": "Initialize git repository",
      "success_criteria": "Git repo initialized with initial commit",
      "considerations": [
        "Check if git is available",
        "Add all files before committing",
        "Use meaningful commit message"
      ],
      "backup_strategy": "Skip git if not available or not needed"
    }}
  ],
  "overall_goal": "Working Flask application in /tmp/flask_app with git initialized",
  "lessons_learned": [
    "Always check if tools (like git) are available before using",
    "Create files before trying to commit them",
    "Use simple commands instead of complex scripts"
  ],
  "risks": ["Directory already exists", "Permission issues", "Git not installed", "Disk space"]
}}
```

Generate a STRATEGIC plan (tool recommendations + high-level guidance):
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
        Parse LLM plan response (supports both adaptive and legacy formats)
        
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
                
                # Check if this is strategic format (newest)
                if 'recommended_tools' in data or 'step_guidance' in data:
                    # Parse recommended tools
                    for tool_data in data.get('recommended_tools', []):
                        tool_rec = ToolRecommendation(
                            tool=tool_data['tool'],
                            reason=tool_data['reason'],
                            typical_use=tool_data['typical_use']
                        )
                        plan.recommended_tools.append(tool_rec)
                    
                    # Parse step guidance
                    for guidance_data in data.get('step_guidance', []):
                        guidance = StepGuidance(
                            goal=guidance_data['goal'],
                            success_criteria=guidance_data['success_criteria'],
                            considerations=guidance_data.get('considerations', []),
                            backup_strategy=guidance_data.get('backup_strategy')
                        )
                        plan.step_guidance.append(guidance)
                    
                    # Set other fields
                    plan.overall_goal = data.get('overall_goal')
                    plan.lessons_learned = data.get('lessons_learned', [])
                    plan.total_steps = len(plan.step_guidance)
                    
                    logger.info(f"Parsed strategic plan: {len(plan.recommended_tools)} tools, {len(plan.step_guidance)} guidance steps")
                
                # Check if this is adaptive format (old new)
                elif 'first_step' in data:
                    # Parse first step
                    first_step_data = data['first_step']
                    plan.first_step = PlanStep(
                        id=1,
                        description=first_step_data['description'],
                        tool=first_step_data['tool'],
                        params=first_step_data['params'],
                        verify_with=first_step_data.get('expected_output'),
                        estimated_risk=first_step_data.get('estimated_risk', 'low')
                    )
                    
                    # Parse next steps guidance
                    for guidance_data in data.get('next_steps_guidance', []):
                        guidance = NextStepGuidance(
                            goal=guidance_data['goal'],
                            success_criteria=guidance_data['success_criteria'],
                            backup_strategy=guidance_data.get('backup_strategy')
                        )
                        plan.next_steps_guidance.append(guidance)
                    
                    # Set overall goal
                    plan.overall_goal = data.get('overall_goal')
                    
                    # For compatibility, also set total_steps
                    plan.total_steps = 1 + len(plan.next_steps_guidance)
                    
                    logger.info(f"Parsed adaptive plan: 1 detailed step + {len(plan.next_steps_guidance)} guidance steps")
                
                # Legacy format (backward compatibility)
                elif 'steps' in data:
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
                    logger.info(f"Parsed legacy plan: {plan.total_steps} detailed steps")
                
                else:
                    raise ValueError("Plan has neither 'first_step' nor 'steps'")
                
                # Validate plan has at least one step
                if plan.total_steps == 0:
                    logger.error("Plan has no steps, using fallback")
                    raise ValueError("Empty plan generated")
                
                return plan
            
            except Exception as e:
                logger.error(f"Failed to parse plan JSON: {e}")
                import traceback
                traceback.print_exc()
        
        # Fallback: create simple strategic plan
        logger.warning("Could not parse plan, creating simple fallback plan")
        return ExecutionPlan(
            query=query,
            working_directory=os.getcwd(),
            recommended_tools=[],
            step_guidance=[
                StepGuidance(
                    goal="Complete the task",
                    success_criteria="Task requirements met",
                    considerations=["Planning failed, use best judgment"],
                    backup_strategy="Ask for clarification if unclear"
                )
            ],
            overall_goal=query,
            lessons_learned=["Planning failed, proceeding with ReAct"],
            total_steps=1,
            risks=["Planning failed, may need manual guidance"]
        )
