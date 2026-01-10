"""
Built-in tools for CLIS.
"""

import os
import subprocess
from pathlib import Path
from typing import Any, Dict

from clis.tools.base import Tool, ToolResult
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class ListFilesTool(Tool):
    """List files in a directory."""
    
    @property
    def name(self) -> str:
        return "list_files"
    
    @property
    def description(self) -> str:
        return "List files in a directory. Can filter by pattern (e.g., '*.py', '*.md')."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to list (default: current directory)",
                    "default": "."
                },
                "pattern": {
                    "type": "string",
                    "description": "File pattern to filter (e.g., '*.py', '*.md')",
                    "default": "*"
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Whether to list files recursively",
                    "default": False
                }
            },
            "required": []
        }
    
    def execute(self, path: str = ".", pattern: str = "*", recursive: bool = False) -> ToolResult:
        """Execute list files."""
        try:
            path_obj = Path(path)
            
            if not path_obj.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Path does not exist: {path}"
                )
            
            if not path_obj.is_dir():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Path is not a directory: {path}"
                )
            
            # List files
            if recursive:
                files = list(path_obj.rglob(pattern))
            else:
                files = list(path_obj.glob(pattern))
            
            # Filter out directories, only keep files
            files = [f for f in files if f.is_file()]
            
            # Sort by name
            files.sort()
            
            # Format output
            if not files:
                output = f"No files found matching pattern '{pattern}' in {path}"
            else:
                output = f"Found {len(files)} file(s) in {path}:\n"
                output += "\n".join([f"  {f.relative_to(path_obj) if f.is_relative_to(path_obj) else f}" for f in files])
            
            return ToolResult(
                success=True,
                output=output,
                metadata={"count": len(files), "files": [str(f) for f in files]}
            )
        
        except Exception as e:
            logger.error(f"Error listing files: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error listing files: {str(e)}"
            )


class ReadFileTool(Tool):
    """Read file content with intelligent chunking support."""
    
    def __init__(self, chunker=None):
        """
        Initialize ReadFileTool.
        
        Args:
            chunker: Optional FileChunker instance for intelligent file splitting.
                     If None, chunking is disabled.
        """
        self._chunker = chunker
    
    @property
    def name(self) -> str:
        return "read_file"
    
    @property
    def description(self) -> str:
        return (
            "Read file content. Supports intelligent chunking for large files. "
            "Use chunk_index to read specific chunks of large files."
        )
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to read"
                },
                "max_lines": {
                    "type": "integer",
                    "description": "Maximum number of lines to read (default: all, -1)",
                    "default": -1
                },
                "chunk_index": {
                    "type": "integer",
                    "description": "Which chunk to read for large files (0-indexed, default: 0)",
                    "default": 0
                },
                "auto_chunk": {
                    "type": "boolean",
                    "description": "Enable automatic chunking for large files (default: true if chunker configured)",
                    "default": True
                }
            },
            "required": ["path"]
        }
    
    def set_chunker(self, chunker) -> None:
        """Set the file chunker instance."""
        self._chunker = chunker
    
    def execute(
        self,
        path: str,
        max_lines: int = -1,
        chunk_index: int = 0,
        auto_chunk: bool = True
    ) -> ToolResult:
        """
        Execute read file with optional chunking.
        
        Args:
            path: Path to the file
            max_lines: Maximum lines to read (-1 for all)
            chunk_index: Which chunk to read (0-indexed)
            auto_chunk: Whether to use automatic chunking
        """
        try:
            path_obj = Path(path)
            
            if not path_obj.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"File does not exist: {path}"
                )
            
            if not path_obj.is_file():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Path is not a file: {path}"
                )
            
            # Check if chunking should be used
            use_chunking = (
                auto_chunk and 
                self._chunker is not None and 
                max_lines <= 0  # Don't chunk if max_lines is specified
            )
            
            if use_chunking:
                needs_chunk, estimated_tokens, line_count = self._chunker.needs_chunking(path)
                
                if needs_chunk:
                    return self._read_with_chunking(path_obj, chunk_index, estimated_tokens, line_count)
            
            # Standard file reading
            return self._read_standard(path_obj, max_lines)
        
        except UnicodeDecodeError:
            return ToolResult(
                success=False,
                output="",
                error=f"File is not a text file or uses unsupported encoding: {path}"
            )
        except Exception as e:
            logger.error(f"Error reading file: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error reading file: {str(e)}"
            )
    
    def _read_standard(self, path_obj: Path, max_lines: int) -> ToolResult:
        """Standard file reading without chunking."""
        with open(path_obj, 'r', encoding='utf-8') as f:
            if max_lines > 0:
                lines = []
                i = 0
                for i, line in enumerate(f):
                    if i >= max_lines:
                        break
                    lines.append(line.rstrip('\n'))
                content = '\n'.join(lines)
                if i >= max_lines:
                    content += f"\n... (truncated, showing first {max_lines} lines)"
            else:
                content = f.read()
        
        return ToolResult(
            success=True,
            output=content,
            metadata={"path": str(path_obj), "size": path_obj.stat().st_size}
        )
    
    def _read_with_chunking(
        self,
        path_obj: Path,
        chunk_index: int,
        estimated_tokens: int,
        line_count: int
    ) -> ToolResult:
        """Read file with chunking support."""
        chunks = self._chunker.chunk_file(str(path_obj))
        total_chunks = len(chunks)
        
        if chunk_index < 0 or chunk_index >= total_chunks:
            return ToolResult(
                success=False,
                output="",
                error=f"Invalid chunk_index: {chunk_index}. File has {total_chunks} chunks (0-{total_chunks-1})"
            )
        
        chunk = chunks[chunk_index]
        
        # Add chunk navigation info
        chunk_info = (
            f"=== File: {path_obj} ===\n"
            f"=== Chunk {chunk.chunk_index + 1}/{chunk.total_chunks} | "
            f"Lines {chunk.start_line}-{chunk.end_line} | "
            f"~{estimated_tokens} total tokens ===\n\n"
        )
        
        # Navigation hints
        if total_chunks > 1:
            nav_hints = []
            if chunk_index > 0:
                nav_hints.append(f"Previous: chunk_index={chunk_index - 1}")
            if chunk_index < total_chunks - 1:
                nav_hints.append(f"Next: chunk_index={chunk_index + 1}")
            if nav_hints:
                chunk_info += f"[Navigation: {' | '.join(nav_hints)}]\n\n"
        
        content = chunk_info + chunk.content
        
        return ToolResult(
            success=True,
            output=content,
            metadata={
                "path": str(path_obj),
                "size": path_obj.stat().st_size,
                "chunk_index": chunk_index,
                "total_chunks": total_chunks,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "estimated_tokens": estimated_tokens,
                "total_lines": line_count
            }
        )


