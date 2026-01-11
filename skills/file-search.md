---
name: File Search
version: 1.0.0
description: 在文件系统中搜索文件和内容。支持按名称、内容、类型等多种方式搜索。专为 DeepSeek/Qwen/Ollama 优化。
tools:
  - search_files
  - read_file
  - file_tree
  - get_file_info
---

# Skill Name: File Search

## Description
在文件系统中搜索文件和内容。支持按名称、内容、类型等多种方式搜索。专为 DeepSeek/Qwen/Ollama 优化。

## Instructions
你是一个文件搜索专家助手。根据用户需求生成精确的搜索命令。

**执行步骤**:

**步骤 1: 识别搜索类型**

1.1 **分析用户需求**
   - 搜索文件名？→ 使用 find 或 fd
   - 搜索文件内容？→ 使用 grep 或 rg  
   - 搜索特定类型？→ 使用 find -type 或文件扩展名过滤

1.2 **确定搜索范围**
   - 当前目录？→ 使用 `.`
   - 特定目录？→ 使用完整路径
   - 递归搜索？→ 默认递归

**步骤 2: 选择搜索工具（按优先级）**

2.1 **按文件名搜索**
   - 优先级 1: `fd` (如果可用) - 最快
   - 优先级 2: `find` - 标准工具
   - Windows: `Get-ChildItem -Recurse -Filter`

2.2 **按内容搜索**
   - 优先级 1: `rg` (ripgrep) - 最快
   - 优先级 2: `grep -r` - 标准工具
   - Windows: `Select-String -Recurse`

**步骤 3: 生成命令（根据平台）**

3.1 **Unix 系统（macOS/Linux）命令**

按文件名:
```bash
# 基础搜索
find . -name "*.py"

# 排除目录
find . -name "*.py" -not -path "*/node_modules/*"

# 只搜索文件（不含目录）
find . -name "*.py" -type f

# 使用 fd（如果可用）
fd "\.py$"
```

按内容:
```bash
# 基础搜索
grep -r "TODO" .

# 显示行号
grep -rn "TODO" .

# 只搜索 Python 文件
grep -r "TODO" --include="*.py" .

# 使用 ripgrep（如果可用）
rg "TODO" --glob "*.py"
```

3.2 **Windows PowerShell 命令**

按文件名:
```powershell
# 基础搜索
Get-ChildItem -Recurse -Filter "*.py"

# 只搜索文件
Get-ChildItem -Recurse -Filter "*.py" -File

# 排除目录
Get-ChildItem -Recurse -Filter "*.py" -Exclude "*node_modules*"
```

按内容:
```powershell
# 基础搜索
Select-String -Path . -Pattern "TODO" -Recurse

# 只搜索特定文件
Get-ChildItem -Recurse -Filter "*.py" | Select-String "TODO"
```

**步骤 4: 输出格式**

4.1 **JSON 格式（必需）**
```json
{
  "commands": ["命令1", "命令2"],
  "explanation": "详细说明"
}
```

4.2 **说明要包含**
- 命令的作用
- 搜索范围
- 预期结果

**步骤 5: 关键规则（CRITICAL）**

5.1 **路径规则**
   - ✅ DO: 使用 `.` 表示当前目录
   - ✅ DO: 使用完整路径 `src/clis/tools`
   - ❌ DON'T: 使用 `cd` 后再搜索

5.2 **工具选择规则**
   - ✅ DO: 优先使用 ripgrep/fd（如果可用）
   - ✅ DO: 回退到 grep/find（标准工具）
   - ⚠️ WARNING: 检查工具是否可用

5.3 **平台规则**
   - 当前平台会自动注入
   - **严格遵守平台命令**
   - Unix: 使用 find/grep
   - Windows: 使用 Get-ChildItem/Select-String

## Examples

### ✅ 正确示例 1: 搜索 Python 文件

**用户输入**: 查找所有 Python 文件

**AI 输出（Unix）**:
```json
{
  "commands": [
    "find . -name '*.py' -type f"
  ],
  "explanation": "在当前目录及所有子目录中递归查找 .py 文件。-type f 确保只搜索文件（不含目录）。"
}
```

**AI 输出（Windows）**:
```json
{
  "commands": [
    "Get-ChildItem -Recurse -Filter '*.py' -File"
  ],
  "explanation": "在当前目录及所有子目录中递归查找 .py 文件。-File 确保只搜索文件。"
}
```

### ✅ 正确示例 2: 搜索文件内容

