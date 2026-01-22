# Agent Comparison Test Report

**Generated**: 2026-01-22 02:17:42
**Total Scenarios**: 4

## Summary

- ReAct wins: 0
- Plan-Execute wins: 4
- Ties: 0

## Detailed Results

### Simple File Creation

| Metric | ReAct | Plan-Execute | Diff |
|--------|-------|--------------|------|
| Success | False | True | - |
| Time (s) | 79.01 | 8.53 | -70.48 |
| Operations | 20 | 2 | -18 |

### Simple File Read

| Metric | ReAct | Plan-Execute | Diff |
|--------|-------|--------------|------|
| Success | True | True | - |
| Time (s) | 25.77 | 7.79 | -17.97 |
| Operations | 4 | 3 | -1 |

### Flask Web Service

| Metric | ReAct | Plan-Execute | Diff |
|--------|-------|--------------|------|
| Success | False | True | - |
| Time (s) | 79.09 | 44.91 | -34.19 |
| Operations | 20 | 3 | -17 |

### Git Repository Creation

| Metric | ReAct | Plan-Execute | Diff |
|--------|-------|--------------|------|
| Success | False | True | - |
| Time (s) | 105.66 | 9.49 | -96.17 |
| Operations | 20 | 3 | -17 |
