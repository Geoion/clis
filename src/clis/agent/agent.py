"""
Agent core for CLIS - handles LLM interactions and prompt building.
"""

from typing import Any, Dict, Generator, Optional

from clis.agent.providers.base import LLMProvider
from clis.agent.providers.anthropic import AnthropicProvider
from clis.agent.providers.deepseek import DeepSeekProvider
from clis.agent.providers.ollama import OllamaProvider
from clis.agent.providers.openai import OpenAIProvider
from clis.agent.providers.openrouter import OpenRouterProvider
from clis.agent.providers.qwen import QwenProvider
from clis.config import ConfigManager
from clis.utils.logger import get_logger
from clis.utils.platform import get_platform, get_shell

logger = get_logger(__name__)


class Agent:
    """Agent for interacting with LLMs."""

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """
        Initialize agent.
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config_manager = config_manager or ConfigManager()
        self.provider: Optional[LLMProvider] = None
        self._load_provider()

    def _load_provider(self) -> None:
        """Load LLM provider based on configuration."""
        llm_config = self.config_manager.load_llm_config()
        
        provider_name = llm_config.provider
        api_key = llm_config.api.key
        base_url = llm_config.api.base_url
        model = llm_config.model.name
        temperature = llm_config.model.temperature
        max_tokens = llm_config.model.max_tokens
        timeout = llm_config.api.timeout
        
        logger.info(f"Loading LLM provider: {provider_name}")
        
        if provider_name == "deepseek":
            self.provider = DeepSeekProvider(
                api_key=api_key,
                base_url=base_url,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            )
        elif provider_name == "ollama":
            self.provider = OllamaProvider(
                base_url=base_url,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            )
        elif provider_name == "openai":
            self.provider = OpenAIProvider(
                api_key=api_key,
                base_url=base_url or "https://api.openai.com/v1",
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            )
        elif provider_name == "anthropic":
            self.provider = AnthropicProvider(
                api_key=api_key,
                base_url=base_url,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            )
        elif provider_name == "qwen":
            self.provider = QwenProvider(
                api_key=api_key,
                base_url=base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1",
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            )
        elif provider_name == "openrouter":
            self.provider = OpenRouterProvider(
                api_key=api_key,
                base_url=base_url or "https://openrouter.ai/api/v1",
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {provider_name}")

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        inject_context: bool = True,
        max_retries: int = 2
    ) -> str:
        """
        Generate text from prompt with retry on timeout.
        
        Args:
            prompt: User prompt
            system_prompt: System prompt
            inject_context: Whether to inject platform context
            max_retries: Maximum number of retries on timeout (default: 2)
            
        Returns:
            Generated text
        """
        if self.provider is None:
            raise RuntimeError("LLM provider not initialized")
        
        # Inject platform context if requested
        if inject_context and system_prompt:
            system_prompt = self._inject_context(system_prompt)
        
        # Retry logic for timeout errors
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                return self.provider.generate(prompt, system_prompt)
            except Exception as e:
                error_msg = str(e).lower()
                # Check if it's a timeout error
                if 'timeout' in error_msg or 'timed out' in error_msg:
                    last_error = e
                    if attempt < max_retries:
                        from clis.utils.logger import get_logger
                        logger = get_logger(__name__)
                        logger.warning(f"API timeout on attempt {attempt + 1}/{max_retries + 1}, retrying...")
                        continue
                # For non-timeout errors, raise immediately
                raise
        
        # All retries exhausted
        raise last_error if last_error else RuntimeError("Generation failed")

    def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        inject_context: bool = True,
    ) -> Generator[str, None, None]:
        """
        Generate text from prompt with streaming.
        
        Args:
            prompt: User prompt
            system_prompt: System prompt
            inject_context: Whether to inject platform context
            
        Yields:
            Text chunks as they are generated
        """
        if self.provider is None:
            raise RuntimeError("LLM provider not initialized")
        
        # Inject platform context if requested
        if inject_context and system_prompt:
            system_prompt = self._inject_context(system_prompt)
        
        yield from self.provider.generate_stream(prompt, system_prompt)

    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        inject_context: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate JSON response from prompt.
        
        Args:
            prompt: User prompt
            system_prompt: System prompt
            inject_context: Whether to inject platform context
            
        Returns:
            Parsed JSON dict
        """
        if self.provider is None:
            raise RuntimeError("LLM provider not initialized")
        
        # Add JSON format instruction to system prompt
        if system_prompt:
            system_prompt += "\n\nYou MUST respond with valid JSON format."
        else:
            system_prompt = "You MUST respond with valid JSON format."
        
        response = self.generate(prompt, system_prompt, inject_context)
        return self.provider.parse_json_response(response)

    def _inject_context(self, system_prompt: str) -> str:
        """
        Inject platform context into system prompt.
        
        Args:
            system_prompt: Original system prompt
            
        Returns:
            System prompt with injected context
        """
        platform = get_platform()
        shell = get_shell()
        
        # Platform-specific command examples
        platform_examples = {
            "windows": "Use PowerShell commands: Get-ChildItem, Get-Content, etc.",
            "macos": "Use Unix commands: ls, cat, grep, find, etc.",
            "linux": "Use Unix commands: ls, cat, grep, find, etc."
        }
        
        context = f"""
## Platform Context (CRITICAL)

**IMPORTANT**: You are running on {platform.upper()} with {shell} shell.

- Operating System: {platform}
- Shell: {shell}
- Command Style: {platform_examples.get(platform, "Unix commands")}

**CRITICAL RULES**:
- If platform is "macos" or "linux": Use ONLY Unix/bash commands (ls, grep, find, cat, etc.)
- If platform is "windows": Use ONLY PowerShell commands (Get-ChildItem, Get-Content, etc.)
- DO NOT mix Windows and Unix commands!
- All commands MUST be compatible with {platform} and {shell}

When generating commands, ensure they are 100% compatible with the above platform and shell.
"""
        
        return system_prompt + "\n\n" + context

    def estimate_cost(self, prompt: str, response: str) -> float:
        """
        Estimate cost for API call.
        
        Args:
            prompt: Input prompt
            response: Generated response
            
        Returns:
            Estimated cost in CNY
        """
        if self.provider is None:
            return 0.0
        
        input_tokens = self.provider.count_tokens(prompt)
        output_tokens = self.provider.count_tokens(response)
        
        return self.provider.estimate_cost(input_tokens, output_tokens)
