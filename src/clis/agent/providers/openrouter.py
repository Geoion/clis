"""
OpenRouter LLM provider implementation.
"""

from typing import Generator, Optional

from openai import OpenAI

from clis.agent.providers.base import LLMProvider
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class OpenRouterProvider(LLMProvider):
    """OpenRouter LLM provider using OpenAI-compatible API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://openrouter.ai/api/v1",
        model: str = "anthropic/claude-3.5-sonnet",
        temperature: float = 0.1,
        max_tokens: int = 2000,
        timeout: int = 30,
    ):
        """
        Initialize OpenRouter provider.
        
        Args:
            api_key: OpenRouter API key
            base_url: API base URL
            model: Model name (e.g., anthropic/claude-3.5-sonnet, openai/gpt-4o, etc.)
            temperature: Temperature for generation
            max_tokens: Maximum tokens in response
            timeout: Request timeout in seconds
        """
        super().__init__(api_key, base_url, model, temperature, max_tokens, timeout)
        
        if not api_key:
            raise ValueError("OpenRouter API key is required")
        
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        max_reasoning_tokens: Optional[int] = None,
    ) -> str:
        """
        Generate text from prompt using OpenRouter.
        
        Args:
            prompt: User prompt
            system_prompt: System prompt
            temperature: Temperature override
            max_tokens: Max tokens override
            max_reasoning_tokens: Not used (for compatibility)
            
        Returns:
            Generated text
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        temp = temperature if temperature is not None else self.temperature
        max_tok = max_tokens if max_tokens is not None else self.max_tokens
        
        logger.debug(f"Calling OpenRouter API with model {self.model}")
        logger.debug(f"Temperature: {temp}, Max tokens: {max_tok}")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temp,
                max_tokens=max_tok,
            )
            
            content = response.choices[0].message.content or ""
            
            # Log token usage
            if response.usage:
                usage_msg = (
                    f"Token usage - Input: {response.usage.prompt_tokens}, "
                    f"Output: {response.usage.completion_tokens}, "
                    f"Total: {response.usage.total_tokens}"
                )
                logger.info(usage_msg)
            
            return content
        
        except Exception as e:
            logger.error(f"OpenRouter API error: {e}")
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
        Generate text from prompt using OpenRouter with streaming.
        
        Args:
            prompt: User prompt
            system_prompt: System prompt
            temperature: Temperature override
            max_tokens: Max tokens override
            max_reasoning_tokens: Not used (for compatibility)
            
        Yields:
            Text chunks as they are generated
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        temp = temperature if temperature is not None else self.temperature
        max_tok = max_tokens if max_tokens is not None else self.max_tokens
        
        logger.debug(f"Calling OpenRouter API (streaming) with model {self.model}")
        logger.debug(f"Temperature: {temp}, Max tokens: {max_tok}")
        
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temp,
                max_tokens=max_tok,
                stream=True,
            )
            
            # Track tokens for logging
            total_tokens = 0
            
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    total_tokens += len(content.split())
                    yield content
            
            logger.info(f"Streaming completed, approximate tokens: {total_tokens}")
        
        except Exception as e:
            logger.error(f"OpenRouter streaming API error: {e}")
            raise

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Estimate cost for OpenRouter API call.
        
        Note: OpenRouter pricing varies by model. This provides rough estimates.
        Check https://openrouter.ai/models for exact pricing.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Estimated cost in USD
        """
        model_lower = self.model.lower()
        
        # Rough estimates based on common models
        if "claude-3.5-sonnet" in model_lower or "claude-3-5-sonnet" in model_lower:
            input_cost = input_tokens / 1_000_000 * 3
            output_cost = output_tokens / 1_000_000 * 15
        elif "claude-3-opus" in model_lower:
            input_cost = input_tokens / 1_000_000 * 15
            output_cost = output_tokens / 1_000_000 * 75
        elif "gpt-4o" in model_lower:
            input_cost = input_tokens / 1_000_000 * 2.5
            output_cost = output_tokens / 1_000_000 * 10
        elif "gpt-4" in model_lower:
            input_cost = input_tokens / 1_000_000 * 10
            output_cost = output_tokens / 1_000_000 * 30
        elif "gpt-3.5" in model_lower:
            input_cost = input_tokens / 1_000_000 * 0.5
            output_cost = output_tokens / 1_000_000 * 1.5
        elif "gemini" in model_lower:
            input_cost = input_tokens / 1_000_000 * 0.5
            output_cost = output_tokens / 1_000_000 * 1.5
        else:
            # Default estimate
            input_cost = input_tokens / 1_000_000 * 1
            output_cost = output_tokens / 1_000_000 * 3
        
        return input_cost + output_cost
