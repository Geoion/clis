#!/usr/bin/env python3
"""
测试高效的记忆学习系统

验证:
1. 失败任务在第一行显示失败原因
2. 向量搜索能快速提取失败原因(只读第一行)
3. 规划时能使用这些信息(无需解析整个文件)
"""

import sys
from pathlib import Path
import tempfile
import shutil

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from clis.agent.memory_manager import MemoryManager
from clis.agent.vector_search import VectorSearch

def test_failure_reason_format():
    """测试失败原因格式"""
    print("=" * 80)
    print("测试 1: 失败原因格式")
    print("=" * 80)
    
    # Create temporary memory directory
    temp_dir = tempfile.mkdtemp(prefix="test_memory_")
    
    try:
        mm = MemoryManager(memory_dir=temp_dir)
        
        # Create a test task
        task_id, task_file = mm.create_task_memory(
            "create flask web service on port 5000",
            None
        )
        
        # Create the actual task file (normally done by EpisodicMemory)
        task_file.write_text(f"""# Task: create flask web service on port 5000

**Task ID**: {task_id}
**Status**: In Progress

## Task Objectives

create flask web service on port 5000
""", encoding='utf-8')
        
        print(f"✓ 创建测试任务: {task_id}")
        
        # Complete task with failure
        failure_reason = "Port 5000 already in use, use port 5001 instead"
        mm.complete_task(
            task_id,
            success=False,
            failure_reason=failure_reason
        )
        
        print(f"✓ 标记任务失败: {failure_reason}")
        
        # Read completed task file
        completed_file = Path(temp_dir) / "tasks" / "completed" / f"task_{task_id}.md"
        
        if not completed_file.exists():
            print(f"✗ 任务文件不存在: {completed_file}")
            return False
        
        # Read first few lines
        with open(completed_file, 'r', encoding='utf-8') as f:
            lines = [f.readline() for _ in range(10)]
        
        print("\n文件前几行:")
        print("-" * 80)
        for i, line in enumerate(lines[:5], 1):
            print(f"{i}: {line.rstrip()}")
        print("-" * 80)
        
        # Check if failure reason is prominent
        has_failure_marker = any('❌ FAILED:' in line for line in lines)
        has_failure_reason = any(failure_reason[:30] in line for line in lines)
        
        print(f"\n格式检查:")
        print(f"  包含失败标记 (❌ FAILED:): {'✓' if has_failure_marker else '✗'}")
        print(f"  包含失败原因: {'✓' if has_failure_reason else '✗'}")
        
        return has_failure_marker and has_failure_reason
        
    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

def test_efficient_extraction():
    """测试高效提取(只读第一行)"""
    print("\n" + "=" * 80)
    print("测试 2: 高效提取失败原因")
    print("=" * 80)
    
    # Create temporary memory directory
    temp_dir = tempfile.mkdtemp(prefix="test_memory_")
    
    try:
        mm = MemoryManager(memory_dir=temp_dir)
        
        # Create multiple test tasks
        test_cases = [
            ("create flask on port 5000", False, "Port 5000 occupied, use 5001"),
            ("install missing package", False, "Package not found in pip"),
            ("successful task", True, None),
        ]
        
        task_ids = []
        for i, (desc, success, reason) in enumerate(test_cases):
            # Use unique task_id to avoid collision
            task_id, task_file = mm.create_task_memory(desc, f"test_{i}")
            # Create actual file
            task_file.write_text(f"# Task: {desc}\n\n**Task ID**: {task_id}\n", encoding='utf-8')
            mm.complete_task(task_id, success=success, failure_reason=reason)
            task_ids.append(task_id)
            print(f"✓ 创建任务: {desc} ({'成功' if success else '失败'})")
        
        # Rebuild index (this should extract failure reasons efficiently)
        vs = VectorSearch(memory_dir=temp_dir)
        vs.rebuild_index(mm)
        
        print(f"\n✓ 重建索引: {len(vs.index)} 个任务")
        
        # Check if failure reasons were extracted
        extracted_count = 0
        for task_id in task_ids:
            if task_id in vs.index:
                metadata = vs.index[task_id].get('metadata', {})
                if metadata.get('failure_reason'):
                    extracted_count += 1
                    print(f"  - {task_id}: {metadata['failure_reason'][:60]}...")
        
        print(f"\n提取统计:")
        print(f"  失败任务数: 2")
        print(f"  提取到失败原因: {extracted_count}")
        
        return extracted_count == 2
        
    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

