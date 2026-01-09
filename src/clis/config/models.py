"""
Pydantic models for CLIS configuration.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class PathsConfig(BaseModel):
    """Paths configuration."""

    skills_dir: str = Field(default="~/.clis/skills", description="Skills directory")
    cache_dir: str = Field(default="~/.clis/cache", description="Cache directory")
    log_dir: str = Field(default="~/.clis/logs", description="Log directory")


class OutputConfig(BaseModel):
    """Output configuration."""

    level: Literal["minimal", "normal", "verbose", "debug"] = Field(
        default="normal", description="Output level"
    )
    use_rich: bool = Field(default=True, description="Use Rich formatting")
    show_timing: bool = Field(default=True, description="Show execution time")
    show_tokens: bool = Field(default=True, description="Show token usage")


class EditorConfig(BaseModel):
    """Editor configuration."""

    preferred: str = Field(default="auto", description="Preferred editor")
    fallback: List[str] = Field(
        default_factory=lambda: ["code", "subl", "nano", "vim", "vi"],
        description="Fallback editors",
    )


class BaseConfig(BaseModel):
    """Base configuration (base.yaml)."""

    paths: PathsConfig = Field(default_factory=PathsConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    editor: EditorConfig = Field(default_factory=EditorConfig)
    language: str = Field(default="zh-CN", description="Language")


class APIConfig(BaseModel):
    """API configuration."""

    key: Optional[str] = Field(default=None, description="API key")
    base_url: str = Field(default="", description="API base URL")
    timeout: int = Field(default=30, description="Request timeout in seconds")


class ModelConfig(BaseModel):
    """Model configuration."""

    name: str = Field(default="", description="Model name")
    temperature: float = Field(default=0.1, description="Temperature")
    max_tokens: int = Field(default=2000, description="Max tokens")


class RetryConfig(BaseModel):
    """Retry configuration."""

    enabled: bool = Field(default=True, description="Enable retry")
    max_attempts: int = Field(default=3, description="Max retry attempts")
    delay: int = Field(default=1, description="Delay between retries in seconds")


class CostConfig(BaseModel):
    """Cost tracking configuration."""

    enabled: bool = Field(default=True, description="Enable cost tracking")
    daily_threshold: float = Field(default=10.0, description="Daily cost threshold in CNY")


class LLMConfig(BaseModel):
    """LLM configuration (llm.yaml)."""

    provider: Literal["openai", "anthropic", "deepseek", "qwen", "ollama"] = Field(
        default="deepseek", description="LLM provider"
    )
    api: APIConfig = Field(default_factory=APIConfig)
    model: ModelConfig = Field(default_factory=ModelConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    cost: CostConfig = Field(default_factory=CostConfig)


class BlacklistConfig(BaseModel):
    """Blacklist configuration."""

    enabled: bool = Field(default=True, description="Enable blacklist checking")
    patterns: List[str] = Field(default_factory=list, description="Dangerous command patterns")
    custom: List[str] = Field(default_factory=list, description="Custom blacklist patterns")


class DryRunConfig(BaseModel):
    """Dry-run configuration."""

    enabled: bool = Field(default=True, description="Enable dry-run by default")
    force_for: List[str] = Field(
        default_factory=lambda: ["delete", "modify", "system", "network"],
        description="Force dry-run for these operation types",
    )
    auto_approve_readonly: bool = Field(
        default=False, description="Auto-approve read-only operations"
    )


class SudoConfig(BaseModel):
    """Sudo configuration."""

    allowed: bool = Field(default=False, description="Allow sudo commands")
    require_skill_permission: bool = Field(
        default=True, description="Require explicit skill permission"
    )
    always_confirm: bool = Field(default=True, description="Always confirm sudo commands")


class RiskThresholdsConfig(BaseModel):
    """Risk thresholds configuration."""

    low: int = Field(default=30, description="Low risk threshold")
    medium: int = Field(default=60, description="Medium risk threshold")
    high: int = Field(default=90, description="High risk threshold")
    critical: int = Field(default=100, description="Critical risk threshold")


class RiskActionsConfig(BaseModel):
    """Risk actions configuration."""

    low: str = Field(default="execute", description="Action for low risk")
    medium: str = Field(default="confirm", description="Action for medium risk")
    high: str = Field(default="dry_run", description="Action for high risk")
    critical: str = Field(default="block", description="Action for critical risk")


class RiskConfig(BaseModel):
    """Risk scoring configuration."""

    enabled: bool = Field(default=True, description="Enable risk scoring")
    thresholds: RiskThresholdsConfig = Field(default_factory=RiskThresholdsConfig)
    actions: RiskActionsConfig = Field(default_factory=RiskActionsConfig)


class ConfirmationConfig(BaseModel):
    """Confirmation configuration."""

    timeout: int = Field(default=60, description="Confirmation timeout in seconds")
    default_on_timeout: Literal["reject", "accept"] = Field(
        default="reject", description="Default action on timeout"
    )
    show_risk_score: bool = Field(default=True, description="Show risk score in confirmation")


class LoggingConfig(BaseModel):
    """Logging configuration."""

    log_commands: bool = Field(default=True, description="Log executed commands")
    log_blocked: bool = Field(default=True, description="Log blocked commands")
    include_timestamp: bool = Field(default=True, description="Include timestamps")
    include_risk_score: bool = Field(default=True, description="Include risk scores")


class SafetyConfig(BaseModel):
    """Safety configuration (safety.yaml)."""

    blacklist: BlacklistConfig = Field(default_factory=BlacklistConfig)
    dry_run: DryRunConfig = Field(default_factory=DryRunConfig)
    sudo: SudoConfig = Field(default_factory=SudoConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    confirmation: ConfirmationConfig = Field(default_factory=ConfirmationConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
