"""
Skill parser for CLIS - parses Markdown skill files.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from markdown_it import MarkdownIt

from clis.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Skill:
    """Represents a parsed skill."""

    name: str
    file_path: Path
    description: str = ""
    instructions: str = ""
    input_schema: str = ""
    examples: str = ""
    safety_rules: List[str] = field(default_factory=list)
    platform_compatibility: Dict[str, str] = field(default_factory=dict)
    dry_run_mode: bool = False
    raw_content: str = ""

    def to_dict(self) -> Dict[str, any]:
        """Convert skill to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "instructions": self.instructions,
            "input_schema": self.input_schema,
            "examples": self.examples,
            "safety_rules": self.safety_rules,
            "platform_compatibility": self.platform_compatibility,
            "dry_run_mode": self.dry_run_mode,
        }


class SkillParser:
    """Parser for Skill Markdown files."""

    def __init__(self):
        """Initialize skill parser."""
        self.md = MarkdownIt()

    def parse_file(self, file_path: Path) -> Skill:
        """
        Parse a skill file.
        
        Args:
            file_path: Path to skill file
            
        Returns:
            Parsed Skill object
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Skill file not found: {file_path}")
        
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        return self.parse_content(content, file_path)

    def parse_content(self, content: str, file_path: Optional[Path] = None) -> Skill:
        """
        Parse skill content.
        
        Args:
            content: Markdown content
            file_path: Optional file path
            
        Returns:
            Parsed Skill object
        """
        # Extract skill name from first heading or filename
        name_match = re.search(r"^#\s+(?:Skill Name:\s+)?(.+)$", content, re.MULTILINE)
        if name_match:
            name = name_match.group(1).strip()
        elif file_path:
            name = file_path.stem
        else:
            name = "Unnamed Skill"
        
        skill = Skill(
            name=name,
            file_path=file_path or Path(""),
            raw_content=content,
        )
        
        # Parse sections
        skill.description = self._extract_section(content, "Description")
        skill.instructions = self._extract_section(content, "Instructions")
        skill.input_schema = self._extract_section(content, "Input Schema")
        skill.examples = self._extract_section(content, "Examples")
        
        # Parse CLIS extensions
        safety_rules_text = self._extract_section(content, "Safety Rules")
        if safety_rules_text:
            skill.safety_rules = self._parse_safety_rules(safety_rules_text)
        
        platform_compat_text = self._extract_section(content, "Platform Compatibility")
        if platform_compat_text:
            skill.platform_compatibility = self._parse_platform_compatibility(platform_compat_text)
        
        dry_run_text = self._extract_section(content, "Dry-Run Mode")
        if dry_run_text:
            skill.dry_run_mode = dry_run_text.strip().lower() in ["true", "yes", "1"]
        
        logger.debug(f"Parsed skill: {skill.name}")
        
        return skill

    def _extract_section(self, content: str, section_name: str) -> str:
        """
        Extract content of a section.
        
        Args:
            content: Full markdown content
            section_name: Section name to extract
            
        Returns:
            Section content
        """
        # Pattern: ## Section Name
        pattern = rf"^##\s+{re.escape(section_name)}(?:\s+\(.*?\))?\s*$"
        
        lines = content.split("\n")
        section_lines = []
        in_section = False
        
        for line in lines:
            if re.match(pattern, line, re.IGNORECASE):
                in_section = True
                continue
            
            if in_section:
                # Stop at next section (## or #)
                if re.match(r"^##?\s+", line):
                    break
                section_lines.append(line)
        
        return "\n".join(section_lines).strip()

    def _parse_safety_rules(self, text: str) -> List[str]:
        """
        Parse safety rules from text.
        
        Args:
            text: Safety rules text
            
        Returns:
            List of safety rules
        """
        rules = []
        
        # Pattern: - Rule: description
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("-"):
                rule = line[1:].strip()
                if rule:
                    rules.append(rule)
        
        return rules

    def _parse_platform_compatibility(self, text: str) -> Dict[str, str]:
        """
        Parse platform compatibility from text.
        
        Args:
            text: Platform compatibility text
            
        Returns:
            Dict mapping platform to instructions
        """
        compat = {}
        
        # Pattern: - Platform: instructions
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("-"):
                parts = line[1:].split(":", 1)
                if len(parts) == 2:
                    platform = parts[0].strip().lower()
                    instructions = parts[1].strip()
                    compat[platform] = instructions
        
        return compat
