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
- ✅ **19 tools** - Filesystem, Git, Docker, System, Network
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

### Git Workflow

```bash
clis run "show git status"
clis run "show my changes"
clis run "commit modified files by directory"
clis run "push to remote"
```

### Docker Management

```bash
clis run "list running containers"
clis run "show logs of web-app"
clis run "restart web container"
clis run "show container stats"
```

### Code Search

```bash
clis run "find all TODOs in Python files"
clis run "where is execute_query defined?"
clis run "find files containing ModuleNotFoundError"
```

### System Diagnostics

```bash
clis run "show system info"
clis run "is port 8000 open?"
clis run "show top CPU processes"
clis run "is docker installed?"
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
clis new "skill-name"
clis new "description" --auto  # AI-generated

# List all skills
clis list

# Edit skill
clis edit skill-name

# View configuration
clis config

# Check health
clis doctor

# Debug mode
clis --verbose run "your query"
```

---

## 🛠️ Available Tools (19)

### Filesystem (6)
- `list_files` - List directory contents
- `read_file` - Read file content
- `search_files` - Search text in files (grep/ripgrep)
- `file_tree` - Display directory tree
- `write_file` - Write to files
- `get_file_info` - File metadata

### Git (3)
- `git_status` - Repository status
- `git_diff` - View changes
- `git_log` - Commit history

### Docker (4)
- `docker_ps` - List containers
- `docker_logs` - Container logs
- `docker_inspect` - Container details
- `docker_stats` - Resource usage

### System (4)
- `system_info` - OS, CPU, memory
- `check_command` - Verify command availability
- `get_env` - Environment variables
- `list_processes` - Running processes

### Network (2)
- `http_request` - HTTP requests
- `check_port` - Port availability

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

## 🛡️ Safety

Three-layer protection:
1. **Blacklist** - Blocks dangerous patterns (rm -rf /, dd, mkfs, etc.)
2. **Risk Scoring** - 0-100 automatic scoring
3. **User Confirmation** - All commands require approval

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
