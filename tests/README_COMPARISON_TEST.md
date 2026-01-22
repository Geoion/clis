# Agent Comparison Test Guide

## Overview

This test framework is used to compare the performance of **ReAct** and **Plan-Execute** Agent modes.

## Test Files

```
tests/
├── test_agent_comparison.py      # Main test framework (430 lines)
├── test_quick_comparison.py      # Quick test (single scenario)
├── test_scenarios.json           # Test scenario configuration (10 scenarios)
├── README_COMPARISON_TEST.md     # This document
└── results/                      # Test results output directory
    ├── test_results.json         # Detailed data
    └── test_report.md            # Readable report
```

## Quick Start

### 1. Quick Verification (Recommended First)

Test a single simple scenario to verify the framework works correctly:

```bash
cd tests
python3 test_quick_comparison.py
```

**Expected Output**:
- Compare ReAct and Plan-Execute execution processes
- Display execution time, operation count, tool calls
- Generate JSON results file

### 2. Complete Test Suite

Run all 10 test scenarios:

```bash
# Method 1: Use script (recommended)
./scripts/run_comparison_test.sh

# Method 2: Direct pytest run
python3 -m pytest tests/test_agent_comparison.py::test_full_comparison -v -s

# Method 3: Direct Python run
cd tests
python3 test_agent_comparison.py
```

### 3. Test Single Scenario

```python
from test_agent_comparison import AgentComparison

comparison = AgentComparison()

# Test Flask Web Service
comparison.compare_scenario(
    "Flask Test",
    "Create a Flask web service in /tmp/flask_test with /hello endpoint"
)

# Save results
comparison.save_results("my_test_results.json")

# Generate report
print(comparison.generate_report())
```

## Test Scenarios

### Simple Tasks (2)
1. **Simple File Creation** - Create text file
2. **Simple File Read** - Read and analyze file

**Expected**: ReAct may be more flexible

### Medium Tasks (4)
3. **Flask Web Service** - Create Flask service
4. **Django Project Init** - Django project initialization
5. **Git Repository Setup** - Git repository creation
6. **Git Branch Operations** - Git branch operations

**Expected**: Plan-Execute should be more efficient

### Complex Tasks (2)
7. **Multi-file Refactoring** - Multi-file refactoring
8. **Docker Service Deployment** - Docker service deployment

**Expected**: Plan-Execute significant advantage

### Edge Cases (2)
9. **File Not Found Error** - File not found error
10. **Permission Error Handling** - Permission error handling

**Expected**: ReAct better at adapting to errors

## Evaluation Metrics

### 1. Efficiency (Weight: 30%)
- **Execution Time**: Total time taken
- **Operation Count**: Tool call count

### 2. Accuracy (Weight: 40%)
- **Success Rate**: Whether task completed successfully
- **Error Handling**: Error recovery capability

### 3. Predictability (Weight: 15%)
- **Execution Path Stability**: Consistency across repeated runs

### 4. Memory Quality (Weight: 10%)
- **Task Document Completeness**: `.clis_memory/` document quality
- **Known Facts Relevance**: Working Memory effectiveness

### 5. Debuggability (Weight: 5%)
- **Log Clarity**: Output information readability
- **Error Messages**: Error message usefulness

## Result Output

### JSON Results (`test_results.json`)

```json
{
  "timestamp": "2026-01-22T02:30:00",
  "total_scenarios": 4,
  "results": [
    {
      "mode": "react",
      "scenario": "Quick Test",
      "success": true,
      "execution_time": 3.45,
      "operation_count": 3,
      "tool_calls": [
        {"tool": "write_file", "params": {...}},
        {"tool": "file_tree", "params": {...}}
      ],
      "memory_stats": {
        "tools_used": 2,
        "files_written": 1
      }
    },
    ...
  ]
}
```

### Markdown Report (`test_report.md`)

```markdown
# Agent Comparison Test Report

## Summary
- ReAct wins: 2
- Plan-Execute wins: 6
- Ties: 2

## Detailed Results

### Flask Web Service
| Metric | ReAct | Plan-Execute | Diff |
|--------|-------|--------------|------|
| Success | true | true | - |
| Time (s) | 12.34 | 8.45 | -3.89 |
| Operations | 11 | 6 | -5 |
```

## Custom Tests

### Add New Scenario

Edit `test_scenarios.json`:

```json
{
  "id": 11,
  "name": "My Custom Test",
  "category": "custom",
  "query": "Your test query here",
  "expected_operations": {
    "react": "3-5",
    "plan-execute": "2-3"
  }
}
```

### Modify Evaluation Criteria

Adjust weights in `test_scenarios.json`:

```json
{
  "evaluation_criteria": {
    "efficiency": {"weight": 0.4},  // Increase efficiency weight
    "accuracy": {"weight": 0.3}     // Decrease accuracy weight
  }
}
```

## Troubleshooting

### Issue: Test Fails "No module named 'clis'"

**Solution**:
```bash
# Ensure in project root directory
cd /path/to/clis

# Install project
pip install -e .
```

### Issue: Test Hangs

**Solution**:
1. Check if LLM configuration is correct (`config/llm.yaml`)
2. Check log files to confirm network issues
3. Try increasing timeout

### Issue: Memory Errors

**Solution**:
```bash
# Clean old memory files
rm -rf .clis_memory/*
```

## Best Practices

1. **Run quick test first** - Verify environment configuration
2. **Gradually add scenarios** - Don't run all tests at once
3. **Record environment info** - Save LLM model, version, etc.
4. **Run multiple times and average** - Reduce randomness impact
5. **Save test results** - For subsequent comparison analysis

## Next Steps

1. Run quick test to verify framework
2. Adjust test scenarios based on results
3. Execute complete test suite
4. Analyze results and make decisions
5. Update documentation with conclusions

---

**Maintainer**: @eskiyin  
**Last Updated**: 2026-01-22  
**Status**: 🟢 Ready for testing
