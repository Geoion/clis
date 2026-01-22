#!/usr/bin/env python3
"""
Memory System Demo

Demonstrates how to use CLIS's hybrid memory system to manage Agent tasks.
"""

from clis.agent import (
    WorkingMemory,
    EpisodicMemory,
    TaskStateMachine,
    MemoryManager,
)


def demo_working_memory():
    """Demonstrate working memory usage"""
    print("=" * 60)
    print("1. WorkingMemory - Track Operation History")
    print("=" * 60)
    
    wm = WorkingMemory()
    
    # Simulate file reads
    print("\n📂 Reading files:")
    wm.add_file_read("src/main.py")
    wm.add_file_read("src/utils.py")
    print("  ✓ Read src/main.py")
    print("  ✓ Read src/utils.py")
    
    # Detect duplicates
    is_new = wm.add_file_read("src/main.py")
    if not is_new:
        print("  ⚠️  Duplicate read of src/main.py!")
    
    # Record writes
    print("\n✏️  Writing files:")
    wm.add_file_written("src/main.py")
    print("  ✓ Wrote src/main.py")
    
    # Record commands
    print("\n⚙️  Executing commands:")
    wm.add_command("pytest tests/", True)
    print("  ✓ pytest tests/ (success)")
    
    # Tool statistics
    wm.increment_tool("read_file")
    wm.increment_tool("read_file")
    wm.increment_tool("write_file")
    
    # Show summary
    print("\n" + wm.to_prompt(max_items=5))
    
    # Loop detection
    print("\n🔍 Testing loop detection:")
    wm_loop = WorkingMemory()
    for _ in range(4):
        wm_loop.add_file_read("loop.py")
    
    is_loop, reason = wm_loop.detect_loop()
    if is_loop:
        print(f"  ⚠️  {reason}")


def demo_episodic_memory():
    """Demonstrate episodic memory usage"""
    print("\n\n" + "=" * 60)
    print("2. EpisodicMemory - Task Document Management")
    print("=" * 60)
    
    import tempfile
    import shutil
    
    # Use temporary directory
    temp_dir = tempfile.mkdtemp()
    
    try:
        em = EpisodicMemory("demo_task", memory_dir=temp_dir)
        em.load_or_create("Demo task: Implement user authentication")
        
        print("\n📋 Task created successfully")
        print(f"   File: {em.get_file_path()}")
        
        # Update steps
        print("\n✅ Updating task steps:")
        em.update_step("Analyze requirements", "done")
        print("  ✓ Analyze requirements")
        
        em.update_step("Design database model", "done")
        print("  ✓ Design database model")
        
        em.update_step("Implement authentication logic", "in_progress")
        print("  🔄 Implement authentication logic")
        
        # Record findings
        print("\n🔍 Recording key findings:")
        em.add_finding("Need to use bcrypt for password encryption", category="security")
        print("  ✓ [security] Need to use bcrypt for password encryption")
        
        em.add_finding("Database table: users(id, username, password_hash)", category="database")
        print("  ✓ [database] Database table structure")
        
        # Update progress
        em.update_progress("execution", "2/3")
        em.update_next_action("Complete authentication logic implementation and write tests")
        
        print("\n📖 Task document preview:")
        print(em.inject_to_prompt(include_log=False))
        
    finally:
        # Cleanup
        shutil.rmtree(temp_dir)


def demo_state_machine():
    """Demonstrate state machine usage"""
    print("\n\n" + "=" * 60)
    print("3. TaskStateMachine - State Guidance")
    print("=" * 60)
    
    wm = WorkingMemory()
    sm = TaskStateMachine(max_iterations=20)
    
    # Initial phase
    print("\n🟢 Iteration 0 - Initialization:")
    advice = sm.detect_state(0, wm)
    print(f"   State: {advice.state.value}")
    print(f"   Suggestion: {advice.suggested_actions[0]}")
    
    # Information gathering
    print("\n🔵 Iteration 2 - Information gathering:")
    for i in range(3):
        wm.add_file_read(f"file{i}.py")
    advice = sm.detect_state(2, wm)
    print(f"   State: {advice.state.value}")
    print(f"   Files read: {len(wm.files_read)}")
    
    # Analysis phase
    print("\n🟡 Iteration 5 - Analysis phase:")
    for i in range(3):
        wm.add_file_read(f"extra{i}.py")
    advice = sm.detect_state(5, wm)
    print(f"   State: {advice.state.value}")
    print(f"   Files read: {len(wm.files_read)}")
    
    # Loop detection
    print("\n🔴 Loop detection:")
    wm_loop = WorkingMemory()
    for _ in range(4):
        wm_loop.add_file_read("same.py")
    
    advice = sm.detect_state(7, wm_loop)
    print(f"   State: {advice.state.value}")
    print(f"   Urgent: {advice.is_urgent}")
    print(f"   Message: {advice.message}")


