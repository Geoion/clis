#!/usr/bin/env python3
"""
Test Improvements to Exploration Phase

Tests the 4 key improvements:
1. Loop Detection
2. Truncation Handling
3. Smart Strategy
4. Progress Indication
"""

import sys
import time
from datetime import datetime

def print_header(title):
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80 + "\n")

def main():
    print_header("Testing Exploration Improvements")
    
    print("Improvements Implemented:")
    print("  ✅ 1. Loop Detection - Detects repeated tool calls")
    print("  ✅ 2. Truncation Handling - Detects and handles truncated output")
    print("  ✅ 3. Smart Strategy - Better tool selection priority")
    print("  ✅ 4. Progress Indication - Shows progress and warnings")
    print()
    
    print("Test Command:")
    test_cmd = 'clis run "find all TODO comments in src/clis/agent/ and show top 3"'
    print(f"  {test_cmd}")
    print()
    
    print("What to Observe:")
    print()
    
    print("1. Loop Detection:")
    print("   - Should NOT repeat same tool 3 times")
    print("   - Should show '⚠️ Loop detected!' if repeated")
    print("   - Should suggest alternative tool")
    print()
    
    print("2. Truncation Handling:")
    print("   - Should detect '...' in output")
    print("   - Should show '⚠️ Output truncated'")
    print("   - Should suggest more specific query")
    print()
    
    print("3. Smart Strategy:")
    print("   - Should use grep FIRST for TODO search")
    print("   - Should NOT start with file_tree or list_files")
    print("   - Should be more direct")
    print()
    
    print("4. Progress Indication:")
    print("   - Should show '📊 Exploration step X/5'")
    print("   - Should show '⏱️ Step took Xs' if slow")
    print("   - Should show '✓ Exploration complete' at end")
    print()
    
    print_header("Running Test")
    print("Press Ctrl+C to stop\n")
    
    start_time = time.time()
    
    try:
        import subprocess
        result = subprocess.run(
            test_cmd,
            shell=True,
            timeout=180  # 3 minutes
        )
        
        elapsed = time.time() - start_time
        
        print()
        print_header("Test Results")
        print(f"Exit Code: {result.returncode}")
        print(f"Duration: {elapsed:.1f}s")
        
        if result.returncode == 0:
            print("\n✅ Test completed successfully!")
        else:
            print(f"\n⚠️ Test completed with errors (exit code {result.returncode})")
        
    except subprocess.TimeoutExpired:
        print("\n❌ Test timed out after 3 minutes")
    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
    
    print()
    print_header("Checklist")
    print("""
Please verify the following improvements were observed:

[ ] 1. Loop Detection
    - No repeated tool calls (max 2 of same tool)
    - Warning shown if loop detected
    - Alternative tool suggested

[ ] 2. Truncation Handling
    - Truncation detected in output
    - Warning shown
    - More specific query suggested

[ ] 3. Smart Strategy
    - grep used first for TODO search
    - Direct approach taken
    - No unnecessary file_tree/list_files

[ ] 4. Progress Indication
    - Step numbers shown (X/5)
    - Slow step warnings shown
    - Completion message shown

Overall Improvement: [ ] Yes [ ] No

Notes:
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________
""")

if __name__ == "__main__":
    main()
