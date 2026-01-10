"""
File chunker - intelligent file splitting based on model context window.

Supports:
- Automatic chunking based on model context window size
- Manual threshold override
- Chunk overlap for context continuity
- Multiple strategies: lines, tokens, semantic
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

from clis.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class FileChunk:
    """Represents a chunk of a file."""
    
    content: str
    start_line: int
    end_line: int
    chunk_index: int
    total_chunks: int
    file_path: str
    
    @property
    def header(self) -> str:
        """Generate a header describing this chunk."""
        return (
            f"[File: {self.file_path}] "
            f"[Chunk {self.chunk_index + 1}/{self.total_chunks}] "
            f"[Lines {self.start_line}-{self.end_line}]"
        )
    
    def __str__(self) -> str:
        return f"{self.header}\n{self.content}"


class FileChunker:
    """
    Intelligent file chunker based on model context window.
    
    Usage:
        chunker = FileChunker(
            window_size=64000,      # Model's context window
            auto_chunk=True,        # Enable auto chunking
            chunk_threshold=0,      # 0 = auto calculate
            chunk_overlap=200,      # Lines overlap between chunks
            reserved_tokens=4000    # Reserved for system/response
        )
        
        # Get all chunks
        chunks = chunker.chunk_file("large_file.py")
        
        # Or iterate over chunks
        for chunk in chunker.iter_chunks("large_file.py"):
            process(chunk)
    """
    
    # Approximate tokens per line (for estimation)
    TOKENS_PER_LINE = 15
    
    # Approximate characters per token
    CHARS_PER_TOKEN = 4
    
    def __init__(
        self,
        window_size: int = 64000,
        auto_chunk: bool = True,
        chunk_threshold: int = 0,
        chunk_overlap: int = 200,
        reserved_tokens: int = 4000
    ):
        """
        Initialize file chunker.
        
        Args:
            window_size: Model's context window size in tokens
            auto_chunk: Enable automatic chunking
            chunk_threshold: Manual threshold (0 = auto calculate)
            chunk_overlap: Lines to overlap between chunks
            reserved_tokens: Tokens reserved for system prompt and response
        """
        self.window_size = window_size
        self.auto_chunk = auto_chunk
        self.chunk_threshold = chunk_threshold
        self.chunk_overlap = chunk_overlap
        self.reserved_tokens = reserved_tokens
    
    @property
    def effective_threshold(self) -> int:
        """Calculate effective chunk threshold in tokens."""
        if self.chunk_threshold > 0:
            return self.chunk_threshold
        # Auto: use 60% of (window_size - reserved) for file content
        return int((self.window_size - self.reserved_tokens) * 0.6)
    
    @property
    def max_lines_per_chunk(self) -> int:
        """Calculate maximum lines per chunk based on token threshold."""
        return self.effective_threshold // self.TOKENS_PER_LINE
    
    @property
    def max_chars_per_chunk(self) -> int:
        """Calculate maximum characters per chunk."""
        return self.effective_threshold * self.CHARS_PER_TOKEN
    
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        
        This is a rough estimation. For more accurate results,
        use the actual tokenizer for the model.
        """
        # Simple estimation: chars / 4
        return len(text) // self.CHARS_PER_TOKEN
    
    def needs_chunking(self, file_path: str) -> Tuple[bool, int, int]:
        """
        Check if a file needs chunking.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Tuple of (needs_chunking, estimated_tokens, line_count)
        """
        if not self.auto_chunk:
            return False, 0, 0
        
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            return False, 0, 0
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
        except (UnicodeDecodeError, IOError):
            return False, 0, 0
        
        line_count = content.count('\n') + 1
        estimated_tokens = self.estimate_tokens(content)
        
        needs_chunk = estimated_tokens > self.effective_threshold
        
        logger.debug(
            f"File {file_path}: {line_count} lines, ~{estimated_tokens} tokens, "
            f"threshold: {self.effective_threshold}, needs_chunking: {needs_chunk}"
        )
        
        return needs_chunk, estimated_tokens, line_count
    
    def chunk_file(self, file_path: str) -> List[FileChunk]:
        """
        Split a file into chunks.
        
        Args:
            file_path: Path to the file
            
        Returns:
            List of FileChunk objects
        """
        return list(self.iter_chunks(file_path))
    
    def iter_chunks(self, file_path: str) -> Iterator[FileChunk]:
        """
        Iterate over file chunks.
        
        Args:
            file_path: Path to the file
            
        Yields:
            FileChunk objects
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if not path.is_file():
            raise ValueError(f"Path is not a file: {file_path}")
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            raise ValueError(f"Cannot read file (encoding error): {file_path}")
        
        total_lines = len(lines)
        
        # Check if chunking is needed
        needs_chunk, _, _ = self.needs_chunking(file_path)
        
        if not needs_chunk:
            # Return whole file as single chunk
            content = ''.join(lines).rstrip('\n')
            yield FileChunk(
                content=content,
                start_line=1,
                end_line=total_lines,
                chunk_index=0,
                total_chunks=1,
                file_path=str(path)
            )
            return
        
        # Calculate chunks
        max_lines = self.max_lines_per_chunk
        step = max(1, max_lines - self.chunk_overlap)
        
        chunks_info = []
        start = 0
        
        while start < total_lines:
            end = min(start + max_lines, total_lines)
            chunks_info.append((start, end))
            
            if end >= total_lines:
                break
            
            start += step
        
        total_chunks = len(chunks_info)
        
        logger.info(
            f"Splitting {file_path} into {total_chunks} chunks "
            f"(max {max_lines} lines/chunk, {self.chunk_overlap} lines overlap)"
        )
        
        for chunk_idx, (start_idx, end_idx) in enumerate(chunks_info):
            chunk_lines = lines[start_idx:end_idx]
            content = ''.join(chunk_lines).rstrip('\n')
            
            yield FileChunk(
                content=content,
                start_line=start_idx + 1,  # 1-indexed
                end_line=end_idx,
                chunk_index=chunk_idx,
                total_chunks=total_chunks,
                file_path=str(path)
            )
    
    def chunk_text(
        self,
        text: str,
        source_name: str = "text"
    ) -> List[FileChunk]:
        """
        Split text content into chunks.
        
        Args:
            text: Text content to chunk
            source_name: Name for the source (for headers)
            
        Returns:
            List of FileChunk objects
        """
        lines = text.split('\n')
        total_lines = len(lines)
        
        estimated_tokens = self.estimate_tokens(text)
        
        if not self.auto_chunk or estimated_tokens <= self.effective_threshold:
            # Return whole text as single chunk
            return [FileChunk(
                content=text,
                start_line=1,
                end_line=total_lines,
                chunk_index=0,
                total_chunks=1,
                file_path=source_name
            )]
        
        # Calculate chunks
        max_lines = self.max_lines_per_chunk
        step = max(1, max_lines - self.chunk_overlap)
        
        chunks = []
        chunks_info = []
        start = 0
        
        while start < total_lines:
            end = min(start + max_lines, total_lines)
            chunks_info.append((start, end))
            
            if end >= total_lines:
                break
            
            start += step
        
        total_chunks = len(chunks_info)
        
        for chunk_idx, (start_idx, end_idx) in enumerate(chunks_info):
            chunk_lines = lines[start_idx:end_idx]
            content = '\n'.join(chunk_lines)
            
            chunks.append(FileChunk(
                content=content,
                start_line=start_idx + 1,
                end_line=end_idx,
                chunk_index=chunk_idx,
                total_chunks=total_chunks,
                file_path=source_name
            ))
        
        return chunks
    
    @classmethod
    def from_config(cls, context_config) -> "FileChunker":
        """
        Create FileChunker from ContextConfig.
        
        Args:
            context_config: ContextConfig object from config models
            
        Returns:
            Configured FileChunker instance
        """
        return cls(
            window_size=context_config.window_size,
            auto_chunk=context_config.auto_chunk,
            chunk_threshold=context_config.chunk_threshold,
            chunk_overlap=context_config.chunk_overlap,
            reserved_tokens=context_config.reserved_tokens
        )


# Preset configurations for supported models
# Note: CLIS primarily supports DeepSeek, Qwen, and Ollama
# For Ollama, context window depends on the specific model running locally
MODEL_PRESETS = {
    # DeepSeek (API)
    "deepseek-chat": {"window_size": 64000},
    "deepseek-coder": {"window_size": 128000},
    "deepseek-reasoner": {"window_size": 64000},
    
    # Qwen (API)
    "qwen-plus": {"window_size": 32000},
    "qwen-turbo": {"window_size": 8000},
    "qwen-max": {"window_size": 128000},
    "qwen-long": {"window_size": 1000000},  # Long context model
    
    # Ollama local models (context depends on your local setup)
    # These are common defaults, adjust based on your model's actual config
    "llama3": {"window_size": 8192},
    "llama3:8b": {"window_size": 8192},
    "llama3:70b": {"window_size": 8192},
    "llama3.1": {"window_size": 128000},
    "llama3.2": {"window_size": 128000},
    "codellama": {"window_size": 16384},
    "mistral": {"window_size": 32000},
    "mixtral": {"window_size": 32000},
    "phi": {"window_size": 2048},
    "phi3": {"window_size": 4096},
    "qwen2": {"window_size": 32000},
    "qwen2.5": {"window_size": 32000},
    "gemma": {"window_size": 8192},
    "gemma2": {"window_size": 8192},
    "yi": {"window_size": 4096},
    "deepseek-v2": {"window_size": 128000},
    "deepseek-coder-v2": {"window_size": 128000},
}


def get_model_preset(model_name: str) -> dict:
    """
    Get preset configuration for a model.
    
    Args:
        model_name: Name of the model
        
    Returns:
        Dict with preset configuration, or default values
    """
    # Check exact match first
    if model_name in MODEL_PRESETS:
        return MODEL_PRESETS[model_name]
    
    # Check prefix match
    for preset_name, preset_config in MODEL_PRESETS.items():
        if model_name.startswith(preset_name):
            return preset_config
    
    # Return conservative default
    logger.warning(
        f"No preset found for model '{model_name}', using default (64000 tokens)"
    )
    return {"window_size": 64000}
