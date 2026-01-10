"""
Tool calling demo for CLIS.

This script demonstrates how the tool calling system works.
"""

from clis.agent.tool_calling import ToolCallingAgent
from clis.config import ConfigManager
from clis.tools.builtin import (
    ListFilesTool,
    ReadFileTool,
    GitStatusTool,
    DockerPsTool,
)


def demo_basic_tool_calling():
    """Demonstrate basic tool calling."""
    print("=" * 60)
    print("DEMO 1: Basic Tool Calling")
    print("=" * 60)
    
    # Initialize
    config_manager = ConfigManager()
    tools = [
        ListFilesTool(),
        GitStatusTool(),
    ]
    
    agent = ToolCallingAgent(
        config_manager=config_manager,
        tools=tools,
        max_iterations=5
    )
    
    # Query
    query = "List all Python files in the current directory"
    
    system_prompt = """
You are a helpful assistant that can use tools to gather information.

Generate shell commands based on the user's request.
"""
    
    print(f"\nUser Query: {query}")
    print("\nExecuting with tool calling...")
    
    commands, explanation, tool_calls = agent.execute_with_tools(
        query=query,
        system_prompt=system_prompt
    )
    
    print(f"\nTool Calls Made: {len(tool_calls)}")
    for i, call in enumerate(tool_calls, 1):
        print(f"  {i}. {call['tool']}({call['parameters']})")
        if call['success']:
            output_preview = call['output'][:100] + "..." if len(call['output']) > 100 else call['output']
            print(f"     ✓ {output_preview}")
        else:
            print(f"     ✗ {call['error']}")
    
    print(f"\nGenerated Commands:")
    for i, cmd in enumerate(commands, 1):
        print(f"  {i}. {cmd}")
    
    print(f"\nExplanation: {explanation}")


def demo_git_operations():
    """Demonstrate git operations with tool calling."""
    print("\n" + "=" * 60)
    print("DEMO 2: Git Operations with Tool Calling")
    print("=" * 60)
    
    config_manager = ConfigManager()
    tools = [
        ListFilesTool(),
        GitStatusTool(),
    ]
    
    agent = ToolCallingAgent(
        config_manager=config_manager,
        tools=tools,
        max_iterations=5
    )
    
    query = "Commit all modified Python files"
    
    system_prompt = """
You are a Git expert assistant.

When the user asks to commit files:
1. Use git_status tool to see what files are modified
2. Use list_files tool to find Python files
3. Generate precise git commands based on actual files

Generate commands in JSON format.
"""
    
    print(f"\nUser Query: {query}")
    print("\nExecuting with tool calling...")
    
    commands, explanation, tool_calls = agent.execute_with_tools(
        query=query,
        system_prompt=system_prompt
    )
    
    print(f"\nTool Calls Made: {len(tool_calls)}")
    for i, call in enumerate(tool_calls, 1):
        status = "✓" if call['success'] else "✗"
        print(f"  {status} {i}. {call['tool']}({call['parameters']})")
    
    print(f"\nGenerated Commands:")
    for i, cmd in enumerate(commands, 1):
        print(f"  {i}. {cmd}")
    
    print(f"\nExplanation: {explanation}")


def demo_docker_operations():
    """Demonstrate Docker operations with tool calling."""
    print("\n" + "=" * 60)
    print("DEMO 3: Docker Operations with Tool Calling")
    print("=" * 60)
    
    config_manager = ConfigManager()
    tools = [
        DockerPsTool(),
    ]
    
    agent = ToolCallingAgent(
        config_manager=config_manager,
        tools=tools,
        max_iterations=5
    )
    
    query = "Restart the web container"
    
    system_prompt = """
You are a Docker expert assistant.

When the user asks to manage containers:
1. Use docker_ps tool to see what containers are running
2. Identify the correct container based on the user's description
3. Generate precise docker commands

Generate commands in JSON format.
"""
    
    print(f"\nUser Query: {query}")
    print("\nExecuting with tool calling...")
    
    commands, explanation, tool_calls = agent.execute_with_tools(
        query=query,
        system_prompt=system_prompt
    )
    
    print(f"\nTool Calls Made: {len(tool_calls)}")
    for i, call in enumerate(tool_calls, 1):
        status = "✓" if call['success'] else "✗"
        print(f"  {status} {i}. {call['tool']}({call['parameters']})")
        if call['success'] and call['output']:
            print(f"     Output: {call['output'][:100]}...")
    
    print(f"\nGenerated Commands:")
    for i, cmd in enumerate(commands, 1):
        print(f"  {i}. {cmd}")
    
    print(f"\nExplanation: {explanation}")


def main():
    """Run all demos."""
    print("\n" + "=" * 60)
    print("CLIS Tool Calling System Demo")
    print("=" * 60)
    
    try:
        # Demo 1: Basic tool calling
        demo_basic_tool_calling()
        
        # Demo 2: Git operations
        demo_git_operations()
        
        # Demo 3: Docker operations (may fail if Docker not running)
        try:
            demo_docker_operations()
        except Exception as e:
            print(f"\nDocker demo skipped: {e}")
        
        print("\n" + "=" * 60)
        print("All demos completed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nError running demos: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
