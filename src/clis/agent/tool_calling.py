"""
Tool calling agent for CLIS.

Enables multi-turn conversations with tool calling capabilities.
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from clis.agent.agent import Agent
from clis.config import ConfigManager
from clis.tools.base import Tool, ToolExecutor, ToolResult
from clis.tools.filesystem.file_chunker import FileChunker
from clis.tools.builtin import ReadFileTool
from clis.utils.logger import get_logger

logger = get_logger(__name__)

# Default values (can be overridden by config)
# Maximum characters per tool output (to prevent context overflow)
# ~20000 chars ≈ 5000 tokens (rough estimate: 1 token ≈ 4 chars)
DEFAULT_MAX_TOOL_OUTPUT_CHARS = 20000

# Maximum total characters for all tool results combined
# ~100000 chars ≈ 25000 tokens, leaving room for system prompt and other content
DEFAULT_MAX_TOTAL_TOOL_RESULTS_CHARS = 100000

# Maximum total context length (system prompt + user prompt + tool results)
# Conservative limit: ~400000 chars ≈ 100000 tokens (model limit is 131072 tokens)
DEFAULT_MAX_TOTAL_CONTEXT_CHARS = 400000


class ToolCallingAgent:
    """Agent with tool calling capabilities."""
    
    def __init__(
        self,
        config_manager: Optional[ConfigManager] = None,
        tools: Optional[List[Tool]] = None,
        max_iterations: int = 10
    ):
        """
        Initialize tool calling agent.
        
        Args:
            config_manager: Configuration manager
            tools: List of available tools
            max_iterations: Maximum number of tool calling iterations
        """
        self.config_manager = config_manager or ConfigManager()
        self.agent = Agent(self.config_manager)
        self.tools = tools or []
        self.max_iterations = max_iterations
        
        # Load context limits from config
        self._setup_context_limits()
        
        # Setup file chunker based on config
        self._setup_file_chunker()
        
        # Setup tool executor
        self.tool_executor = ToolExecutor(self.tools)
        
        # Conversation history
        self.messages: List[Dict[str, str]] = []
    
    def _setup_context_limits(self) -> None:
        """Setup context limits based on model configuration."""
        try:
            llm_config = self.config_manager.load_llm_config()
            context_config = llm_config.model.context
            
            # Calculate limits based on window size
            window_size = context_config.window_size
            chars_per_token = 4  # Approximate
            
            # Max tool output: 20% of window
            self.max_tool_output_chars = int(window_size * 0.2 * chars_per_token)
            
            # Max total tool results: 40% of window  
            self.max_total_tool_results_chars = int(window_size * 0.4 * chars_per_token)
            
            # Max total context: 80% of window (leave room for response)
            self.max_total_context_chars = int(window_size * 0.8 * chars_per_token)
            
            logger.debug(
                f"Context limits configured for window_size={window_size}: "
                f"max_tool_output={self.max_tool_output_chars}, "
                f"max_total_results={self.max_total_tool_results_chars}, "
                f"max_context={self.max_total_context_chars}"
            )
        except Exception as e:
            logger.warning(f"Failed to load context config, using defaults: {e}")
            self.max_tool_output_chars = DEFAULT_MAX_TOOL_OUTPUT_CHARS
            self.max_total_tool_results_chars = DEFAULT_MAX_TOTAL_TOOL_RESULTS_CHARS
            self.max_total_context_chars = DEFAULT_MAX_TOTAL_CONTEXT_CHARS
    
    def _setup_file_chunker(self) -> None:
        """Setup file chunker for ReadFileTool based on config."""
        try:
            llm_config = self.config_manager.load_llm_config()
            context_config = llm_config.model.context
            
            if context_config.auto_chunk:
                # Create chunker from config
                self.file_chunker = FileChunker.from_config(context_config)
                
                # Find and configure ReadFileTool
                for tool in self.tools:
                    if isinstance(tool, ReadFileTool):
                        tool.set_chunker(self.file_chunker)
                        logger.debug(
                            f"Configured ReadFileTool with chunker: "
                            f"window_size={context_config.window_size}, "
                            f"threshold={self.file_chunker.effective_threshold} tokens"
                        )
                        break
            else:
                self.file_chunker = None
                logger.debug("File chunking disabled in config")
        except Exception as e:
            logger.warning(f"Failed to setup file chunker: {e}")
            self.file_chunker = None
    
    def execute_with_tools(
        self,
        query: str,
        system_prompt: str,
        skill_name: str = "Unknown"
    ) -> Tuple[List[str], str, List[Dict[str, Any]]]:
        """
        Execute query with tool calling support.
        
        Args:
            query: User query
            system_prompt: System prompt with skill instructions
            skill_name: Name of the skill being executed
            
        Returns:
            Tuple of (commands, explanation, tool_calls_history)
        """
        # Initialize conversation
        self.messages = []
        tool_calls_history = []
        
        # Get platform information
        from clis.utils.platform import get_platform, get_shell
        platform = get_platform()
        shell = get_shell()
        
        # Build initial prompt with tool definitions
        tools_description = self._format_tools_for_prompt()
        
        enhanced_system_prompt = f"""{system_prompt}

