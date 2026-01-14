"""
Pydantic models for CLIS configuration.
"""

from typing import List, Literal, Optional, Union

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


class ContextConfig(BaseModel):
    """Context window configuration for intelligent file chunking."""
    
    # Context window size in tokens (model-specific)
    window_size: int = Field(default=64000, description="Model context window size in tokens")
    
    # File chunking settings
    auto_chunk: bool = Field(default=True, description="Enable automatic file chunking based on context window")
    chunk_threshold: int = Field(
        default=0, 
        description="Manual chunk threshold in tokens (0 = auto based on window_size)"
    )
    chunk_overlap: int = Field(default=200, description="Overlap between chunks in lines")
    
    # Reserved tokens for system prompt and response
    reserved_tokens: int = Field(
        default=4000, 
        description="Tokens reserved for system prompt and model response"
    )
    
    @property
    def effective_threshold(self) -> int:
        """Calculate effective chunk threshold."""
        if self.chunk_threshold > 0:
            return self.chunk_threshold
        # Auto: use 60% of (window_size - reserved) for file content
        return int((self.window_size - self.reserved_tokens) * 0.6)


class ModelConfig(BaseModel):
    """Model configuration."""

    name: str = Field(default="", description="Model name")
    temperature: float = Field(default=0.1, description="Temperature")
    max_tokens: int = Field(default=2000, description="Max tokens")
    context: ContextConfig = Field(default_factory=ContextConfig, description="Context window settings")


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
    
    def get_chunk_threshold(self) -> int:
        """Get the effective chunk threshold for file reading."""
        return self.model.context.effective_threshold


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
    high: str = Field(default="confirm", description="Action for high risk")
    critical: str = Field(default="block", description="Action for critical risk")


class AutoApproveConfig(BaseModel):
    """Auto-approve configuration based on risk level."""
    
    enabled: bool = Field(default=False, description="Enable auto-approve")
    max_risk_level: Literal["low", "medium", "high"] = Field(
        default="low", 
        description="Maximum risk level to auto-approve (low/medium/high)"
    )
    readonly_only: bool = Field(
        default=True, 
        description="Only auto-approve read-only operations"
    )
    record_decisions: bool = Field(
        default=True,
        description="Record all auto-approve decisions"
    )


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
    record_rejections: bool = Field(
        default=True,
        description="Record rejected operations in context"
    )


class LoggingConfig(BaseModel):
    """Logging configuration."""

    log_commands: bool = Field(default=True, description="Log executed commands")
    log_blocked: bool = Field(default=True, description="Log blocked commands")
    include_timestamp: bool = Field(default=True, description="Include timestamps")
    include_risk_score: bool = Field(default=True, description="Include risk scores")


class ContextManagementConfig(BaseModel):
    """Context management configuration for intelligent history compression."""
    
    enabled: bool = Field(default=True, description="Enable intelligent context management")
    max_observations: int = Field(default=10, description="Maximum observations to keep")
    compression_threshold: int = Field(
        default=5,
        description="Compress observations when count exceeds this"
    )
    keep_critical: bool = Field(
        default=True,
        description="Always keep critical observations (errors, rejections)"
    )
    keep_recent: int = Field(
        default=3,
        description="Always keep N most recent observations"
    )


class AgentConfig(BaseModel):
    """Agent execution configuration."""
    
    max_iterations: Union[str, int] = Field(
        default="auto",
        description="Maximum iterations for ReAct agent ('auto' or integer)"
    )
    auto_iterations_base: int = Field(
        default=100,
        description="Safety limit for auto mode (prevents infinite loops)"
    )

class SafetyConfig(BaseModel):
    """Safety configuration (safety.yaml)."""

    blacklist: BlacklistConfig = Field(default_factory=BlacklistConfig)
    dry_run: DryRunConfig = Field(default_factory=DryRunConfig)
    sudo: SudoConfig = Field(default_factory=SudoConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    auto_approve: AutoApproveConfig = Field(default_factory=AutoApproveConfig)
    confirmation: ConfirmationConfig = Field(default_factory=ConfirmationConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    context_management: ContextManagementConfig = Field(default_factory=ContextManagementConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)

