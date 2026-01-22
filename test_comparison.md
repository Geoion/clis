# ReAct vs Plan-Execute Horizontal Comparison Test

## Test Configuration
- **Model**: deepseek-chat
- **Max Tokens**: 8192 (adjusted to maximum)
- **Temperature**: 0.1
- **Date**: 2026-01-22

## Test Scenarios

### Scenario 1: Medium Complexity - Python Flask Web Service
**Task**: Create a Flask Web service in `/tmp/test_flask`, including:
- Basic directory structure
- app.py (hello world API)
- requirements.txt
- Git initialization and commit
- Test API (using curl)

**Commands**:
```bash
# ReAct Mode
clis run "create a python web service with flask in /tmp/test_flask, use python3 and test 'hello world' API with CURL"

# Plan-Execute Mode  
clis run --plan "create a python web service with flask in /tmp/test_flask, use python3 and test 'hello world' API with CURL"
```

### Scenario 2: Simple Task - File Creation and Query
**Task**: Create a test.txt file in /tmp and read its content

**Commands**:
```bash
# ReAct Mode
clis run "create a file /tmp/test.txt with content 'hello world' and read it"

# Plan-Execute Mode
clis run --plan "create a file /tmp/test.txt with content 'hello world' and read it"
```

### Scenario 3: Complex Task - Multi-step Project Initialization
**Task**: Create a Python project template, including:
- Directory structure (src/, tests/, docs/)
- setup.py
- README.md
- .gitignore
- Git initialization
- Virtual environment creation

**Commands**:
```bash
# ReAct Mode
clis run "create a complete python project template in /tmp/my_project with src/, tests/, docs/ directories, setup.py, README.md, .gitignore, git init, and create virtualenv"

# Plan-Execute Mode
clis run --plan "create a complete python project template in /tmp/my_project with src/, tests/, docs/ directories, setup.py, README.md, .gitignore, git init, and create virtualenv"
```

## Comparison Metrics

| Metric | ReAct | Plan-Execute | Description |
|-----|-------|--------------|------|
| Actions | | | Total tool calls + command executions |
| Execution Time | | | Total duration (seconds) |
| Repeated Operations | | | Number of repeated calls to same tool/command |
| Plan Quality | N/A | | Whether plan step count is reasonable |
| Success Rate | | | Whether task completed successfully |
| Efficiency | | | Actions/time |

## Test Results

### Scenario 1: Flask Web Service

#### ReAct Mode
- Actions: 
- Execution Time: 
- Repeated Operations: 
- Success Rate: 
- Notes: 

#### Plan-Execute Mode
- Actions: 
- Execution Time: 
- Plan Steps: 
- Repeated Operations: 
- Success Rate: 
- Notes: 

---

### Scenario 2: Simple File Operations

#### ReAct Mode
- Actions: 
- Execution Time: 
- Repeated Operations: 
- Success Rate: 
- Notes: 

#### Plan-Execute Mode
- Actions: 
- Execution Time: 
- Plan Steps: 
- Repeated Operations: 
- Success Rate: 
- Notes: 

---

### Scenario 3: Complex Project Initialization

#### ReAct Mode
- Actions: 
- Execution Time: 
- Repeated Operations: 
- Success Rate: 
- Notes: 

#### Plan-Execute Mode
- Actions: 
- Execution Time: 
- Plan Steps: 
- Repeated Operations: 
- Success Rate: 
- Notes: 

---

## Comprehensive Analysis

### Advantage Comparison
| Dimension | ReAct | Plan-Execute |
|-----|-------|--------------|
| Simple Tasks | | |
| Medium Tasks | | |
| Complex Tasks | | |
| Execution Speed | | |
| Resource Consumption | | |
| User Experience | | |

### Conclusion

To be filled after testing...
