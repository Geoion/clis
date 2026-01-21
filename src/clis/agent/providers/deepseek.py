"""
DeepSeek LLM provider implementation.
"""

from typing import Generator, Optional

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
        max_reasoning_tokens: Optional[int] = None,
    ):
        """
        Initialize DeepSeek provider.
        
        Args:
            api_key: DeepSeek API key
            base_url: API base URL
            model: Model name (deepseek-chat, deepseek-r1, deepseek-coder)
            temperature: Temperature for generation
            max_tokens: Maximum tokens in response
            timeout: Request timeout in seconds
            max_reasoning_tokens: Max tokens for reasoning (R1 only)
        """
        super().__init__(api_key, base_url, model, temperature, max_tokens, timeout)
        
        if not api_key:
            raise ValueError("DeepSeek API key is required")
        
        self.max_reasoning_tokens = max_reasoning_tokens
        
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
        Generate text from prompt using DeepSeek.
        
        Args:
            prompt: User prompt
            system_prompt: System prompt
            temperature: Temperature override
            max_tokens: Max tokens override
            max_reasoning_tokens: Max reasoning tokens override (R1 only)
            
        Returns:
            Generated text
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        temp = temperature if temperature is not None else self.temperature
        max_tok = max_tokens if max_tokens is not None else self.max_tokens
        max_reasoning = max_reasoning_tokens if max_reasoning_tokens is not None else self.max_reasoning_tokens
        
        logger.debug(f"Calling DeepSeek API with model {self.model}")
        logger.debug(f"Temperature: {temp}, Max tokens: {max_tok}, Max reasoning: {max_reasoning}")
        
        try:
            # Build request parameters
            api_params = {
                "model": self.model,
                "messages": messages,
                "temperature": temp,
                "max_tokens": max_tok,
            }
            
            # R1 models support reasoning parameter
            if 'r1' in self.model.lower() and max_reasoning:
                api_params["max_reasoning_tokens"] = max_reasoning
            
            response = self.client.chat.completions.create(**api_params)
            
            content = response.choices[0].message.content or ""
            
            # Log token usage
            if response.usage:
                usage_msg = (
                    f"Token usage - Input: {response.usage.prompt_tokens}, "
                    f"Output: {response.usage.completion_tokens}, "
                    f"Total: {response.usage.total_tokens}"
                )
                
                # R1 may have reasoning tokens
                if hasattr(response.usage, 'reasoning_tokens'):
                    usage_msg += f", Reasoning: {response.usage.reasoning_tokens}"
                
                logger.info(usage_msg)
            
            return content
        
        except Exception as e:
            logger.error(f"DeepSeek API error: {e}")
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
        Generate text from prompt using DeepSeek with streaming.
        
        Args:
            prompt: User prompt
            system_prompt: System prompt
            temperature: Temperature override
            max_tokens: Max tokens override
            max_reasoning_tokens: Max reasoning tokens override (R1 only)
            
        Yields:
            Text chunks as they are generated
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        temp = temperature if temperature is not None else self.temperature
        max_tok = max_tokens if max_tokens is not None else self.max_tokens
        max_reasoning = max_reasoning_tokens if max_reasoning_tokens is not None else self.max_reasoning_tokens
        
        logger.debug(f"Calling DeepSeek API (streaming) with model {self.model}")
        logger.debug(f"Temperature: {temp}, Max tokens: {max_tok}, Max reasoning: {max_reasoning}")
        
        try:
            api_params = {
                "model": self.model,
                "messages": messages,
                "temperature": temp,
                "max_tokens": max_tok,
                "stream": True,
            }
            
            if 'r1' in self.model.lower() and max_reasoning:
                api_params["max_reasoning_tokens"] = max_reasoning
            
            stream = self.client.chat.completions.create(**api_params)
            
            # Track tokens for logging
            total_tokens = 0
            
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    total_tokens += len(content.split())  # Rough estimate
                    yield content
            
            logger.info(f"Streaming completed, approximate tokens: {total_tokens}")
        
        except Exception as e:
            logger.error(f"DeepSeek streaming API error: {e}")
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
