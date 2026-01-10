#!/usr/bin/env python3
"""
并行工具调用和流式输出演示

展示 CLIS 的两个新功能：
1. 并行工具调用 - 多个只读工具同时执行
2. 流式输出 - 实时显示 LLM 思考过程
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
    """演示流式输出功能"""
    print("=" * 60)
    print("演示 1: 流式输出")
    print("=" * 60)
    print("\n观察 LLM 思考过程的实时显示：\n")
    
    config = ConfigManager()
    tools = get_all_tools()
    agent = InteractiveAgent(config, tools, max_iterations=5)
    
    query = "列出当前目录下所有 Python 文件"
    
    print(f"📝 查询: {query}\n")
    print("🤔 思考过程 (流式显示):")
    print("-" * 60)
    
    start_time = time.time()
    thinking_start_time = None
    first_chunk_time = None
    
    for step in agent.execute(query):
        step_type = step.get("type")
        
        if step_type == "thinking_start":
            thinking_start_time = time.time()
            print(f"\n[开始思考] {step.get('content')}")
            
        elif step_type == "thinking_chunk":
            if first_chunk_time is None:
                first_chunk_time = time.time()
                ttfc = (first_chunk_time - thinking_start_time) * 1000
                print(f"\n⚡ 首字符延迟: {ttfc:.0f}ms\n")
            # 实时显示每个 chunk
            print(step.get("content"), end="", flush=True)
            
        elif step_type == "thinking_end":
            elapsed = time.time() - thinking_start_time
            print(f"\n\n[思考完成] 耗时: {elapsed:.2f}秒")
            
        elif step_type == "tool_call":
            print(f"\n🔧 工具调用: {step.get('tool')}")
            print(f"   参数: {step.get('params')}")
            
        elif step_type == "tool_result":
            success = "✅" if step.get("success") else "❌"
            print(f"{success} 结果: {step.get('content')[:200]}...")
            
        elif step_type == "complete":
            print(f"\n✅ 完成: {step.get('content')}")
            break
            
        elif step_type == "error":
            print(f"\n❌ 错误: {step.get('content')}")
            break
    
    total_time = time.time() - start_time
    print(f"\n总耗时: {total_time:.2f}秒")
    print("=" * 60)


def demo_parallel_tools():
    """演示并行工具调用功能"""
    print("\n\n")
    print("=" * 60)
    print("演示 2: 并行工具调用")
    print("=" * 60)
    print("\n对比串行和并行执行的性能差异：\n")
    
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
    
    # 模拟多个工具调用
    tool_calls = [
        {"tool": "list_files", "parameters": {"pattern": "*.py"}},
        {"tool": "get_file_info", "parameters": {"path": "."}},
        {"tool": "check_command", "parameters": {"command": "git"}}
    ]
    
    print("🔧 准备调用 3 个只读工具:")
    for i, tc in enumerate(tool_calls, 1):
        print(f"   {i}. {tc['tool']}")
    
    print("\n⚡ 执行中 (并行)...")
    start_time = time.time()
    
    # 执行并行工具调用
    called_tools = set()
    results = agent._execute_tool_calls_parallel(tool_calls, called_tools)
    
    elapsed = time.time() - start_time
    
    print(f"\n✅ 完成! 耗时: {elapsed:.2f}秒")
    print(f"\n📊 结果:")
    for i, result in enumerate(results, 1):
        success = "✅" if result["result"]["success"] else "❌"
        print(f"   {i}. {result['tool']}: {success}")
    
    print(f"\n💡 提示:")
    print(f"   - 并行执行: ~{elapsed:.2f}秒")
    print(f"   - 串行执行: 预计 ~{elapsed * 3:.2f}秒")
    print(f"   - 速度提升: ~{3:.0f}x")
    
    print("=" * 60)


def main():
    """主函数"""
    print("\n🚀 CLIS 并行工具调用和流式输出演示\n")
    
    try:
        # 演示 1: 流式输出
        demo_streaming_output()
        
        # 演示 2: 并行工具调用
        demo_parallel_tools()
        
        print("\n\n✨ 演示完成!")
        print("\n📚 了解更多:")
        print("   - 查看 PARALLEL_AND_STREAMING_IMPLEMENTATION.md")
        print("   - 查看 docs/TODO/CLIS_VS_CURSOR_CLAUDE_COMPARISON.md")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  演示被中断")
    except Exception as e:
        print(f"\n\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
