"""
DeepSeek LLM provider implementation.
"""

from typing import Optional

from openai import OpenAI

from clis.agent.providers.base import LLMProvider
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class DeepSeekProvider(LLMProvider):
    """DeepSeek LLM provider using OpenAI-compatible API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.deepseek.com/v1",
        model: str = "deepseek-chat",
        temperature: float = 0.1,
        max_tokens: int = 2000,
        timeout: int = 30,
    ):
        """
        Initialize DeepSeek provider.
        
        Args:
            api_key: DeepSeek API key
            base_url: API base URL
            model: Model name (deepseek-chat, deepseek-coder)
            temperature: Temperature for generation
            max_tokens: Maximum tokens in response
            timeout: Request timeout in seconds
        """
        super().__init__(api_key, base_url, model, temperature, max_tokens, timeout)
        
        if not api_key:
            raise ValueError("DeepSeek API key is required")
        
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
    ) -> str:
        """
        Generate text from prompt using DeepSeek.
        
        Args:
            prompt: User prompt
            system_prompt: System prompt
            temperature: Temperature override
            max_tokens: Max tokens override
            
        Returns:
            Generated text
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        temp = temperature if temperature is not None else self.temperature
        max_tok = max_tokens if max_tokens is not None else self.max_tokens
        
        logger.debug(f"Calling DeepSeek API with model {self.model}")
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
                logger.info(
                    f"Token usage - Input: {response.usage.prompt_tokens}, "
                    f"Output: {response.usage.completion_tokens}, "
                    f"Total: {response.usage.total_tokens}"
                )
            
            return content
        
        except Exception as e:
            logger.error(f"DeepSeek API error: {e}")
            raise

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Estimate cost for DeepSeek API call.
        
        DeepSeek pricing (as of 2024):
        - Input: ¥0.001/1K tokens
        - Output: ¥0.002/1K tokens
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Estimated cost in CNY
        """
        input_cost = input_tokens / 1000 * 0.001
        output_cost = output_tokens / 1000 * 0.002
        return input_cost + output_cost
