"""
Quick comparison test - Single simple scenario

Used to quickly verify if the test framework works
"""

import sys
from pathlib import Path

# Add project path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from test_agent_comparison import AgentComparison


def quick_test():
    """Quick test: Create a simple file"""
    print("\n" + "="*60)
    print("QUICK COMPARISON TEST")
    print("="*60 + "\n")
    
    comparison = AgentComparison()
    
    # Scenario: Create simple file
    test_file = comparison.test_root / "quick_test" / "hello.txt"
    query = f"Create a text file at {test_file} with content 'Hello from CLIS!'"
    
    results = comparison.compare_scenario("Quick Test", query)
    
    # Display detailed results
    print("\n" + "="*60)
    print("DETAILED RESULTS")
    print("="*60)
    
    for mode, result in results.items():
        print(f"\n{mode.upper()}:")
        print(f"  Success: {result.success}")
        print(f"  Time: {result.execution_time:.2f}s")
        print(f"  Operations: {result.operation_count}")
        print(f"  Tool calls: {[t['tool'] for t in result.tool_calls]}")
        if result.error:
            print(f"  Error: {result.error}")
        if result.memory_stats:
            print(f"  Memory stats: {result.memory_stats}")
    
    # Save results
    comparison.save_results("tests/quick_test_results.json")
    
    # Generate report
    report = comparison.generate_report()
    print("\n" + "="*60)
    print("REPORT")
    print("="*60)
    print(report)
    
    return comparison


if __name__ == "__main__":
    try:
        comparison = quick_test()
        print("\n✓ Quick test completed successfully!")
        print(f"Test directory: {comparison.test_root}")
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
