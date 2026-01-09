"""
Skill validator for CLIS.
"""

from typing import List, Tuple

from clis.skills.parser import Skill
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class SkillValidator:
    """Validator for Skill objects."""

    def validate(self, skill: Skill) -> Tuple[bool, List[str]]:
        """
        Validate a skill.
        
        Args:
            skill: Skill to validate
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        # Check required fields
        if not skill.name:
            errors.append("Skill name is required")
        
        if not skill.description:
            errors.append("Description is required")
        
        if not skill.instructions:
            errors.append("Instructions are required")
        
        # Validate safety rules format
        for rule in skill.safety_rules:
            if not rule.strip():
                errors.append("Empty safety rule found")
        
        # Validate platform compatibility
        valid_platforms = ["windows", "macos", "linux", "macos/linux"]
        for platform in skill.platform_compatibility.keys():
            if platform not in valid_platforms:
                errors.append(f"Invalid platform: {platform}")
        
        is_valid = len(errors) == 0
        
        if is_valid:
            logger.debug(f"Skill '{skill.name}' is valid")
        else:
            logger.warning(f"Skill '{skill.name}' has {len(errors)} validation errors")
        
        return is_valid, errors
