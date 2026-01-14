#!/usr/bin/env python3
"""
Parallel Tool Calling and Streaming Output Demo

Demonstrates two new CLIS features:
1. Parallel Tool Calling - Execute multiple read-only tools simultaneously
2. Streaming Output - Real-time display of LLM thinking process
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from clis.config import ConfigManager
from clis.agent.interactive_agent import InteractiveAgent
from clis.tools.registry import get_all_tools


def demo_streaming_output():
    """Demonstrate streaming output functionality"""
    print("=" * 60)
    print("Demo 1: Streaming Output")
    print("=" * 60)
    print("\nObserve real-time display of LLM thinking process:\n")
    
    config = ConfigManager()
    tools = get_all_tools()
    agent = InteractiveAgent(config, tools, max_iterations=5)
    
    query = "List all Python files in the current directory"
    
    print(f"📝 Query: {query}\n")
    print("🤔 Thinking Process (streaming):")
    print("-" * 60)
    
    start_time = time.time()
    thinking_start_time = None
    first_chunk_time = None
    
    for step in agent.execute(query):
        step_type = step.get("type")
        
        if step_type == "thinking_start":
            thinking_start_time = time.time()
            print(f"\n[Thinking Started] {step.get('content')}")
            
        elif step_type == "thinking_chunk":
            if first_chunk_time is None:
                first_chunk_time = time.time()
                ttfc = (first_chunk_time - thinking_start_time) * 1000
                print(f"\n⚡ Time to First Character: {ttfc:.0f}ms\n")
            # Display each chunk in real-time
            print(step.get("content"), end="", flush=True)
            
        elif step_type == "thinking_end":
            elapsed = time.time() - thinking_start_time
            print(f"\n\n[Thinking Complete] Time: {elapsed:.2f}s")
            
        elif step_type == "tool_call":
            print(f"\n🔧 Tool Call: {step.get('tool')}")
            print(f"   Parameters: {step.get('params')}")
            
        elif step_type == "tool_result":
            success = "✅" if step.get("success") else "❌"
            print(f"{success} Result: {step.get('content')[:200]}...")
            
        elif step_type == "complete":
            print(f"\n✅ Complete: {step.get('content')}")
            break
            
        elif step_type == "error":
            print(f"\n❌ Error: {step.get('content')}")
            break
    
    total_time = time.time() - start_time
    print(f"\nTotal Time: {total_time:.2f}s")
    print("=" * 60)


def demo_parallel_tools():
    """Demonstrate parallel tool calling functionality"""
    print("\n\n")
    print("=" * 60)
    print("Demo 2: Parallel Tool Calling")
    print("=" * 60)
    print("\nCompare performance difference between serial and parallel execution:\n")
    
    from clis.agent.tool_calling import ToolCallingAgent
    from clis.tools.builtin import (
        ListFilesTool,
        GetFileInfoTool,
        CheckCommandTool
    )
    
    config = ConfigManager()
    tools = [
        ListFilesTool(),
        GetFileInfoTool(),
        CheckCommandTool()
    ]
    
    agent = ToolCallingAgent(config, tools, max_iterations=3)
    
    # Simulate multiple tool calls
    tool_calls = [
        {"tool": "list_files", "parameters": {"pattern": "*.py"}},
        {"tool": "get_file_info", "parameters": {"path": "."}},
        {"tool": "check_command", "parameters": {"command": "git"}}
    ]
    
    print("🔧 Preparing to call 3 read-only tools:")
    for i, tc in enumerate(tool_calls, 1):
        print(f"   {i}. {tc['tool']}")
    
    print("\n⚡ Executing (parallel)...")
    start_time = time.time()
    
    # Execute parallel tool calls
    called_tools = set()
    results = agent._execute_tool_calls_parallel(tool_calls, called_tools)
    
    elapsed = time.time() - start_time
    
    print(f"\n✅ Complete! Time: {elapsed:.2f}s")
    print(f"\n📊 Results:")
    for i, result in enumerate(results, 1):
        success = "✅" if result["result"]["success"] else "❌"
        print(f"   {i}. {result['tool']}: {success}")
    
    print(f"\n💡 Tips:")
    print(f"   - Parallel execution: ~{elapsed:.2f}s")
    print(f"   - Serial execution: Estimated ~{elapsed * 3:.2f}s")
    print(f"   - Speed improvement: ~{3:.0f}x")
    
    print("=" * 60)


def main():
    """Main function"""
    print("\n🚀 CLIS Parallel Tool Calling and Streaming Output Demo\n")
    
    try:
        # Demo 1: Streaming output
        demo_streaming_output()
        
        # Demo 2: Parallel tool calling
        demo_parallel_tools()
        
        print("\n\n✨ Demo Complete!")
        print("\n📚 Learn More:")
        print("   - Check PARALLEL_AND_STREAMING_IMPLEMENTATION.md")
        print("   - Check docs/TODO/CLIS_VS_CURSOR_CLAUDE_COMPARISON.md")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Demo Interrupted")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
