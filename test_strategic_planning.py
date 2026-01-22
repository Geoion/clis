#!/usr/bin/env python3
"""
Test Strategic Planning with Read-Only Exploration

This script tests the new architecture:
- Phase 1.1: Read-only exploration
- Phase 1.2: Strategic guidance
- Phase 2: ReAct execution

Test Scenario: Analyze TODO comments and create priority report
"""

import sys
import time
from datetime import datetime

def print_section(title):
    """Print a formatted section header"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80 + "\n")

def print_step(step_num, description):
    """Print a test step"""
    print(f"\n[Step {step_num}] {description}")
    print("-" * 60)

def record_observation(category, observation):
    """Record an observation for later analysis"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"  📝 [{category}] {observation}")
    return {
        "timestamp": timestamp,
        "category": category,
        "observation": observation
    }

def main():
    print_section("Strategic Planning Architecture Test")
    
    print("Test Scenario:")
    print("  Task: Analyze TODO comments in src/clis/agent/")
    print("  Expected: Find TODOs, categorize by priority, show top 3")
    print()
    
    observations = []
    
    # Test configuration
    test_command = 'clis run "analyze all TODO comments in src/clis/agent/ directory, categorize them by priority (HIGH/MEDIUM/LOW based on keywords like urgent, critical, fix for HIGH; should, consider, improve for MEDIUM; nice, optional, future for LOW), and create a report showing the top 3 most important ones with their file locations and descriptions"'
    
    print_step(1, "Prepare Test Environment")
    print(f"  Command: {test_command}")
    print(f"  Working Directory: src/clis/agent/")
    print(f"  Expected Files: agent.py, pevl_agent.py, planner.py, etc.")
    
    observations.append(record_observation(
        "SETUP",
        "Test command prepared with detailed task description"
    ))
    
    print_step(2, "Expected Phase 1.1: Read-Only Exploration")
    print("  Expected explorations:")
    print("    1. file_tree src/clis/agent/ (understand structure)")
    print("    2. grep 'TODO' src/clis/agent/ (find all TODOs)")
    print("    3. read_file on files with TODOs (get context)")
    print()
    print("  What to observe:")
    print("    ✓ Does it use read-only tools?")
    print("    ✓ Does it limit to 3-5 explorations?")
    print("    ✓ Does it gather relevant context?")
    print("    ✓ Does it stop when enough info collected?")
    
    observations.append(record_observation(
        "EXPECTATION",
        "Phase 1.1 should explore with read-only tools (max 5 steps)"
    ))
    
    print_step(3, "Expected Phase 1.2: Strategic Guidance")
    print("  Expected outputs:")
    print("    - Recommended tools: grep, read_file, write_file")
    print("    - Step guidance:")
    print("      1. Goal: Find all TODOs")
    print("         Success: List with file:line and context")
    print("      2. Goal: Categorize by priority")
    print("         Success: Each TODO has HIGH/MEDIUM/LOW label")
    print("      3. Goal: Show top 3")
    print("         Success: Report with top 3 TODOs")
    print("    - Lessons: Avoid complex inline Python scripts")
    print()
    print("  What to observe:")
    print("    ✓ Does guidance reference exploration findings?")
    print("    ✓ Are recommended tools appropriate?")
    print("    ✓ Are success criteria clear?")
    print("    ✓ Are considerations helpful?")
    
    observations.append(record_observation(
        "EXPECTATION",
        "Phase 1.2 should provide strategic guidance based on exploration"
    ))
    
    print_step(4, "Expected Phase 2: ReAct Execution")
    print("  Expected behavior:")
    print("    - Start ReAct from first step (no fixed plan)")
    print("    - Use exploration context and guidance")
    print("    - Flexibly choose tools based on results")
    print("    - Apply backup strategies if needed")
    print()
    print("  What to observe:")
    print("    ✓ Does it start ReAct immediately?")
    print("    ✓ Does it reference guidance goals?")
    print("    ✓ Does it adapt based on actual results?")
    print("    ✓ Does it avoid complex inline Python scripts?")
    print("    ✓ Does it achieve the overall goal?")
    
    observations.append(record_observation(
        "EXPECTATION",
        "Phase 2 should execute with full ReAct autonomy"
    ))
    
    print_step(5, "Run Test")
    print("  Execute the command and observe each phase...")
    print()
    print(f"  $ {test_command}")
    print()
    print("  Press Ctrl+C to stop and analyze observations")
    print()
    
    # Record start time
    start_time = time.time()
    
    try:
        import subprocess
        result = subprocess.run(
            test_command,
            shell=True,
            capture_output=False,
            text=True,
            timeout=300  # 5 minutes timeout
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        observations.append(record_observation(
            "RESULT",
            f"Test completed in {duration:.1f}s with exit code {result.returncode}"
        ))
        
    except subprocess.TimeoutExpired:
        observations.append(record_observation(
            "ERROR",
            "Test timed out after 5 minutes"
        ))
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        observations.append(record_observation(
            "INTERRUPTED",
            "Test stopped by user"
        ))
    except Exception as e:
        observations.append(record_observation(
            "ERROR",
            f"Test failed with error: {str(e)}"
        ))
    
    # Analysis section
    print_section("Test Analysis & Observations")
    
    print("Recorded Observations:")
    for i, obs in enumerate(observations, 1):
        print(f"\n{i}. [{obs['timestamp']}] {obs['category']}")
        print(f"   {obs['observation']}")
    
    print_section("Areas for Improvement")
    
    print("""
Based on the test, record improvements needed in these areas:

1. **Phase 1.1 Exploration**
   - [ ] Does exploration use appropriate tools?
   - [ ] Is exploration limited to necessary steps?
   - [ ] Does it gather relevant context?
   - [ ] Does it stop at the right time?
   
   Improvements needed:
   _____________________________________________________________

2. **Phase 1.2 Strategic Guidance**
   - [ ] Does guidance reference exploration findings?
   - [ ] Are tool recommendations appropriate?
   - [ ] Are success criteria clear and measurable?
   - [ ] Are considerations helpful?
   
   Improvements needed:
   _____________________________________________________________

3. **Phase 2 ReAct Execution**
   - [ ] Does it start ReAct immediately?
   - [ ] Does it use guidance effectively?
   - [ ] Does it adapt to actual results?
   - [ ] Does it avoid anti-patterns (complex scripts)?
   - [ ] Does it achieve the goal?
   
   Improvements needed:
   _____________________________________________________________

4. **Overall Architecture**
   - [ ] Is the flow clear and logical?
   - [ ] Are phases well-separated?
   - [ ] Is there good information flow between phases?
   - [ ] Are costs reasonable (token usage)?
   
   Improvements needed:
   _____________________________________________________________

5. **Error Handling**
   - [ ] Does it handle exploration failures gracefully?
   - [ ] Does it have good backup strategies?
   - [ ] Does it recover from tool failures?
   
   Improvements needed:
   _____________________________________________________________
""")
    
    print_section("Next Steps")
    print("""
1. Review the test output above
2. Fill in the improvement sections
3. Update TODO.md with findings
4. Implement high-priority improvements
5. Re-test to verify improvements
""")

if __name__ == "__main__":
    main()