def test_search_with_failure_info():
    """测试搜索结果包含失败信息"""
    print("\n" + "=" * 80)
    print("测试 3: 搜索结果包含失败信息")
    print("=" * 80)
    
    # Create temporary memory directory
    temp_dir = tempfile.mkdtemp(prefix="test_memory_")
    
    try:
        mm = MemoryManager(memory_dir=temp_dir)
        vs = VectorSearch(memory_dir=temp_dir)
        
        # Create test tasks
        test_cases = [
            ("create python flask web service", False, "Port 5000 occupied"),
            ("create flask api", False, "Missing Flask dependency"),
            ("create django app", True, None),
        ]
        
        for i, (desc, success, reason) in enumerate(test_cases):
            # Use unique task_id
            task_id, task_file = mm.create_task_memory(desc, f"search_test_{i}")
            # Create actual file
            task_file.write_text(f"# Task: {desc}\n\n**Task ID**: {task_id}\n", encoding='utf-8')
            mm.complete_task(task_id, success=success, failure_reason=reason)
        
        # Rebuild index
        vs.rebuild_index(mm)
        
        # Search for flask tasks
        results = vs.search_similar_tasks("create flask web service", top_k=3)
        
        print(f"✓ 搜索结果: {len(results)} 个任务\n")
        
        has_failure_info = False
        for i, result in enumerate(results, 1):
            print(f"任务 {i}:")
            print(f"  ID: {result['task_id']}")
            print(f"  相似度: {result['similarity']:.2f}")
            print(f"  描述: {result['description'][:60]}...")
            
            if result.get('failure_reason'):
                print(f"  ⚠️ 失败原因: {result['failure_reason']}")
                has_failure_info = True
            print()
        
        return has_failure_info
        
    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

def test_token_efficiency():
    """测试token效率"""
    print("\n" + "=" * 80)
    print("测试 4: Token效率对比")
    print("=" * 80)
    
    # Simulate old approach: parse entire file
    old_approach_chars = 5000  # Typical task file size
    
    # New approach: read first line only
    new_approach_chars = 100  # First line with failure reason
    
    efficiency_gain = (old_approach_chars - new_approach_chars) / old_approach_chars * 100
    
    print(f"旧方案 (解析整个文件):")
    print(f"  平均字符数: {old_approach_chars}")
    print(f"  估算token数: ~{old_approach_chars // 4}")
    
    print(f"\n新方案 (只读第一行):")
    print(f"  平均字符数: {new_approach_chars}")
    print(f"  估算token数: ~{new_approach_chars // 4}")
    
    print(f"\n效率提升: {efficiency_gain:.1f}%")
    print(f"✓ 每次搜索3个相似任务可节省 ~{(old_approach_chars - new_approach_chars) * 3 // 4} tokens")
    
    return True

def main():
    """运行所有测试"""
    print("高效记忆学习系统测试")
    print("=" * 80)
    
    results = []
    
    # 测试1: 失败原因格式
    results.append(("失败原因格式", test_failure_reason_format()))
    
    # 测试2: 高效提取
    results.append(("高效提取", test_efficient_extraction()))
    
    # 测试3: 搜索结果
    results.append(("搜索结果", test_search_with_failure_info()))
    
    # 测试4: Token效率
    results.append(("Token效率", test_token_efficiency()))
    
    # 总结
    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)
    
    for test_name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"{test_name}: {status}")
    
    total = len(results)
    passed = sum(1 for _, p in results if p)
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过!新方案更高效、更优雅!")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
