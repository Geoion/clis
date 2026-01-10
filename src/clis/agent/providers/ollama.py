"""
Ollama LLM provider implementation.
"""

from typing import Any, Dict, Generator, Optional

import requests

from clis.agent.providers.base import LLMProvider
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class OllamaProvider(LLMProvider):
    """Ollama LLM provider for local models."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3",
        temperature: float = 0.1,
        max_tokens: int = 2000,
        timeout: int = 30,
    ):
        """
        Initialize Ollama provider.
        
        Args:
            base_url: Ollama API base URL
            model: Model name (llama3, codellama, mistral, etc.)
            temperature: Temperature for generation
            max_tokens: Maximum tokens in response
            timeout: Request timeout in seconds
        """
        super().__init__(None, base_url, model, temperature, max_tokens, timeout)
        
        # Check if Ollama is running
        try:
            response = requests.get(f"{base_url}/api/tags", timeout=2)
            if response.status_code != 200:
                logger.warning("Ollama is not responding correctly")
        except Exception as e:
            logger.warning(f"Cannot connect to Ollama: {e}")
            logger.warning("Make sure Ollama is running: https://ollama.ai/download")

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Generate text from prompt using Ollama.
        
        Args:
            prompt: User prompt
            system_prompt: System prompt
            temperature: Temperature override
            max_tokens: Max tokens override
            
        Returns:
            Generated text
        """
        temp = temperature if temperature is not None else self.temperature
        max_tok = max_tokens if max_tokens is not None else self.max_tokens
        
        # Build request payload
        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temp,
                "num_predict": max_tok,
            },
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        
        logger.debug(f"Calling Ollama API with model {self.model}")
        logger.debug(f"Temperature: {temp}, Max tokens: {max_tok}")
        
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            
            result = response.json()
            content = result.get("response", "")
            
            # Log token usage if available
            if "eval_count" in result:
                logger.info(
                    f"Token usage - Input: {result.get('prompt_eval_count', 0)}, "
                    f"Output: {result.get('eval_count', 0)}"
                )
            
            return content
        
        except requests.exceptions.ConnectionError:
            logger.error("Cannot connect to Ollama. Is it running?")
            raise RuntimeError(
                "Cannot connect to Ollama. Please ensure Ollama is running.\n"
                "Install: https://ollama.ai/download\n"
                f"Then run: ollama pull {self.model}"
            )
        except Exception as e:
            logger.error(f"Ollama API error: {e}")
            raise

    def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Generator[str, None, None]:
        """
        Generate text from prompt using Ollama with streaming.
        
        Args:
            prompt: User prompt
            system_prompt: System prompt
            temperature: Temperature override
            max_tokens: Max tokens override
            
        Yields:
            Text chunks as they are generated
        """
        temp = temperature if temperature is not None else self.temperature
        max_tok = max_tokens if max_tokens is not None else self.max_tokens
        
        # Build request payload
        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,  # Enable streaming
            "options": {
                "temperature": temp,
                "num_predict": max_tok,
            },
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        
        logger.debug(f"Calling Ollama API (streaming) with model {self.model}")
        logger.debug(f"Temperature: {temp}, Max tokens: {max_tok}")
        
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout,
                stream=True,  # Enable streaming response
            )
            response.raise_for_status()
            
            # Process streaming response
            for line in response.iter_lines():
                if line:
                    try:
                        result = requests.compat.json.loads(line)
                        if "response" in result:
                            yield result["response"]
                        
                        # Check if done
                        if result.get("done", False):
                            # Log token usage if available
                            if "eval_count" in result:
                                logger.info(
                                    f"Token usage - Input: {result.get('prompt_eval_count', 0)}, "
                                    f"Output: {result.get('eval_count', 0)}"
                                )
                            break
                    except Exception as e:
                        logger.warning(f"Error parsing streaming response: {e}")
                        continue
        
        except requests.exceptions.ConnectionError:
            logger.error("Cannot connect to Ollama. Is it running?")
            raise RuntimeError(
                "Cannot connect to Ollama. Please ensure Ollama is running.\n"
                "Install: https://ollama.ai/download\n"
                f"Then run: ollama pull {self.model}"
            )
        except Exception as e:
            logger.error(f"Ollama streaming API error: {e}")
            raise

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Estimate cost for Ollama API call.
        
        Ollama is free (local), so cost is always 0.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Cost (always 0 for Ollama)
        """
        return 0.0

    def is_available(self) -> bool:
        """
        Check if Ollama is available.
        
        Returns:
            True if Ollama is running and model is available
        """
        try:
            # Check if Ollama is running
            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            if response.status_code != 200:
                return False
            
            # Check if model is available
            models = response.json().get("models", [])
            model_names = [m["name"] for m in models]
            
            return any(self.model in name for name in model_names)
        
        except Exception:
            return False
