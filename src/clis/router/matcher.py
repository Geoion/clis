"""
Skill matcher for CLIS - uses LLM to match user intent to skills.
"""

from typing import List, Optional, Tuple

from clis.agent import Agent
from clis.skills.parser import Skill
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class SkillMatcher:
    """Matcher for finding the best skill for user intent."""

    def __init__(self, agent: Agent):
        """
        Initialize skill matcher.
        
        Args:
            agent: Agent instance for LLM calls
        """
        self.agent = agent

    def match(self, user_input: str, skills: List[Skill]) -> Optional[Tuple[Skill, float]]:
        """
        Match user input to the best skill.
        
        Args:
            user_input: User's natural language input
            skills: List of available skills
            
        Returns:
            Tuple of (matched_skill, confidence) or None if no match
        """
        if not skills:
            logger.warning("No skills available for matching")
            return None
        
        # Build skill list for prompt
        skill_list = []
        for i, skill in enumerate(skills, 1):
            skill_list.append(f"{i}. {skill.name} - {skill.description}")
        
        skills_text = "\n".join(skill_list)
        
        # Build prompt
        system_prompt = f"""
You are a skill router for CLIS. Your task is to match user input to the most appropriate skill.

Available skills:
{skills_text}

Analyze the user's intent and select the best matching skill.
Return your response in JSON format:
{{
    "skill_name": "Name of the matched skill",
    "confidence": 0.95,
    "reasoning": "Brief explanation of why this skill matches"
}}

If no skill matches well (confidence < 0.7), return:
{{
    "skill_name": null,
    "confidence": 0.0,
    "reasoning": "No suitable skill found"
}}
"""
        
        prompt = f"User input: {user_input}"
        
        try:
            response = self.agent.generate_json(prompt, system_prompt, inject_context=False)
            
            skill_name = response.get("skill_name")
            confidence = float(response.get("confidence", 0.0))
            reasoning = response.get("reasoning", "")
            
            logger.info(f"Skill matching result: {skill_name} (confidence: {confidence})")
            logger.debug(f"Reasoning: {reasoning}")
            
            if skill_name is None or confidence < 0.7:
                logger.info("No suitable skill found")
                return None
            
            # Find the skill by name
            for skill in skills:
                if skill.name.lower() == skill_name.lower():
                    return (skill, confidence)
            
            logger.warning(f"Matched skill '{skill_name}' not found in skill list")
            return None
        
        except Exception as e:
            logger.error(f"Skill matching failed: {e}")
            return None
