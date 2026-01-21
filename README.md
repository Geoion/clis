# CLIS - AI-Powered Terminal Assistant

<div align="center">

**Claude Code Skills Alternative for DeepSeek/Qwen/Ollama**

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache%202.0-green)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.1.0-orange)](CHANGELOG.md)

[Quick Start](#-quick-start) • [Usage](#-usage) • [Commands](#-commands) • [Documentation](#-documentation)

</div>

---

## 🎯 What is CLIS?

**CLIS** (Command Line Intelligence System) brings Claude Code's intelligent tool calling capabilities to open-source LLMs:

- ✅ **96% cost savings** - < $0.003/query (DeepSeek) vs $20/month (Claude Code)
- ✅ **40 tools** - Complete editing, search, analysis capabilities
- ✅ **智能记忆** - AI 自动参考历史任务经验 ⭐
- ✅ **Open Skills System** - Customizable domain knowledge (vs Claude's closed skills)
- ✅ **Offline mode** - Ollama support for complete privacy
- ✅ **Full control** - User confirmation for all commands
- ✅ **Cross-platform** - Windows/macOS/Linux

---

## 🚀 Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/Geoion/clis.git
cd clis

# Install (all dependencies will be installed automatically)
pip install -e .
```

### Initialize

```bash
# Interactive setup
clis init

# Or specify provider
clis init --provider deepseek  # Low cost (recommended)
clis init --provider ollama     # Free, offline
clis init --provider qwen       # Chinese-optimized
```

### First Command

```bash
# Tool calling is enabled by default
clis run "list all Python files"
clis run "show my git changes"
clis run "show container logs"
```

---

## 💡 Usage

### Git Workflow (Complete)

```bash
clis run "show git status"
clis run "show my changes"
clis run "commit modified files by directory"
clis run "push to remote"
clis run "create a new feature branch"
clis run "pull latest changes from main"
```

### Docker Management

```bash
clis run "list running containers"
clis run "show logs of web-app"
clis run "restart web container"
clis run "show container stats"
```

### Code Editing & Analysis

```bash
clis run "find all TODOs in Python files"
clis run "replace print with logger in main.py"
clis run "check linter errors in src/"
clis run "show me functions matching pattern 'async def.*'"
```

### System & Background Tasks

```bash
clis run "show system info"
clis run "is port 8000 open?"
clis run "show top CPU processes"
clis run "start dev server in background"
clis run "list background processes"
```

---

## 🧠 智能记忆系统 (新功能)

### 自动历史学习 ⭐
AI 会**自动参考**相似的历史任务经验：

```bash
# 第一次做某事
clis run "配置 Docker 容器"
# → AI 从零开始学习

# 第二次做类似的事
clis run "部署 Docker 服务"
# → 💡 AI 自动找到之前的 Docker 任务
# → 💡 自动参考历史经验和解决方案
# → 更快更准确！
```

### 手动搜索历史
```bash
# 搜索相似任务
clis memory similar "Docker 配置"

# 查看详情
clis memory show <task_id>

# 查看子任务
clis memory subtasks <task_id>

# 管理记忆
clis memory list
clis memory stats
clis memory cleanup
```

---

## 📋 Commands

### Core Commands

```bash
# Run query (tool calling enabled by default)
clis run "your query"

# Disable tool calling
clis run "your query" --no-tool-calling

# Create custom skill
clis skill create "skill-name"
clis skill create "description" --auto  # AI-generated

# List all skills
clis skill list

# View configuration
clis config show

# Check health
clis doctor

# Debug mode
clis --verbose run "your query"
```

---

## 🛠️ Available Tools (40)

### Filesystem (20)
**基础操作** (6):
- `list_files`, `read_file`, `write_file`, `delete_file`, `get_file_info`, `file_tree`

**搜索功能** (3):
- `search_files` - 文件内容搜索
- `grep` - 增强搜索（正则）⭐
- `codebase_search` - 语义搜索 ⭐

**代码编辑** (4):
- `edit_file` - 精确编辑（diff 模式）⭐
- `search_replace` - 批量替换（正则）⭐
- `insert_code` - 行级插入 ⭐
- `delete_lines` - 行范围删除 ⭐

**代码分析** (4):
- `find_definition` - 查找定义 ⭐
- `find_references` - 查找引用 ⭐
- `get_symbols` - 提取符号 ⭐
- `read_lints` - Linter 集成 ⭐

**其他** (3):
- 各种辅助工具

### Git (8) - Complete Workflow
- `git_status` - Repository status
- `git_add` - Stage files
- `git_commit` - Commit changes
- `git_push` - 🆕 Push to remote (with upstream support)
- `git_pull` - 🆕 Pull from remote (with rebase support)
- `git_branch` - 🆕 Branch management (list/create/delete/rename)
- `git_checkout` - 🆕 Switch branches or restore files
- `git_diff` - View changes
- `git_log` - Commit history

### Docker (4)
- `docker_ps` - List containers
- `docker_logs` - Container logs
- `docker_inspect` - Container details
- `docker_stats` - Resource usage

### System (5)
- `system_info` - OS, CPU, memory
- `check_command` - Verify command availability
- `get_env` - Environment variables
- `list_processes` - Running processes
- `run_terminal_cmd` - 🆕 Execute commands (with background support)

### Network (2)
- `http_request` - HTTP requests
- `check_port` - Port availability

### General (2)
- `execute_command` - Execute shell commands
- `git_status` - Quick git status (built-in)

---

## 🔧 Configuration

### Provider Setup

**DeepSeek (Recommended for Cost)**
```bash
clis init --provider deepseek
export DEEPSEEK_API_KEY="your-key"
# Cost: ~$0.003/query
```

**Ollama (Recommended for Privacy)**
```bash
# Install Ollama from https://ollama.ai
ollama pull llama3
clis init --provider ollama
# Cost: $0 (completely free)
```

**Qwen (Chinese-Optimized)**
```bash
clis init --provider qwen
export QWEN_API_KEY="your-key"
```

### Context Window Configuration

Edit `~/.clis/config/llm.yaml`:

```yaml
model:
  name: deepseek-chat
  context:
    window_size: 64000      # deepseek-chat: 64K, deepseek-coder: 128K
    auto_chunk: true        # Enable automatic file chunking
    chunk_overlap: 200      # Overlap lines between chunks
    reserved_tokens: 4000   # Reserved for system prompt
```

## 🌟 Key Features

### Open Skills System
Unlike Claude Code's closed skills, CLIS uses **open, customizable Skills**:
- 📝 Markdown format - Easy to read and edit
- 🔧 User-definable - Create skills for any domain
- 🤝 Community-driven - Share and collaborate
- 🎯 Fine-grained control - Safety rules, platform compatibility

See `skills/` directory for examples (Docker, Git, etc.)

### Enhanced Code Editing
- **edit_file**: Precise editing with diff preview and dry-run mode
- **grep**: Regex search with context lines
- **read_lints**: Automatic linter integration

### Complete Git Workflow
Full git operations from status to push, including branch management

### Background Process Support
Run long-running tasks (dev servers, builds) in background with process management

## 🛡️ Safety

Three-layer protection system ensures safe command execution:

1. **Blacklist Protection** - Blocks dangerous patterns
   - Destructive commands (`rm -rf /`, `dd`, `mkfs`)
   - System modifications without confirmation
   - Fork bombs and malicious patterns

2. **Risk Scoring (0-100)** - Automatic risk assessment
   - **Low (0-30)**: Read-only operations - Auto-execute
   - **Medium (31-60)**: Write operations - Require confirmation
   - **High (61-90)**: Destructive operations - Require confirmation
   - **Critical (91-100)**: System-level operations - Blocked
   
   Examples:
   - `ls -la` → 10 (low) → Auto-execute
   - `git add .` → 50 (medium) → Confirm
   - `git push` → 70 (high) → Confirm
   - `git push --force` → 95 (critical) → Blocked
   - `rm -rf dir` → 85 (high) → Confirm
   - `sudo apt install` → 95 (critical) → Blocked

3. **User Confirmation** - Interactive approval for risky operations
   - All high-risk tools require explicit approval
   - Risk score and level displayed for transparency
   - File modifications, git operations, deletions always confirmed

All tools have explicit risk scores and confirmation requirements. Configure behavior in `~/.clis/config/safety.yaml`.

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

## 📄 License

Apache License 2.0 - see [LICENSE](LICENSE) file for details.

---

## 🔗 Links

- **Homepage**: https://github.com/Geoion/clis
- **Issues**: https://github.com/Geoion/clis/issues
- **Documentation**: https://github.com/Geoion/clis#readme