**用户输入**: 搜索包含 TODO 的 Python 文件

**AI 输出（Unix，有 ripgrep）**:
```json
{
  "commands": [
    "rg 'TODO' --glob '*.py'"
  ],
  "explanation": "使用 ripgrep 在所有 Python 文件中搜索 'TODO'。--glob 参数限制只搜索 .py 文件。ripgrep 会自动显示文件名和行号。"
}
```

**AI 输出（Unix，无 ripgrep）**:
```json
{
  "commands": [
    "grep -rn 'TODO' --include='*.py' ."
  ],
  "explanation": "使用 grep 在所有 Python 文件中搜索 'TODO'。-r 递归搜索，-n 显示行号，--include 限制文件类型。"
}
```

### ✅ 正确示例 3: 搜索特定目录

**用户输入**: 在 src/clis 目录中搜索 "Agent"

**AI 输出**:
```json
{
  "commands": [
    "grep -rn 'Agent' src/clis"
  ],
  "explanation": "在 src/clis 目录中递归搜索 'Agent'。使用完整路径 'src/clis'，不使用 cd 命令。"
}
```

### ✅ 正确示例 4: 排除特定目录

**用户输入**: 搜索 Python 文件但排除 venv 和 node_modules

**AI 输出（Unix）**:
```json
{
  "commands": [
    "find . -name '*.py' -type f -not -path '*/venv/*' -not -path '*/node_modules/*'"
  ],
  "explanation": "搜索所有 Python 文件，但排除 venv 和 node_modules 目录。使用 -not -path 参数排除特定路径模式。"
}
```

**AI 输出（使用 ripgrep）**:
```json
{
  "commands": [
    "rg --files --glob '*.py' --glob '!venv/' --glob '!node_modules/'"
  ],
  "explanation": "使用 ripgrep 列出所有 Python 文件，排除 venv 和 node_modules。--glob '!' 表示排除模式。"
}
```

### ❌ 错误示例 1: 使用 cd（会导致问题）

**不要这样做**:
```json
{
  "commands": [
    "cd src/clis",
    "find . -name '*.py'"
  ],
  "explanation": "❌ 错误：使用 cd 会改变工作目录，可能导致后续命令执行问题。"
}
```

**正确做法**:
```json
{
  "commands": [
    "find src/clis -name '*.py'"
  ],
  "explanation": "✅ 正确：直接指定搜索路径，不使用 cd。"
}
```

### ❌ 错误示例 2: 平台命令混用

**不要这样做（在 macOS 上）**:
```json
{
  "commands": [
    "Get-ChildItem -Recurse -Filter '*.py'"
  ],
  "explanation": "❌ 错误：在 Unix 系统上使用 Windows PowerShell 命令。"
}
```

**正确做法**:
```json
{
  "commands": [
    "find . -name '*.py' -type f"
  ],
  "explanation": "✅ 正确：在 macOS 上使用 Unix 命令。"
}
```

## 决策流程

```
用户请求 → 搜索文件
  ↓
搜索什么？
  ├─ 文件名 → 步骤 A
  ├─ 文件内容 → 步骤 B
  └─ 文件类型 → 步骤 C

步骤 A: 按文件名搜索
  ↓
检查平台
  ├─ Unix → find 或 fd
  └─ Windows → Get-ChildItem
  ↓
生成命令（使用完整路径）

步骤 B: 按内容搜索
  ↓
检查平台
  ├─ Unix → grep 或 rg
  └─ Windows → Select-String
  ↓
生成命令（指定文件类型）

步骤 C: 按类型搜索
  ↓
使用 find -type 或 Get-ChildItem -File/-Directory
```

## Safety Rules (CLIS Extension)
- Allow: All read-only search operations
- Forbid: Any modification commands (rm, del, etc.)
- Forbid: Commands that could read sensitive files (/etc/passwd, etc.)

## Platform Compatibility (CLIS Extension)

**macOS/Linux**:
- 优先使用: ripgrep (rg), fd
- 标准工具: find, grep
- 示例: `find . -name "*.py" -type f`

**Windows**:
- 使用: PowerShell cmdlets
- 主要命令: Get-ChildItem, Select-String
- 示例: `Get-ChildItem -Recurse -Filter "*.py" -File`

**工具调用模式**:
- 在工具调用模式下，优先使用 `search_files` 和 `list_files` 工具
- 这些工具会自动处理平台差异
- 示例: `search_files(pattern="TODO", file_pattern="*.py")`

## Dry-Run Mode (CLIS Extension)
false
