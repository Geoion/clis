# 优先级工具实现计划

## Phase 1: 核心工具（第一优先级）

### 1. SearchFilesTool - 代码搜索 ⭐⭐⭐⭐⭐

**功能**: 在文件中搜索文本模式（使用 grep/ripgrep）

**实现预览**:

```python
class SearchFilesTool(Tool):
    """Search for text patterns in files using grep or ripgrep."""
    
    @property
    def name(self) -> str:
        return "search_files"
    
    @property
    def description(self) -> str:
        return "Search for text patterns in files. Supports regex and various file filters."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Search pattern (can be regex)"
                },
                "path": {
                    "type": "string",
                    "default": ".",
                    "description": "Directory to search in"
                },
                "file_pattern": {
                    "type": "string",
                    "description": "File pattern to search (e.g., '*.py', '*.js')"
                },
                "case_sensitive": {
                    "type": "boolean",
                    "default": True,
                    "description": "Case sensitive search"
                },
                "max_results": {
                    "type": "integer",
                    "default": 100,
                    "description": "Maximum number of results"
                }
            },
            "required": ["pattern"]
        }
    
    def execute(self, pattern: str, path: str = ".", 
                file_pattern: str = None, case_sensitive: bool = True,
                max_results: int = 100) -> ToolResult:
        """Execute search."""
        try:
            # Try ripgrep first (faster), fallback to grep
            cmd = ["rg"] if self._has_command("rg") else ["grep", "-r"]
            
            if not case_sensitive:
                cmd.append("-i")
            
            cmd.extend(["-n", "--max-count", str(max_results)])
            
            if file_pattern:
                if cmd[0] == "rg":
                    cmd.extend(["-g", file_pattern])
                else:
                    cmd.append("--include=" + file_pattern)
            
            cmd.extend([pattern, path])
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                return ToolResult(
                    success=True,
                    output=result.stdout,
                    metadata={"matches": len(result.stdout.split('\n'))}
                )
            elif result.returncode == 1:  # No matches
                return ToolResult(
                    success=True,
                    output="No matches found",
                    metadata={"matches": 0}
                )
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=result.stderr
                )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )
```

**使用场景**:
```bash
# 搜索所有 Python 文件中的 TODO
clis run "find all TODOs in Python files" --tool-calling

# 搜索函数定义
clis run "where is function 'execute_query' defined?" --tool-calling

# 搜索特定错误信息
clis run "find files containing 'ModuleNotFoundError'" --tool-calling
```

**价值**: 极高 - 代码搜索是开发中最常用的功能之一

---

### 2. GitDiffTool - Git 差异 ⭐⭐⭐⭐⭐

**功能**: 查看 Git 差异（文件更改）

**实现预览**:

```python
class GitDiffTool(Tool):
    """Show git diff for files or commits."""
    
    @property
    def name(self) -> str:
        return "git_diff"
    
    @property
    def description(self) -> str:
        return "Show git diff to see changes in files. Can show unstaged, staged, or specific file diffs."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file": {
                    "type": "string",
                    "description": "Specific file to show diff for"
                },
                "staged": {
                    "type": "boolean",
                    "default": False,
                    "description": "Show staged changes (--cached)"
                },
                "commit": {
                    "type": "string",
                    "description": "Compare with specific commit hash"
                },
                "unified": {
                    "type": "integer",
                    "default": 3,
                    "description": "Number of context lines"
                }
            }
        }
    
    def execute(self, file: str = None, staged: bool = False,
                commit: str = None, unified: int = 3) -> ToolResult:
        """Execute git diff."""
        try:
            cmd = ["git", "diff", f"-U{unified}"]
            
            if staged:
                cmd.append("--cached")
            
            if commit:
                cmd.append(commit)
            
            if file:
                cmd.append("--")
                cmd.append(file)
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                output = result.stdout if result.stdout else "No differences found"
                return ToolResult(
                    success=True,
                    output=output
                )
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=result.stderr or "Git diff failed"
                )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )
```

**使用场景**:
```bash
# 查看所有更改
clis run "show me what I changed" --tool-calling

# 查看特定文件的更改
clis run "show changes in cli.py" --tool-calling

# 查看已暂存的更改
clis run "show staged changes" --tool-calling
```

**价值**: 极高 - Git 工作流的核心功能

---

### 3. FileTreeTool - 目录树 ⭐⭐⭐⭐

**功能**: 显示目录结构

**实现预览**:

