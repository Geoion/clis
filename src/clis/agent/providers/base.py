"""
Base class for LLM providers.
"""

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, Generator, Optional


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "",
        temperature: float = 0.1,
        max_tokens: int = 2000,
        timeout: int = 30,
    ):
        """
        Initialize LLM provider.
        
        Args:
            api_key: API key for authentication
            base_url: Base URL for API
            model: Model name
            temperature: Temperature for generation
            max_tokens: Maximum tokens in response
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Generate text from prompt.
        
        Args:
            prompt: User prompt
            system_prompt: System prompt
            temperature: Temperature override
            max_tokens: Max tokens override
            
        Returns:
            Generated text
        """
        pass

    def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Generator[str, None, None]:
        """
        Generate text from prompt with streaming (optional).
        
        Default implementation falls back to non-streaming generate().
        Subclasses should override this for true streaming support.
        
        Args:
            prompt: User prompt
            system_prompt: System prompt
            temperature: Temperature override
            max_tokens: Max tokens override
            
        Yields:
            Text chunks as they are generated
        """
        # Default fallback: return entire response at once
        response = self.generate(prompt, system_prompt, temperature, max_tokens)
        yield response

    def parse_json_response(self, response: str) -> Dict[str, Any]:
        """
        Parse JSON response from LLM.
        
        Args:
            response: Response text
            
        Returns:
            Parsed JSON dict
            
        Raises:
            ValueError: If response is not valid JSON
        """
        # Try to extract JSON from markdown code blocks
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            json_str = response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            json_str = response[start:end].strip()
        else:
            json_str = response.strip()
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON response: {e}\nResponse: {response}")

    def count_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Estimated token count
        """
        # Rough estimation: 1 token ≈ 4 characters
        return len(text) // 4

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Estimate cost for API call.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Estimated cost in CNY
        """
        # Default implementation (override in subclasses for accurate pricing)
        # Assuming DeepSeek pricing: ¥0.001/1K tokens
        return (input_tokens + output_tokens) / 1000 * 0.001