class ExecuteCommandTool(Tool):
    """Execute a shell command."""
    
    @property
    def name(self) -> str:
        return "execute_command"
    
    @property
    def description(self) -> str:
        return "Execute a shell command and return its output. Use with caution."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Command timeout in seconds (default: 30)",
                    "default": 30
                }
            },
            "required": ["command"]
        }
    
    def execute(self, command: str, timeout: int = 30) -> ToolResult:
        """Execute shell command."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"
            
            return ToolResult(
                success=result.returncode == 0,
                output=output,
                error=None if result.returncode == 0 else f"Command exited with code {result.returncode}",
                metadata={"exit_code": result.returncode}
            )
        
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                output="",
                error=f"Command timed out after {timeout} seconds"
            )
        except Exception as e:
            logger.error(f"Error executing command: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error executing command: {str(e)}"
            )


class GitStatusTool(Tool):
    """Get git repository status."""
    
    @property
    def name(self) -> str:
        return "git_status"
    
    @property
    def description(self) -> str:
        return "Get the status of the git repository, including modified, added, and untracked files."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "short": {
                    "type": "boolean",
                    "description": "Use short format (default: true)",
                    "default": True
                }
            },
            "required": []
        }
    
    def execute(self, short: bool = True) -> ToolResult:
        """Execute git status."""
        try:
            cmd = ["git", "status"]
            if short:
                cmd.append("--short")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                return ToolResult(
                    success=False,
                    output="",
                    error="Not a git repository or git command failed"
                )
            
            output = result.stdout.strip()
            if not output:
                output = "Working tree clean (no changes)"
            
            return ToolResult(
                success=True,
                output=output,
                metadata={"clean": not result.stdout.strip()}
            )
        
        except Exception as e:
            logger.error(f"Error getting git status: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error getting git status: {str(e)}"
            )


class DockerPsTool(Tool):
    """List running Docker containers."""
    
    @property
    def name(self) -> str:
        return "docker_ps"
    
    @property
    def description(self) -> str:
        return "List Docker containers (running or all)."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "all": {
                    "type": "boolean",
                    "description": "Show all containers (default: only running)",
                    "default": False
                }
            },
            "required": []
        }
    
    def execute(self, all: bool = False) -> ToolResult:
        """Execute docker ps."""
        try:
            cmd = ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}\t{{.Image}}"]
            if all:
                cmd.append("-a")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                return ToolResult(
                    success=False,
                    output="",
                    error="Docker command failed. Is Docker running?"
                )
            
            output = result.stdout.strip()
            if not output:
                output = "No containers found"
            else:
                # Format output
                lines = output.split('\n')
                formatted = "Docker containers:\n"
                for line in lines:
                    parts = line.split('\t')
                    if len(parts) >= 3:
                        formatted += f"  • {parts[0]} ({parts[1]}) - {parts[2]}\n"
                output = formatted.rstrip()
            
            return ToolResult(
                success=True,
                output=output,
                metadata={"count": len(output.split('\n')) if output != "No containers found" else 0}
            )
        
        except Exception as e:
            logger.error(f"Error listing Docker containers: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Error listing Docker containers: {str(e)}"
            )
