"""
OpenAI LLM provider implementation.
"""

from typing import Generator, Optional

from openai import OpenAI

from clis.agent.providers.base import LLMProvider
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o",
        temperature: float = 0.1,
        max_tokens: int = 2000,
        timeout: int = 30,
    ):
        """
        Initialize OpenAI provider.
        
        Args:
            api_key: OpenAI API key
            base_url: API base URL
            model: Model name (gpt-4o, gpt-4-turbo, gpt-3.5-turbo, etc.)
            temperature: Temperature for generation
            max_tokens: Maximum tokens in response
            timeout: Request timeout in seconds
        """
        super().__init__(api_key, base_url, model, temperature, max_tokens, timeout)
        
        if not api_key:
            raise ValueError("OpenAI API key is required")
        
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
        Generate text from prompt using OpenAI.
        
        Args:
            prompt: User prompt
            system_prompt: System prompt
            temperature: Temperature override
            max_tokens: Max tokens override
            max_reasoning_tokens: Max reasoning tokens (for o1/o3 models)
            
        Returns:
            Generated text
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        temp = temperature if temperature is not None else self.temperature
        max_tok = max_tokens if max_tokens is not None else self.max_tokens
        
        logger.debug(f"Calling OpenAI API with model {self.model}")
        logger.debug(f"Temperature: {temp}, Max tokens: {max_tok}")
        
        try:
            # Build request parameters
            api_params = {
                "model": self.model,
                "messages": messages,
                "temperature": temp,
                "max_tokens": max_tok,
            }
            
            # o1/o3 models support reasoning tokens
            if max_reasoning_tokens and ('o1' in self.model.lower() or 'o3' in self.model.lower()):
                api_params["max_reasoning_tokens"] = max_reasoning_tokens
            
            response = self.client.chat.completions.create(**api_params)
            
            content = response.choices[0].message.content or ""
            
            # Log token usage
            if response.usage:
                usage_msg = (
                    f"Token usage - Input: {response.usage.prompt_tokens}, "
                    f"Output: {response.usage.completion_tokens}, "
                    f"Total: {response.usage.total_tokens}"
                )
                
                # o1/o3 may have reasoning tokens
                if hasattr(response.usage, 'reasoning_tokens') and response.usage.reasoning_tokens:
                    usage_msg += f", Reasoning: {response.usage.reasoning_tokens}"
                
                logger.info(usage_msg)
            
            return content
        
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
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
        Generate text from prompt using OpenAI with streaming.
        
        Args:
            prompt: User prompt
            system_prompt: System prompt
            temperature: Temperature override
            max_tokens: Max tokens override
            max_reasoning_tokens: Max reasoning tokens (for o1/o3 models)
            
        Yields:
            Text chunks as they are generated
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        temp = temperature if temperature is not None else self.temperature
        max_tok = max_tokens if max_tokens is not None else self.max_tokens
        
        logger.debug(f"Calling OpenAI API (streaming) with model {self.model}")
        logger.debug(f"Temperature: {temp}, Max tokens: {max_tok}")
        
        try:
            api_params = {
                "model": self.model,
                "messages": messages,
                "temperature": temp,
                "max_tokens": max_tok,
                "stream": True,
            }
            
            if max_reasoning_tokens and ('o1' in self.model.lower() or 'o3' in self.model.lower()):
                api_params["max_reasoning_tokens"] = max_reasoning_tokens
            
            stream = self.client.chat.completions.create(**api_params)
            
            # Track tokens for logging
            total_tokens = 0
            
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    total_tokens += len(content.split())
                    yield content
            
            logger.info(f"Streaming completed, approximate tokens: {total_tokens}")
        
        except Exception as e:
            logger.error(f"OpenAI streaming API error: {e}")
            raise

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Estimate cost for OpenAI API call.
        
        OpenAI pricing (as of 2024):
        - GPT-4o: $2.5/MTok input, $10/MTok output
        - GPT-4-turbo: $10/MTok input, $30/MTok output
        - GPT-3.5-turbo: $0.5/MTok input, $1.5/MTok output
        - o1: $15/MTok input, $60/MTok output
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Estimated cost in USD
        """
        model_lower = self.model.lower()
        
        if "gpt-4o" in model_lower:
            input_cost = input_tokens / 1_000_000 * 2.5
            output_cost = output_tokens / 1_000_000 * 10
        elif "gpt-4-turbo" in model_lower or "gpt-4-1106" in model_lower:
            input_cost = input_tokens / 1_000_000 * 10
            output_cost = output_tokens / 1_000_000 * 30
        elif "gpt-3.5-turbo" in model_lower:
            input_cost = input_tokens / 1_000_000 * 0.5
            output_cost = output_tokens / 1_000_000 * 1.5
        elif "o1" in model_lower or "o3" in model_lower:
            input_cost = input_tokens / 1_000_000 * 15
            output_cost = output_tokens / 1_000_000 * 60
        else:
            # Default to GPT-4o pricing
            input_cost = input_tokens / 1_000_000 * 2.5
            output_cost = output_tokens / 1_000_000 * 10
        
        return input_cost + output_cost
