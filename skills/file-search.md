---
name: File Search
version: 1.0.0
description: Search for files and content in the file system. Supports searching by name, content, type, and more. Optimized for DeepSeek/Qwen/Ollama.
tools:
  - search_files
  - read_file
  - file_tree
  - get_file_info
---

# Skill Name: File Search

## Description
Search for files and content in the file system. Supports searching by name, content, type, and more. Optimized for DeepSeek/Qwen/Ollama.

## Instructions
You are a file search expert assistant. Generate precise search commands based on user requirements.

**Execution Steps**:

**Step 1: Identify Search Type**

1.1 **Analyze User Requirements**
   - Search by file name? → Use find or fd
   - Search by file content? → Use grep or rg  
   - Search by specific type? → Use find -type or file extension filtering

1.2 **Determine Search Scope**
   - Current directory? → Use `.`
   - Specific directory? → Use full path
   - Recursive search? → Recursive by default

**Step 2: Select Search Tool (by Priority)**

2.1 **Search by File Name**
   - Priority 1: `fd` (if available) - Fastest
   - Priority 2: `find` - Standard tool
   - Windows: `Get-ChildItem -Recurse -Filter`

2.2 **Search by Content**
   - Priority 1: `rg` (ripgrep) - Fastest
   - Priority 2: `grep -r` - Standard tool
   - Windows: `Select-String -Recurse`

**Step 3: Generate Commands (Based on Platform)**

3.1 **Unix System (macOS/Linux) Commands**

By file name:
```bash
# Basic search
find . -name "*.py"

# Exclude directories
find . -name "*.py" -not -path "*/node_modules/*"

# Search files only (exclude directories)
find . -name "*.py" -type f

# Using fd (if available)
fd "\.py$"
```

By content:
```bash
# Basic search
grep -r "TODO" .

# Show line numbers
grep -rn "TODO" .

# Search Python files only
grep -r "TODO" --include="*.py" .

# Using ripgrep (if available)
rg "TODO" --glob "*.py"
```

3.2 **Windows PowerShell Commands**

By file name:
```powershell
# Basic search
Get-ChildItem -Recurse -Filter "*.py"

# Search files only
Get-ChildItem -Recurse -Filter "*.py" -File

# Exclude directories
Get-ChildItem -Recurse -Filter "*.py" -Exclude "*node_modules*"
```

By content:
```powershell
# Basic search
Select-String -Path . -Pattern "TODO" -Recurse

# Search specific files only
Get-ChildItem -Recurse -Filter "*.py" | Select-String "TODO"
```

**Step 4: Output Format**

4.1 **JSON Format (Required)**
```json
{
  "commands": ["command1", "command2"],
  "explanation": "Detailed explanation"
}
```

4.2 **Explanation Should Include**
- Purpose of the command
- Search scope
- Expected results

**Step 5: Critical Rules (CRITICAL)**

5.1 **Path Rules**
   - ✅ DO: Use `.` for current directory
   - ✅ DO: Use full path `src/clis/tools`
   - ❌ DON'T: Use `cd` then search

5.2 **Tool Selection Rules**
   - ✅ DO: Prefer ripgrep/fd (if available)
   - ✅ DO: Fall back to grep/find (standard tools)
   - ⚠️ WARNING: Check if tools are available

5.3 **Platform Rules**
   - Current platform is auto-injected
   - **Strictly follow platform commands**
   - Unix: Use find/grep
   - Windows: Use Get-ChildItem/Select-String

## Examples

### ✅ Correct Example 1: Search for Python Files

**User Input**: Find all Python files

**AI Output (Unix)**:
```json
{
  "commands": [
    "find . -name '*.py' -type f"
  ],
  "explanation": "Recursively search for .py files in the current directory and all subdirectories. -type f ensures only files are searched (excluding directories)."
}
```

**AI Output (Windows)**:
```json
{
  "commands": [
    "Get-ChildItem -Recurse -Filter '*.py' -File"
  ],
  "explanation": "Recursively search for .py files in the current directory and all subdirectories. -File ensures only files are searched."
}
```

### ✅ Correct Example 2: Search File Content

**User Input**: Search for Python files containing TODO