```python
class FileTreeTool(Tool):
    """Display directory structure as a tree."""
    
    @property
    def name(self) -> str:
        return "file_tree"
    
    @property
    def description(self) -> str:
        return "Display directory structure as a tree. Useful for understanding project layout."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "default": ".",
                    "description": "Root directory"
                },
                "max_depth": {
                    "type": "integer",
                    "default": 3,
                    "description": "Maximum depth to traverse"
                },
                "show_hidden": {
                    "type": "boolean",
                    "default": False,
                    "description": "Show hidden files"
                },
                "pattern": {
                    "type": "string",
                    "description": "Filter by file pattern"
                }
            }
        }
    
    def execute(self, path: str = ".", max_depth: int = 3,
                show_hidden: bool = False, pattern: str = None) -> ToolResult:
        """Execute file tree."""
        try:
            # Use tree command if available, otherwise custom implementation
            if self._has_command("tree"):
                cmd = ["tree", "-L", str(max_depth)]
                
                if not show_hidden:
                    cmd.append("-a")
                
                if pattern:
                    cmd.extend(["-P", pattern])
                
                cmd.append(path)
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                
                if result.returncode == 0:
                    return ToolResult(success=True, output=result.stdout)
            
            # Fallback: custom implementation
            output = self._build_tree(Path(path), max_depth, show_hidden, pattern)
            
            return ToolResult(success=True, output=output)
            
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
    
    def _build_tree(self, path: Path, max_depth: int, show_hidden: bool,
                    pattern: str, prefix: str = "", depth: int = 0) -> str:
        """Build tree structure manually."""
        if depth >= max_depth:
            return ""
        
        lines = []
        try:
            items = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name))
            
            for i, item in enumerate(items):
                if not show_hidden and item.name.startswith('.'):
                    continue
                
                if pattern and not fnmatch(item.name, pattern):
                    continue
                
                is_last = i == len(items) - 1
                current_prefix = "└── " if is_last else "├── "
                next_prefix = "    " if is_last else "│   "
                
                lines.append(f"{prefix}{current_prefix}{item.name}")
                
                if item.is_dir():
                    subtree = self._build_tree(
                        item, max_depth, show_hidden, pattern,
                        prefix + next_prefix, depth + 1
                    )
                    lines.append(subtree)
        
        except PermissionError:
            pass
        
        return "\n".join(lines)
```

**使用场景**:
```bash
# 查看项目结构
clis run "show me the project structure" --tool-calling

# 只看 Python 文件
clis run "show Python files in tree structure" --tool-calling

# 查看特定目录
clis run "show structure of src directory" --tool-calling
```

**价值**: 高 - 快速了解项目结构，对新项目特别有用

---

### 4. HttpRequestTool - HTTP 请求 ⭐⭐⭐⭐⭐

**功能**: 发送 HTTP 请求

**实现预览**:

```python
class HttpRequestTool(Tool):
    """Make HTTP requests."""
    
    @property
    def name(self) -> str:
        return "http_request"
    
    @property
    def description(self) -> str:
        return "Make HTTP requests (GET, POST, etc.). Useful for API testing and health checks."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to request"
                },
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                    "default": "GET",
                    "description": "HTTP method"
                },
                "headers": {
                    "type": "object",
                    "description": "HTTP headers (key-value pairs)"
                },
                "data": {
                    "type": "string",
                    "description": "Request body (JSON string for POST/PUT)"
                },
                "timeout": {
                    "type": "integer",
                    "default": 30,
                    "description": "Request timeout in seconds"
                }
            },
            "required": ["url"]
        }
    
    def execute(self, url: str, method: str = "GET", headers: dict = None,
                data: str = None, timeout: int = 30) -> ToolResult:
        """Execute HTTP request."""
        try:
            import requests
            
            # Prepare headers
            req_headers = headers or {}
            
            # Make request
            response = requests.request(
                method=method,
                url=url,
                headers=req_headers,
                data=data,
                timeout=timeout
            )
            
            # Format output
            output = f"Status: {response.status_code} {response.reason}\n"
            output += f"Headers:\n"
            for k, v in response.headers.items():
                output += f"  {k}: {v}\n"
            output += f"\nBody:\n{response.text[:1000]}"  # Limit body size
            
            if len(response.text) > 1000:
                output += "\n... (truncated)"
            
            return ToolResult(
                success=response.status_code < 400,
                output=output,
                metadata={
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "size": len(response.text)
                }
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )
```

**使用场景**:
```bash
# API 健康检查
clis run "check if the API at localhost:8000 is up" --tool-calling

# 测试 REST API
clis run "get data from https://api.example.com/users" --tool-calling

# POST 请求
clis run "post data to webhook" --tool-calling
```

**价值**: 极高 - API 测试和调试必备

---

### 5. DockerLogsTool - Docker 日志 ⭐⭐⭐⭐⭐

**功能**: 查看 Docker 容器日志

**实现预览**:

```python
class DockerLogsTool(Tool):
    """Get logs from Docker containers."""
    
    @property
    def name(self) -> str:
        return "docker_logs"
    
    @property
    def description(self) -> str:
        return "Get logs from a Docker container. Essential for debugging."
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "container": {
                    "type": "string",
                    "description": "Container name or ID"
                },
                "tail": {
                    "type": "integer",
                    "default": 100,
                    "description": "Number of lines to show from end"
                },
                "since": {
                    "type": "string",
                    "description": "Show logs since timestamp (e.g., '1h', '30m')"
                },
                "timestamps": {
                    "type": "boolean",
                    "default": True,
                    "description": "Show timestamps"
                }
            },
            "required": ["container"]
        }
    
    def execute(self, container: str, tail: int = 100, since: str = None,
                timestamps: bool = True) -> ToolResult:
        """Execute docker logs."""
        try:
            cmd = ["docker", "logs", f"--tail={tail}"]
            
            if timestamps:
                cmd.append("--timestamps")
            
            if since:
                cmd.append(f"--since={since}")
            
            cmd.append(container)
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                output = result.stdout or result.stderr  # Some logs go to stderr
                if not output:
                    output = f"No logs found for container: {container}"
                
                return ToolResult(
                    success=True,
                    output=output,
                    metadata={"lines": len(output.split('\n'))}
                )
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=result.stderr or f"Container not found: {container}"
                )
                
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )
```

**使用场景**:
```bash
# 查看容器日志
clis run "show logs of web-app container" --tool-calling

# 最近的错误
clis run "show last 50 lines of logs from database container" --tool-calling

# 特定时间范围
clis run "show logs from last hour for nginx container" --tool-calling
```

**价值**: 极高 - Docker 调试和故障排除必备

---

## 实现时间表

### Week 1: 基础搜索和 Git 工具
- Day 1-2: SearchFilesTool
- Day 3-4: GitDiffTool

### Week 2: 文件和网络工具
- Day 1-2: FileTreeTool
- Day 3-4: HttpRequestTool

### Week 3: Docker 和测试
- Day 1-2: DockerLogsTool
- Day 3-4: 集成测试和文档

## 集成计划

### 1. 更新 builtin.py

```python
# src/clis/tools/builtin.py

from clis.tools.base import Tool, ToolResult

# ... existing tools ...

class SearchFilesTool(Tool):
    # implementation
    pass

class GitDiffTool(Tool):
    # implementation
    pass

class FileTreeTool(Tool):
    # implementation
    pass

class HttpRequestTool(Tool):
    # implementation
    pass

class DockerLogsTool(Tool):
    # implementation
    pass
```

### 2. 更新 __init__.py

```python
# src/clis/tools/__init__.py

from clis.tools.builtin import (
    # Existing
    ListFilesTool,
    ReadFileTool,
    ExecuteCommandTool,
    GitStatusTool,
    DockerPsTool,
    # New
    SearchFilesTool,
    GitDiffTool,
    FileTreeTool,
    HttpRequestTool,
    DockerLogsTool,
)

__all__ = [
    # ... existing ...
    "SearchFilesTool",
    "GitDiffTool",
    "FileTreeTool",
    "HttpRequestTool",
    "DockerLogsTool",
]
```

### 3. 更新 CLI 集成

```python
# src/clis/cli.py - _execute_with_tool_calling()

tools = [
    # Existing
    ListFilesTool(),
    ReadFileTool(),
    GitStatusTool(),
    DockerPsTool(),
    # New Phase 1 tools
    SearchFilesTool(),
    GitDiffTool(),
    FileTreeTool(),
    HttpRequestTool(),
    DockerLogsTool(),
]
```

## 测试场景

### SearchFilesTool
```bash
clis run "find all TODOs" --tool-calling
clis run "where is 'ToolCallingAgent' defined?" --tool-calling
```

### GitDiffTool
```bash
clis run "show my changes" --tool-calling
clis run "what did I change in cli.py?" --tool-calling
```

### FileTreeTool
```bash
clis run "show project structure" --tool-calling
clis run "show me the docs folder structure" --tool-calling
```

### HttpRequestTool
```bash
clis run "check if localhost:8000 is up" --tool-calling
clis run "get weather from api.openweathermap.org" --tool-calling
```

### DockerLogsTool
```bash
clis run "show web-app logs" --tool-calling
clis run "what errors in database container?" --tool-calling
```

## 预期效果

实现这 5 个工具后：

✅ **代码搜索能力**: 达到 Claude Code 水平  
✅ **Git 工作流**: 完整的差异查看  
✅ **项目理解**: 快速了解结构  
✅ **API 测试**: 内置 HTTP 客户端  
✅ **Docker 调试**: 完整的日志查看  

**成本**: 仍然 < ¥0.02/次（DeepSeek）或免费（Ollama）

**竞争力**: 与 Claude Code 功能相当，但成本降低 50-100 倍！
