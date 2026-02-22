"""
Anthropic (Claude) LLM provider implementation.
"""

from typing import Generator, Optional

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

from clis.agent.providers.base import LLMProvider
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class AnthropicProvider(LLMProvider):
    """Anthropic (Claude) LLM provider."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "claude-3-5-sonnet-20241022",
        temperature: float = 0.1,
        max_tokens: int = 2000,
        timeout: int = 30,
    ):
        """
        Initialize Anthropic provider.
        
        Args:
            api_key: Anthropic API key
            base_url: API base URL (optional, for custom endpoints)
            model: Model name (claude-3-5-sonnet-20241022, claude-3-opus-20240229, etc.)
            temperature: Temperature for generation
            max_tokens: Maximum tokens in response
            timeout: Request timeout in seconds
        """
        super().__init__(api_key, base_url, model, temperature, max_tokens, timeout)
        
        if not ANTHROPIC_AVAILABLE:
            raise ImportError(
                "anthropic package is not installed. "
                "Install it with: pip install anthropic"
            )
        
        if not api_key:
            raise ValueError("Anthropic API key is required")
        
        client_kwargs = {
            "api_key": api_key,
            "timeout": timeout,
        }
        
        if base_url:
            client_kwargs["base_url"] = base_url
        
        self.client = Anthropic(**client_kwargs)

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        max_reasoning_tokens: Optional[int] = None,
    ) -> str:
        """
        Generate text from prompt using Anthropic Claude.
        
        Args:
            prompt: User prompt
            system_prompt: System prompt
            temperature: Temperature override
            max_tokens: Max tokens override
            max_reasoning_tokens: Not used (for compatibility)
            
        Returns:
            Generated text
        """
        temp = temperature if temperature is not None else self.temperature
        max_tok = max_tokens if max_tokens is not None else self.max_tokens
        
        logger.debug(f"Calling Anthropic API with model {self.model}")
        logger.debug(f"Temperature: {temp}, Max tokens: {max_tok}")
        
        try:
            # Build request parameters
            api_params = {
                "model": self.model,
                "max_tokens": max_tok,
                "temperature": temp,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
            }
            
            if system_prompt:
                api_params["system"] = system_prompt
            
            response = self.client.messages.create(**api_params)
            
            # Extract text content
            content = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    content += block.text
            
            # Log token usage
            if response.usage:
                usage_msg = (
                    f"Token usage - Input: {response.usage.input_tokens}, "
                    f"Output: {response.usage.output_tokens}"
                )
                logger.info(usage_msg)
            
            return content
        
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise

    def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        max_reasoning_tokens: Optional[int] = None,
    ) -> Generator[str, None, None]:
        """
        Generate text from prompt using Anthropic Claude with streaming.
        
        Args:
            prompt: User prompt
            system_prompt: System prompt
            temperature: Temperature override
            max_tokens: Max tokens override
            max_reasoning_tokens: Not used (for compatibility)
            
        Yields:
            Text chunks as they are generated
        """
        temp = temperature if temperature is not None else self.temperature
        max_tok = max_tokens if max_tokens is not None else self.max_tokens
        
        logger.debug(f"Calling Anthropic API (streaming) with model {self.model}")
        logger.debug(f"Temperature: {temp}, Max tokens: {max_tok}")
        
        try:
            api_params = {
                "model": self.model,
                "max_tokens": max_tok,
                "temperature": temp,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
            }
            
            if system_prompt:
                api_params["system"] = system_prompt
            
            with self.client.messages.stream(**api_params) as stream:
                for text in stream.text_stream:
                    yield text
            
            logger.info("Streaming completed")
        
        except Exception as e:
            logger.error(f"Anthropic streaming API error: {e}")
            raise

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Estimate cost for Anthropic API call.
        
        Claude pricing (as of 2024):
        - Claude 3.5 Sonnet: $3/MTok input, $15/MTok output
        - Claude 3 Opus: $15/MTok input, $75/MTok output
        - Claude 3 Haiku: $0.25/MTok input, $1.25/MTok output
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Estimated cost in USD
        """
        # Default to Sonnet pricing
        if "opus" in self.model.lower():
            input_cost = input_tokens / 1_000_000 * 15
            output_cost = output_tokens / 1_000_000 * 75
        elif "haiku" in self.model.lower():
            input_cost = input_tokens / 1_000_000 * 0.25
            output_cost = output_tokens / 1_000_000 * 1.25
        else:  # Sonnet or default
            input_cost = input_tokens / 1_000_000 * 3
            output_cost = output_tokens / 1_000_000 * 15
        
        return input_cost + output_cost