## Platform Information

**IMPORTANT**: You are running on {platform} with {shell} shell.
- Operating System: {platform}
- Shell: {shell}
- Generate commands compatible with this platform!
- DO NOT use Windows PowerShell commands (Get-ChildItem, etc.) on Unix systems
- DO NOT use Unix commands (ls, grep, etc.) on Windows

## Available Tools

You have access to the following tools to gather information before generating commands:

{tools_description}

## Tool Calling Protocol

**IMPORTANT**: You should call tools ONLY ONCE at the beginning to gather information, then IMMEDIATELY generate the final commands.

When you need information, respond with tool call(s) in this format:

```tool_call
{{
  "tool": "tool_name",
  "parameters": {{
    "param1": "value1",
    "param2": "value2"
  }}
}}
```

## Final Response Format

After tool results are provided, you MUST respond with the final commands in JSON format:

```json
{{
  "commands": ["command1", "command2"],
  "explanation": "Detailed explanation"
}}
```

**CRITICAL**: Do NOT call tools repeatedly. Call tools once to get information, then generate commands.

## Important Rules

1. Call tools ONCE at the start to get actual information (file lists, git status, etc.)
2. After receiving tool results, IMMEDIATELY generate the final commands
3. Base your commands on real data from tool calls
4. Don't use placeholder names (file1.py, container1, etc.)
5. Generate precise commands based on actual context
6. DO NOT call the same tool multiple times - you already have the information!
"""
        
        # Start conversation
        current_query = query
        iteration = 0
        called_tools = set()  # Track which tools have been called to prevent loops
        
        while iteration < self.max_iterations:
            iteration += 1
            logger.debug(f"Tool calling iteration {iteration}/{self.max_iterations}")
            
            # Generate response
            response = self.agent.generate(
                current_query,
                enhanced_system_prompt,
                inject_context=False
            )
            
            logger.debug(f"LLM Response:\n{response}")
            
            # Check if response contains tool calls
            tool_calls = self._extract_tool_calls(response)
            
            if tool_calls:
                # Check for repeated tool calls (indicates loop)
                tool_signatures = [f"{tc.get('tool')}:{tc.get('parameters')}" for tc in tool_calls]
                if any(sig in called_tools for sig in tool_signatures):
                    logger.warning("Detected repeated tool calls, forcing command generation")
                    # Force the LLM to generate commands instead of calling tools again
                    current_query = f"""You have already called these tools and received the results.
DO NOT call tools again. You MUST now generate the final commands based on the information you already have.

User's original request: "{query}"

