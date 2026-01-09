"""
Skill router for CLIS - scans and loads skills.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

from clis.skills.parser import Skill, SkillParser
from clis.skills.validator import SkillValidator
from clis.utils.logger import get_logger
from clis.utils.platform import ensure_dir, get_cache_dir, get_skills_dir

logger = get_logger(__name__)


class SkillRouter:
    """Router for managing and loading skills."""

    def __init__(self, skills_dir: Optional[Path] = None):
        """
        Initialize skill router.
        
        Args:
            skills_dir: Skills directory (default: ~/.clis/skills)
        """
        self.skills_dir = skills_dir or get_skills_dir()
        self.parser = SkillParser()
        self.validator = SkillValidator()
        self.skills: Dict[str, Skill] = {}
        self.cache_file = get_cache_dir() / "skill_index.json"

    def scan_skills(self, force_refresh: bool = False) -> List[Skill]:
        """
        Scan and load all skills.
        
        Args:
            force_refresh: Force refresh cache
            
        Returns:
            List of loaded skills
        """
        # Try to load from cache first
        if not force_refresh and self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
                    
                # Check if cache is still valid
                if self._is_cache_valid(cache_data):
                    logger.debug("Loading skills from cache")
                    return self._load_from_cache(cache_data)
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")
        
        # Scan directories
        logger.info("Scanning skills...")
        skills = []
        
        # Scan built-in skills (from package)
        builtin_dir = Path(__file__).parent.parent.parent.parent / "skills"
        if builtin_dir.exists():
            skills.extend(self._scan_directory(builtin_dir))
        
        # Scan user skills
        if self.skills_dir.exists():
            skills.extend(self._scan_directory(self.skills_dir))
        
        # Validate and store skills
        for skill in skills:
            is_valid, errors = self.validator.validate(skill)
            if is_valid:
                self.skills[skill.name] = skill
            else:
                logger.warning(f"Invalid skill '{skill.name}': {errors}")
        
        # Save to cache
        self._save_cache()
        
        logger.info(f"Loaded {len(self.skills)} skills")
        return list(self.skills.values())

    def get_skill(self, name: str) -> Optional[Skill]:
        """
        Get a skill by name.
        
        Args:
            name: Skill name
            
        Returns:
            Skill object or None
        """
        if not self.skills:
            self.scan_skills()
        
        return self.skills.get(name)

    def list_skills(self) -> List[Skill]:
        """
        List all available skills.
        
        Returns:
            List of skills
        """
        if not self.skills:
            self.scan_skills()
        
        return list(self.skills.values())

    def _scan_directory(self, directory: Path) -> List[Skill]:
        """
        Scan a directory for skill files.
        
        Args:
            directory: Directory to scan
            
        Returns:
            List of skills found
        """
        skills = []
        
        for file_path in directory.rglob("*.md"):
            try:
                skill = self.parser.parse_file(file_path)
                skills.append(skill)
                logger.debug(f"Found skill: {skill.name} at {file_path}")
            except Exception as e:
                logger.error(f"Failed to parse {file_path}: {e}")
        
        return skills

    def _is_cache_valid(self, cache_data: Dict) -> bool:
        """
        Check if cache is still valid.
        
        Args:
            cache_data: Cache data
            
        Returns:
            True if cache is valid
        """
        # Simple validation: check if all files still exist
        for skill_data in cache_data.get("skills", []):
            file_path = Path(skill_data.get("file_path", ""))
            if not file_path.exists():
                return False
        
        return True

    def _load_from_cache(self, cache_data: Dict) -> List[Skill]:
        """
        Load skills from cache.
        
        Args:
            cache_data: Cache data
            
        Returns:
            List of skills
        """
        skills = []
        
        for skill_data in cache_data.get("skills", []):
            file_path = Path(skill_data["file_path"])
            try:
                skill = self.parser.parse_file(file_path)
                skills.append(skill)
                self.skills[skill.name] = skill
            except Exception as e:
                logger.error(f"Failed to load cached skill from {file_path}: {e}")
        
        return skills

    def _save_cache(self) -> None:
        """Save skills index to cache."""
        ensure_dir(self.cache_file.parent)
        
        cache_data = {
            "skills": [
                {
                    "name": skill.name,
                    "file_path": str(skill.file_path),
                    "description": skill.description,
                }
                for skill in self.skills.values()
            ]
        }
        
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Saved skill cache to {self.cache_file}")
