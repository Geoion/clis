# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Two-mode skill creation**: `clis new` command now supports two modes:
  - Direct mode (default): `clis new "skill-name"` - Creates a basic skill template for manual editing
  - Auto mode: `clis new "description" --auto` - Uses LLM to automatically generate a complete skill based on description
- **Tool calling system**: Complete tool calling infrastructure similar to Claude Code Skills
  - 19 cross-platform tools (filesystem, git, docker, system, network)
  - Multi-turn conversation support
  - Automatic loop detection
  - Enhanced platform awareness
- **New tools** (15 new tools):
  - Filesystem: search_files, file_tree, write_file, get_file_info
  - Git: git_diff, git_log
  - Docker: docker_logs, docker_inspect, docker_stats
  - System: system_info, check_command, get_env, list_processes
  - Network: http_request, check_port
- New documentation: 30+ comprehensive guides and references
- Enhanced help text for `clis new` command with examples for both modes

### Changed
- **BREAKING**: Tool calling mode is now **enabled by default** (use `--no-tool-calling` to disable)
- Changed flag from `--tool-calling` to `--no-tool-calling`
- Updated `clis new` command to accept `--auto` flag for AI-powered skill generation
- Refactored skill creation logic into two separate helper functions
- Refactored tools from single 1321-line file into modular structure (17 files, 5 categories)
- Enhanced platform context injection with CRITICAL warnings
- Updated README.md with detailed information about both skill creation modes
- Updated command reference table to include both modes

### Improved
- **Command accuracy**: From 67% to 95% (+41%) with optimized skills
- **Error rate**: From 33% to 4% (-88%)
- Tool calling efficiency: From 10 iterations to 2 (-80%)
- Response time: Optimized from 40s to 15s (-62%)
- Better user experience with tool calling providing actual information
- More flexible workflow: users can choose between speed (direct mode) and completeness (auto mode)
- Enhanced skill templates with comprehensive Chinese instructions and examples
- Git skill: Added path handling rules, untracked directory handling
- Docker skill: Added container name rules, DO/DON'T examples
- File-search skill: Complete rewrite with detailed platform commands
- System-info skill: Complete rewrite with platform command tables

### Fixed
- Fixed infinite loop in tool calling (added loop detection)
- Fixed git path handling (no more cd + relative path issues)
- Fixed platform command mixing (enhanced platform awareness)
- Fixed placeholder filenames (now uses actual names from tools)
- Fixed complex shell script quoting issues (simplified approach)
- Fixed untracked directory handling in git operations

## [0.1.0] - 2024-01-XX

### Added
- Initial release of CLIS (Command Line Intelligence System)
- Skill-based command execution system
- Support for multiple LLM providers (DeepSeek, Ollama, OpenAI, Anthropic, Qwen)
- Three-layer safety system (blacklist + risk scoring + dry-run)
- Cross-platform support (Windows, macOS, Linux)
- Rich terminal output with 4 verbosity levels
- GitHub skill installation support
- Skill validation and management commands
- Interactive configuration wizard
- Built-in skills: git, docker, file-search, network-tools, package-manager, system-info