Generate the final commands NOW in JSON format:
```json
{{
  "commands": ["command1", "command2"],
  "explanation": "explanation"
}}
```
"""
                    continue
                
                # Execute tool calls
                tool_results = []
                for tool_call in tool_calls:
                    tool_name = tool_call.get("tool")
                    parameters = tool_call.get("parameters", {})
                    
                    # Track tool call to prevent loops
                    tool_sig = f"{tool_name}:{parameters}"
                    called_tools.add(tool_sig)
                    
                    logger.info(f"Executing tool: {tool_name} with parameters: {parameters}")
                    
                    result = self.tool_executor.execute(tool_name, parameters)
                    tool_results.append({
                        "tool": tool_name,
                        "parameters": parameters,
                        "result": result.to_dict()
                    })
                    
                    tool_calls_history.append({
                        "tool": tool_name,
                        "parameters": parameters,
                        "success": result.success,
                        "output": result.output,
                        "error": result.error
                    })
                
                # Build next query with tool results
                results_text = self._format_tool_results(tool_results)
                
                # Build base query parts
                query_prefix = """You have gathered the necessary information from tools. Here are the results:

"""
                query_suffix = f"""

**IMPORTANT**: You now have all the information you need. DO NOT call any more tools.

User's original request: "{query}"

Based on the tool results above, generate the final shell commands to accomplish the user's request.

You MUST respond with commands in JSON format:
```json
{{
  "commands": ["command1", "command2", "..."],
  "explanation": "detailed explanation"
}}
```

DO NOT call tools again. Generate the final commands NOW.
"""
                
                # Check total context length and truncate if necessary
                base_query_len = len(query_prefix) + len(query_suffix)
                estimated_context = len(enhanced_system_prompt) + base_query_len + len(results_text)
                
                if estimated_context > self.max_total_context_chars:
                    # Calculate how much space is available for results
                    available_chars = self.max_total_context_chars - len(enhanced_system_prompt) - base_query_len
                    if available_chars > 1000:  # Only truncate if there's meaningful space
                        # Truncate results_text
                        truncated_results = results_text[:available_chars]
                        truncated_results += f"\n\n... (truncated due to context limit, showing first {available_chars} characters of {len(results_text)} total)"
                        results_text = truncated_results
                        logger.warning(
                            f"Context truncated: estimated {estimated_context} chars, "
                            f"limit is {self.max_total_context_chars} chars. "
                            f"Truncated tool results to {available_chars} chars."
                        )
                    else:
                        # Context is still too large even after truncation
                        logger.error(
                            f"Context too large even after truncation: {estimated_context} chars. "
                            f"System prompt or query may be too long. Using minimal query."
                        )
                        # Use a minimal query without tool results
                        current_query = f"""Tool results were too large to include fully.

User's original request: "{query}"

Please generate shell commands based on the user's request. You may need to make reasonable assumptions.

You MUST respond with commands in JSON format:
```json
{{
  "commands": ["command1", "command2", "..."],
  "explanation": "detailed explanation"
}}
```
"""
                        continue
                
                # Build final query
                current_query = query_prefix + results_text + query_suffix
                
                # Continue to next iteration
                continue
            
            # No tool calls, try to extract final commands
            commands_result = self._extract_commands(response)
            
            if commands_result:
                commands, explanation = commands_result
                return commands, explanation, tool_calls_history
            
            # Response doesn't contain tool calls or commands
            # Try one more time with explicit instruction
            if iteration < self.max_iterations:
                current_query = f"""Your previous response did not contain valid tool calls or commands.

User request: "{query}"

Please either:
1. Call tools to gather information (use the tool_call format)
2. Generate final commands (use the JSON format)

Your response:
{response}

Please provide a valid response.
"""
                continue
            
            # Max iterations reached
            break
        
        # Failed to get valid response
        logger.error(f"Failed to get valid response after {self.max_iterations} iterations")
        return (
            [],
            f"Failed to generate commands after {self.max_iterations} attempts. Please try rephrasing your request.",
            tool_calls_history
        )
    
    def _format_tools_for_prompt(self) -> str:
        """Format tool definitions for prompt."""
        if not self.tools:
            return "No tools available."
        
        tools_text = []
        for tool in self.tools:
            tools_text.append(f"""### {tool.name}

**Description**: {tool.description}

