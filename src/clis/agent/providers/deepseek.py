"""
DeepSeek LLM provider implementation.
"""

from typing import Generator, Optional

from openai import OpenAI

from clis.agent.providers.base import LLMProvider
from clis.utils.logger import get_logger

logger = get_logger(__name__)


def _should_apply_reasoning_token_limit(model: str, thinking_mode: Optional[bool]) -> bool:
    """
    Whether to send max_reasoning_tokens for this model.

    Explicit thinking_mode=True enables it for V4 Flash; False disables it.
    When thinking_mode is None, legacy model id heuristics apply (R1 / reasoner).
    """
    if thinking_mode is True:
        return True
    if thinking_mode is False:
        return False
    lowered = model.lower()
    return "r1" in lowered or "reasoner" in lowered


class DeepSeekProvider(LLMProvider):
    """DeepSeek LLM provider using OpenAI-compatible API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.deepseek.com/v1",
        model: str = "deepseek-v4-flash",
        temperature: float = 0.1,
        max_tokens: int = 2000,
        timeout: int = 30,
        max_reasoning_tokens: Optional[int] = None,
        thinking_mode: Optional[bool] = None,
    ):
        """
        Initialize DeepSeek provider.
        
        Args:
            api_key: DeepSeek API key
            base_url: API base URL
            model: Model name (e.g. deepseek-v4-flash, deepseek-v4-pro,
                deepseek-chat, deepseek-reasoner — legacy ids remain supported)
            temperature: Temperature for generation
            max_tokens: Maximum tokens in response
            timeout: Request timeout in seconds
            max_reasoning_tokens: Max tokens for reasoning (reasoning models)
            thinking_mode: For deepseek-v4-flash, set True/False to control
                reasoning token limit; None uses legacy name-based detection only
        """
        super().__init__(api_key, base_url, model, temperature, max_tokens, timeout)
        
        if not api_key:
            raise ValueError("DeepSeek API key is required")
        
        self.max_reasoning_tokens = max_reasoning_tokens
        self.thinking_mode = thinking_mode
        
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
            max_reasoning_tokens: Max reasoning tokens override (reasoning models)
            
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
            
            if _should_apply_reasoning_token_limit(self.model, self.thinking_mode) and max_reasoning:
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
            max_reasoning_tokens: Max reasoning tokens override (reasoning models)
            
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
            
            if _should_apply_reasoning_token_limit(self.model, self.thinking_mode) and max_reasoning:
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
        Estimate cost for DeepSeek API call (CNY, uncached input).

        Uses published per-million-token rates for V4; legacy models keep
        the previous 1K-token based estimate.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Estimated cost in CNY
        """
        name = self.model.lower()
        if "v4-pro" in name:
            input_per_m, output_per_m = 3.0, 6.0
        elif "v4-flash" in name:
            input_per_m, output_per_m = 1.0, 2.0
        else:
            input_per_m = 0.001 * 1000.0
            output_per_m = 0.002 * 1000.0
        input_cost = input_tokens / 1_000_000 * input_per_m
        output_cost = output_tokens / 1_000_000 * output_per_m
        return input_cost + output_cost
