"""
Qwen (通义千问) LLM provider implementation.
"""

from typing import Generator, Optional

from openai import OpenAI

from clis.agent.providers.base import LLMProvider
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class QwenProvider(LLMProvider):
    """Qwen (通义千问) LLM provider using OpenAI-compatible API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
        model: str = "qwen-max",
        temperature: float = 0.1,
        max_tokens: int = 2000,
        timeout: int = 30,
    ):
        """
        Initialize Qwen provider.
        
        Args:
            api_key: Qwen API key (DashScope API key)
            base_url: API base URL
            model: Model name (qwen-max, qwen-plus, qwen-turbo, qwen-long, etc.)
            temperature: Temperature for generation
            max_tokens: Maximum tokens in response
            timeout: Request timeout in seconds
        """
        super().__init__(api_key, base_url, model, temperature, max_tokens, timeout)
        
        if not api_key:
            raise ValueError("Qwen API key is required")
        
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
        Generate text from prompt using Qwen.
        
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
        
        logger.debug(f"Calling Qwen API with model {self.model}")
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
            logger.error(f"Qwen API error: {e}")
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
        Generate text from prompt using Qwen with streaming.
        
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
        
        logger.debug(f"Calling Qwen API (streaming) with model {self.model}")
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
            logger.error(f"Qwen streaming API error: {e}")
            raise

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Estimate cost for Qwen API call.
        
        Qwen pricing (as of 2024):
        - qwen-max: ¥0.04/1K tokens input, ¥0.12/1K tokens output
        - qwen-plus: ¥0.008/1K tokens input, ¥0.024/1K tokens output
        - qwen-turbo: ¥0.003/1K tokens input, ¥0.006/1K tokens output
        - qwen-long: ¥0.0005/1K tokens input, ¥0.002/1K tokens output
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Estimated cost in CNY
        """
        model_lower = self.model.lower()
        
        if "qwen-max" in model_lower:
            input_cost = input_tokens / 1000 * 0.04
            output_cost = output_tokens / 1000 * 0.12
        elif "qwen-plus" in model_lower:
            input_cost = input_tokens / 1000 * 0.008
            output_cost = output_tokens / 1000 * 0.024
        elif "qwen-turbo" in model_lower:
            input_cost = input_tokens / 1000 * 0.003
            output_cost = output_tokens / 1000 * 0.006
        elif "qwen-long" in model_lower:
            input_cost = input_tokens / 1000 * 0.0005
            output_cost = output_tokens / 1000 * 0.002
        else:
            # Default to qwen-plus pricing
            input_cost = input_tokens / 1000 * 0.008
            output_cost = output_tokens / 1000 * 0.024
        
        return input_cost + output_cost