**Parameters**:
```json
{json.dumps(tool.parameters, indent=2)}
```
""")
        
        return "\n".join(tools_text)
    
    def _extract_tool_calls(self, response: str) -> List[Dict[str, Any]]:
        """Extract tool calls from response."""
        tool_calls = []
        
        # Pattern 1: ```tool_call ... ```
        pattern1 = r'```tool_call\s*\n(.*?)\n```'
        matches = re.findall(pattern1, response, re.DOTALL)
        
        for match in matches:
            try:
                tool_call = json.loads(match.strip())
                if "tool" in tool_call:
                    tool_calls.append(tool_call)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse tool call: {match}")
        
        # Pattern 2: Look for JSON objects with "tool" key
        if not tool_calls:
            # Try to find JSON objects
            json_pattern = r'\{[^{}]*"tool"[^{}]*\}'
            matches = re.findall(json_pattern, response)
            
            for match in matches:
                try:
                    tool_call = json.loads(match)
                    if "tool" in tool_call:
                        tool_calls.append(tool_call)
                except json.JSONDecodeError:
                    pass
        
        return tool_calls
    
    def _extract_commands(self, response: str) -> Optional[Tuple[List[str], str]]:
        """Extract commands from response."""
        try:
            # Try to parse as JSON directly
            data = json.loads(response)
            if "commands" in data:
                return data["commands"], data.get("explanation", "")
        except json.JSONDecodeError:
            pass
        
        # Try to extract JSON from code blocks
        json_pattern = r'```json\s*\n(.*?)\n```'
        matches = re.findall(json_pattern, response, re.DOTALL)
        
        for match in matches:
            try:
                data = json.loads(match.strip())
                if "commands" in data:
                    return data["commands"], data.get("explanation", "")
            except json.JSONDecodeError:
                continue
        
        # Try to find any JSON object with "commands" key
        json_obj_pattern = r'\{[^{}]*"commands"[^{}]*\[[^\]]*\][^{}]*\}'
        matches = re.findall(json_obj_pattern, response, re.DOTALL)
        
        for match in matches:
            try:
                data = json.loads(match)
                if "commands" in data:
                    return data["commands"], data.get("explanation", "")
            except json.JSONDecodeError:
                continue
        
        return None
    
    def _format_tool_results(self, tool_results: List[Dict[str, Any]]) -> str:
        """
        Format tool results for next prompt.
        
        Limits output size to prevent context overflow.
        """
        formatted = []
        total_chars = 0
        
        for i, result in enumerate(tool_results, 1):
            tool_name = result["tool"]
            parameters = result["parameters"]
            tool_result = result["result"]
            
            # Get output and error text
            output_text = tool_result.get('output', '')
            error_text = tool_result.get('error', '')
            
            # Truncate output if too long
            original_output_len = len(output_text)
            if len(output_text) > self.max_tool_output_chars:
                output_text = output_text[:self.max_tool_output_chars]
                output_text += f"\n\n... (truncated, showing first {self.max_tool_output_chars} characters of {original_output_len} total)"
                logger.warning(
                    f"Tool '{tool_name}' output truncated from {original_output_len} to {self.max_tool_output_chars} chars"
                )
            
            # Build formatted result
            result_text = f"""Tool Call #{i}: {tool_name}
Parameters: {json.dumps(parameters, indent=2)}
Success: {tool_result['success']}
Output:
{output_text}
{f"Error: {error_text}" if error_text else ""}
"""
            
            # Check if adding this result would exceed total limit
            result_chars = len(result_text)
            if total_chars + result_chars > self.max_total_tool_results_chars:
                remaining_chars = self.max_total_tool_results_chars - total_chars
                if remaining_chars > 100:  # Only add if there's meaningful space
                    # Truncate this result
                    result_text = result_text[:remaining_chars]
                    result_text += f"\n\n... (truncated due to total size limit)"
                    formatted.append(result_text)
                    logger.warning(
                        f"Tool results truncated: reached total limit of {self.max_total_tool_results_chars} chars"
                    )
                break
            
            formatted.append(result_text)
            total_chars += result_chars
        
        return "\n---\n".join(formatted)
