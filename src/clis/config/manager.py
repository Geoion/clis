"""
Configuration manager for CLIS.
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from clis.config.models import BaseConfig, LLMConfig, SafetyConfig
from clis.utils.logger import get_logger
from clis.utils.platform import ensure_dir, get_config_dir, normalize_path

logger = get_logger(__name__)


class ConfigManager:
    """Manages CLIS configuration files."""

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_dir: Configuration directory (default: ~/.clis/config)
        """
        self.config_dir = config_dir or get_config_dir()
        self.base_config_path = self.config_dir / "base.yaml"
        self.llm_config_path = self.config_dir / "llm.yaml"
        self.safety_config_path = self.config_dir / "safety.yaml"
        
        self._base_config: Optional[BaseConfig] = None
        self._llm_config: Optional[LLMConfig] = None
        self._safety_config: Optional[SafetyConfig] = None

    def config_exists(self) -> bool:
        """
        Check if configuration files exist.
        
        Returns:
            True if all config files exist
        """
        return (
            self.base_config_path.exists()
            and self.llm_config_path.exists()
            and self.safety_config_path.exists()
        )

    def load_base_config(self) -> BaseConfig:
        """
        Load base configuration.
        
        Returns:
            Base configuration object
        """
        if self._base_config is None:
            if not self.base_config_path.exists():
                logger.warning("Base config not found, using defaults")
                self._base_config = BaseConfig()
            else:
                data = self._load_yaml(self.base_config_path)
                # Normalize paths
                if "paths" in data:
                    for key, value in data["paths"].items():
                        data["paths"][key] = normalize_path(value)
                self._base_config = BaseConfig(**data)
        return self._base_config

    def load_llm_config(self) -> LLMConfig:
        """
        Load LLM configuration.
        
        Returns:
            LLM configuration object
        """
        if self._llm_config is None:
            if not self.llm_config_path.exists():
                logger.warning("LLM config not found, using defaults")
                self._llm_config = LLMConfig()
            else:
                data = self._load_yaml(self.llm_config_path)
                # Expand environment variables in API key
                if "api" in data and "key" in data["api"]:
                    data["api"]["key"] = self._expand_env_vars(data["api"]["key"])
                self._llm_config = LLMConfig(**data)
        return self._llm_config

    def load_safety_config(self) -> SafetyConfig:
        """
        Load safety configuration.
        
        Returns:
            Safety configuration object
        """
        if self._safety_config is None:
            if not self.safety_config_path.exists():
                logger.warning("Safety config not found, using defaults")
                self._safety_config = SafetyConfig()
            else:
                data = self._load_yaml(self.safety_config_path)
                self._safety_config = SafetyConfig(**data)
        return self._safety_config

    def save_base_config(self, config: BaseConfig) -> None:
        """
        Save base configuration.
        
        Args:
            config: Base configuration object
        """
        ensure_dir(self.config_dir)
        self._save_yaml(self.base_config_path, config.model_dump())
        self._base_config = config
        logger.info(f"Saved base config to {self.base_config_path}")

    def save_llm_config(self, config: LLMConfig) -> None:
        """
        Save LLM configuration.
        
        Args:
            config: LLM configuration object
        """
        ensure_dir(self.config_dir)
        self._save_yaml(self.llm_config_path, config.model_dump())
        self._llm_config = config
        logger.info(f"Saved LLM config to {self.llm_config_path}")

    def save_safety_config(self, config: SafetyConfig) -> None:
        """
        Save safety configuration.
        
        Args:
            config: Safety configuration object
        """
        ensure_dir(self.config_dir)
        self._save_yaml(self.safety_config_path, config.model_dump())
        self._safety_config = config
        logger.info(f"Saved safety config to {self.safety_config_path}")

    def create_default_configs(self) -> None:
        """Create default configuration files from templates."""
        ensure_dir(self.config_dir)
        
        # Get template directory
        template_dir = Path(__file__).parent / "templates"
        
        # Copy templates
        for template_name in ["base.yaml", "llm.yaml", "safety.yaml"]:
            template_path = template_dir / template_name
            target_path = self.config_dir / template_name
            
            if not target_path.exists():
                with open(template_path, "r", encoding="utf-8") as f:
                    content = f.read()
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(content)
                logger.info(f"Created config file: {target_path}")

    def get_config_value(self, key: str) -> Any:
        """
        Get a configuration value by dot-notation key.
        
        Args:
            key: Configuration key (e.g., "output.level", "llm.provider")
            
        Returns:
            Configuration value
        """
        parts = key.split(".")
        
        # Determine which config to load
        if parts[0] == "paths" or parts[0] == "output" or parts[0] == "editor":
            config = self.load_base_config()
        elif parts[0] == "llm" or parts[0] == "provider" or parts[0] == "api" or parts[0] == "model":
            config = self.load_llm_config()
        else:
            config = self.load_safety_config()
        
        # Navigate to the value
        value: Any = config
        for part in parts:
            if hasattr(value, part):
                value = getattr(value, part)
            else:
                raise KeyError(f"Configuration key not found: {key}")
        
        return value

    def set_config_value(self, key: str, value: Any) -> None:
        """
        Set a configuration value by dot-notation key.
        
        Args:
            key: Configuration key (e.g., "output.level", "llm.provider")
            value: New value
        """
        parts = key.split(".")
        
        # Determine which config to modify
        if parts[0] == "paths" or parts[0] == "output" or parts[0] == "editor":
            config = self.load_base_config()
            save_func = self.save_base_config
        elif parts[0] == "llm" or parts[0] == "provider" or parts[0] == "api" or parts[0] == "model":
            config = self.load_llm_config()
            save_func = self.save_llm_config
        else:
            config = self.load_safety_config()
            save_func = self.save_safety_config
        
        # Navigate to the parent and set the value
        obj: Any = config
        for part in parts[:-1]:
            obj = getattr(obj, part)
        
        setattr(obj, parts[-1], value)
        save_func(config)

    def _load_yaml(self, path: Path) -> Dict[str, Any]:
        """Load YAML file."""
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _save_yaml(self, path: Path, data: Dict[str, Any]) -> None:
        """Save YAML file."""
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    def _expand_env_vars(self, value: Optional[str]) -> Optional[str]:
        """
        Expand environment variables in a string.
        
        Args:
            value: String that may contain ${VAR_NAME} patterns
            
        Returns:
            String with environment variables expanded
        """
        if value is None:
            return None
        
        # Pattern: ${VAR_NAME}
        pattern = r"\$\{([^}]+)\}"
        
        def replace_var(match: re.Match[str]) -> str:
            var_name = match.group(1)
            return os.environ.get(var_name, match.group(0))
        
        return re.sub(pattern, replace_var, value)