def demo_memory_manager():
    """Demonstrate memory manager usage"""
    print("\n\n" + "=" * 60)
    print("4. MemoryManager - Lifecycle Management")
    print("=" * 60)
    
    import tempfile
    import shutil
    
    # Use temporary directory
    temp_dir = tempfile.mkdtemp()
    
    try:
        mm = MemoryManager(memory_dir=temp_dir)
        
        # Create tasks
        print("\n📝 Creating tasks:")
        task_id1, _ = mm.create_task_memory("Task 1: Add logging functionality")
        print(f"  ✓ {task_id1}")
        
        task_id2, _ = mm.create_task_memory("Task 2: Fix login bug")
        print(f"  ✓ {task_id2}")
        
        # List tasks
        print("\n📋 Listing tasks:")
        tasks = mm.list_tasks()
        for task in tasks:
            print(f"  • {task['id']}: {task['description']}")
        
        # Complete task
        print("\n✅ Completing task:")
        mm.complete_task(task_id1, success=True)
        print(f"  ✓ {task_id1} completed")
        
        # Statistics
        print("\n📊 Statistics:")
        stats = mm.get_stats()
        print(f"  Total: {stats['total']}")
        print(f"  Active: {stats['active']}")
        print(f"  Completed: {stats['completed']}")
        
        # Search
        print("\n🔍 Searching tasks:")
        results = mm.search_tasks("logging")
        for result in results:
            print(f"  • {result['id']}: {result['description']}")
        
    finally:
        # Cleanup
        shutil.rmtree(temp_dir)


def demo_integration():
    """Demonstrate integrated usage"""
    print("\n\n" + "=" * 60)
    print("5. Integrated Usage - Complete Workflow")
    print("=" * 60)
    
    import tempfile
    import shutil
    from datetime import datetime
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # 1. Create manager and task
        print("\n1️⃣ Initialization:")
        mm = MemoryManager(memory_dir=temp_dir)
        task_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        _, task_file = mm.create_task_memory("Implement search functionality", task_id)
        
        # 2. Create memory components
        wm = WorkingMemory()
        em = EpisodicMemory(task_id, memory_dir=temp_dir)
        em.load_or_create("Implement search functionality")
        sm = TaskStateMachine(max_iterations=10)
        
        print("  ✓ Task memory system initialized")
        
        # 3. Simulate task execution
        print("\n2️⃣ Executing task:")
        
        # Iteration 0: Gather information
        print("  Iteration 0 - Read documentation")
        wm.add_file_read("docs/api.md")
        wm.increment_tool("read_file")
        em.update_step("Read API documentation", "done")
        em.add_finding("API uses Elasticsearch", category="tech")
        
        # Iteration 1: Continue gathering
        print("  Iteration 1 - Read code")
        wm.add_file_read("src/search.py")
        wm.increment_tool("read_file")
        em.update_step("Analyze existing search code", "done")
        
        # Iteration 2: Implement functionality
        print("  Iteration 2 - Implement functionality")
        wm.add_file_written("src/search_new.py")
        wm.increment_tool("write_file")
        em.update_step("Implement new search functionality", "done")
        em.add_finding("Implemented full-text search and filtering", category="feature")
        
        # 4. Check state
        print("\n3️⃣ State check:")
        advice = sm.detect_state(2, wm)
        print(f"  Current state: {advice.state.value}")
        print(f"  Is urgent: {advice.is_urgent}")
        
        # 5. Show memory
        print("\n4️⃣ Working memory summary:")
        stats = wm.get_stats()
        print(f"  Files read: {stats['files_read_count']}")
        print(f"  Files written: {stats['files_written_count']}")
        print(f"  Tool usage: {stats['tools_used']}")
        
        # 6. Complete task
        print("\n5️⃣ Completing task:")
        em.update_step("Task completed", "done")
        em.update_next_action("✅ Search functionality implemented")
        mm.complete_task(task_id, success=True)
        print("  ✓ Task marked as completed")
        
        # 7. Final statistics
        print("\n6️⃣ Final statistics:")
        final_stats = mm.get_stats()
        print(f"  Total tasks: {final_stats['total']}")
        print(f"  Completed: {final_stats['completed']}")
        
    finally:
        shutil.rmtree(temp_dir)


if __name__ == "__main__":
    print("🧪 CLIS Memory System Demo\n")
    
    demo_working_memory()
    demo_episodic_memory()
    demo_state_machine()
    demo_memory_manager()
    demo_integration()
    
    print("\n\n" + "=" * 60)
    print("✅ Demo completed!")
    print("=" * 60)
    print("\n💡 Tips:")
    print("  • Use 'clis memory list' to view tasks")
    print("  • Use 'clis memory stats' to view statistics")
    print("  • View documentation: docs/MEMORY_SYSTEM.md")
    print()