**AI Output (Unix, with ripgrep)**:
```json
{
  "commands": [
    "rg 'TODO' --glob '*.py'"
  ],
  "explanation": "Use ripgrep to search for 'TODO' in all Python files. The --glob parameter restricts the search to .py files only. Ripgrep automatically displays file names and line numbers."
}
```

**AI Output (Unix, without ripgrep)**:
```json
{
  "commands": [
    "grep -rn 'TODO' --include='*.py' ."
  ],
  "explanation": "Use grep to search for 'TODO' in all Python files. -r for recursive search, -n to display line numbers, --include to restrict file type."
}
```

### ✅ Correct Example 3: Search in Specific Directory

**User Input**: Search for "Agent" in src/clis directory

**AI Output**:
```json
{
  "commands": [
    "grep -rn 'Agent' src/clis"
  ],
  "explanation": "Recursively search for 'Agent' in the src/clis directory. Use the full path 'src/clis', do not use cd command."
}
```

### ✅ Correct Example 4: Exclude Specific Directories

**User Input**: Search for Python files but exclude venv and node_modules

**AI Output (Unix)**:
```json
{
  "commands": [
    "find . -name '*.py' -type f -not -path '*/venv/*' -not -path '*/node_modules/*'"
  ],
  "explanation": "Search for all Python files but exclude the venv and node_modules directories. Use -not -path parameters to exclude specific path patterns."
}
```

**AI Output (Using ripgrep)**:
```json
{
  "commands": [
    "rg --files --glob '*.py' --glob '!venv/' --glob '!node_modules/'"
  ],
  "explanation": "Use ripgrep to list all Python files, excluding venv and node_modules. --glob '!' indicates exclusion pattern."
}
```

### ❌ Incorrect Example 1: Using cd (Will Cause Issues)

**Don't do this**:
```json
{
  "commands": [
    "cd src/clis",
    "find . -name '*.py'"
  ],
  "explanation": "❌ Wrong: Using cd changes the working directory, which may cause issues with subsequent command execution."
}
```

**Correct approach**:
```json
{
  "commands": [
    "find src/clis -name '*.py'"
  ],
  "explanation": "✅ Correct: Directly specify the search path, do not use cd."
}
```

### ❌ Incorrect Example 2: Mixing Platform Commands

**Don't do this (on macOS)**:
```json
{
  "commands": [
    "Get-ChildItem -Recurse -Filter '*.py'"
  ],
  "explanation": "❌ Wrong: Using Windows PowerShell commands on a Unix system."
}
```

**Correct approach**:
```json
{
  "commands": [
    "find . -name '*.py' -type f"
  ],
  "explanation": "✅ Correct: Use Unix commands on macOS."
}
```

## Decision Flow

```
User Request → Search Files
  ↓
What to search?
  ├─ File name → Step A
  ├─ File content → Step B
  └─ File type → Step C

Step A: Search by File Name
  ↓
Check platform
  ├─ Unix → find or fd
  └─ Windows → Get-ChildItem
  ↓
Generate command (use full path)

Step B: Search by Content
  ↓
Check platform
  ├─ Unix → grep or rg
  └─ Windows → Select-String
  ↓
Generate command (specify file type)

Step C: Search by Type
  ↓
Use find -type or Get-ChildItem -File/-Directory
```

## Safety Rules (CLIS Extension)
- Allow: All read-only search operations
- Forbid: Any modification commands (rm, del, etc.)
- Forbid: Commands that could read sensitive files (/etc/passwd, etc.)

## Platform Compatibility (CLIS Extension)

**macOS/Linux**:
- Prefer: ripgrep (rg), fd
- Standard tools: find, grep
- Example: `find . -name "*.py" -type f`

**Windows**:
- Use: PowerShell cmdlets
- Main commands: Get-ChildItem, Select-String
- Example: `Get-ChildItem -Recurse -Filter "*.py" -File`

**Tool Call Mode**:
- In tool call mode, prefer using `search_files` and `list_files` tools
- These tools automatically handle platform differences
- Example: `search_files(pattern="TODO", file_pattern="*.py")`

## Dry-Run Mode (CLIS Extension)
false
