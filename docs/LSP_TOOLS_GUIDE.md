# LSP-Based Code Intelligence Tools

本文档介绍 CLIS 的 LSP（Language Server Protocol）工具，它们提供精确的代码分析能力。

## 📦 安装

LSP 工具是可选功能，需要额外安装依赖：

```bash
# 安装 LSP 支持
pip install 'clis[lsp]'

# 或者安装所有高级功能
pip install 'clis[all]'
```

## 🔍 工具对比

### find_definition vs lsp_definition

| 特性 | find_definition (正则) | lsp_definition (LSP) |
|------|----------------------|---------------------|
| **准确性** | ⚠️ 中等（基于正则表达式） | ✅ 高（理解代码语义） |
| **依赖** | ✅ 无需额外依赖 | ⚠️ 需要 jedi |
| **速度** | ✅ 快 | ⚠️ 稍慢（但更准确） |
| **跨文件** | ⚠️ 不理解 imports | ✅ 理解 imports 和作用域 |
| **适用场景** | 快速搜索、简单项目 | 复杂项目、精确导航 |

### find_references vs lsp_references

| 特性 | find_references (grep) | lsp_references (LSP) |
|------|----------------------|---------------------|
| **准确性** | ⚠️ 可能有误报 | ✅ 精确（只找真实引用） |
| **速度** | ✅ 快 | ⚠️ 稍慢 |
| **上下文** | ❌ 不理解作用域 | ✅ 理解变量作用域 |
| **示例** | 找到所有包含 "user" 的行 | 只找到引用 User 类的地方 |

## 🎯 使用场景

### 场景 1：精确查找定义

#### 问题
在大型项目中，`find_definition` 可能找到多个同名符号：

```bash
clis run "find UserService definition"
# 可能找到：
# - class UserService  (正确)
# - user_service = ...  (误报)
# - def user_service(): (误报)
```

#### 解决方案
使用 `lsp_definition` 提供精确上下文：

```bash
clis run "use LSP to find UserService definition in auth.py line 25"
# 只返回正确的 class UserService
```

### 场景 2：理解 Import 链

#### 问题
`find_definition` 无法追踪 import：

```python
# file1.py
from utils import UserService

# file2.py  
class UserService:  # 真正的定义在这里
    pass
```

#### 解决方案
`lsp_definition` 会自动跟随 import：

```bash
# 即使从 file1.py 查询，也会找到 file2.py 中的定义
clis run "find UserService definition from file1.py"
```

### 场景 3：避免重名混淆

#### 问题
项目中有多个 `process` 函数：

```python
# utils.py
def process(data):  # 工具函数
    pass

# main.py
def process(request):  # 请求处理
    pass
```

使用 `find_references` 会混淆两者。

#### 解决方案
`lsp_references` 理解作用域：

```bash
# 只找到对 main.py 中 process 的引用
clis run "find all references to process in main.py line 10"
```

## 📖 详细用法

### lsp_definition

**基本用法**：
```bash
# 简单搜索（会扫描整个项目）
clis run "use LSP to find AuthService definition"
```

**精确搜索（推荐）**：
```bash
# 提供文件、行号、列号获得最准确的结果
clis run "find definition at auth.py line 42 column 15"
```

**API 示例**：
```python
from clis.tools.filesystem import LSPDefinitionTool

tool = LSPDefinitionTool()
result = tool.execute(
    symbol="UserService",
    file="src/auth.py",
    line=25,
    column=10,
    project_path="."
)
```

**输出示例**：
```
Found 1 precise definition(s) for: 'UserService'
(Using Jedi/LSP for accurate code analysis)

======================================================================
Definition 1/1
======================================================================
Type:        class
File:        src/models/user.py
Line:        15
Full Name:   src.models.user.UserService
Module:      src.models.user
Docstring:   Service for user management and authentication.
Signature:   class UserService(BaseService)

Context:
  →   15 | class UserService(BaseService):
      16 |     """Service for user management."""
      17 |     def __init__(self, db):
      18 |         self.db = db
```

### lsp_references

**基本用法**：
```bash
# 查找所有引用
clis run "use LSP to find all references to UserService"
```

**精确查找（推荐）**：
```bash
# 从特定位置开始查找
clis run "find all references to UserService at auth.py line 10"
```

**排除定义**：
```bash
# 只看使用的地方，不包括定义本身
clis run "find references to UserService without definition"
```

**API 示例**：
```python
from clis.tools.filesystem import LSPReferencesTool

tool = LSPReferencesTool()
result = tool.execute(
    symbol="UserService",
    file="src/auth.py",
    line=10,
    column=5,
    include_definition=False  # 不包括定义
)
```

**输出示例**：
```
Found 15 reference(s) to 'UserService' across 5 file(s)
(Using Jedi/LSP for accurate analysis)

======================================================================
📄 src/auth.py (3 reference(s))
======================================================================

→ Line   10:  5  [module]
        from models import UserService

→ Line   25: 12  [instance]
        service = UserService(db)

→ Line   30:  8  
        service.authenticate(user)

======================================================================
📄 src/api/users.py (2 reference(s))
======================================================================
...
```

## 🔧 高级技巧

### 1. 在 AI 对话中使用

```bash
# AI 会自动选择合适的工具
clis run "where is UserService defined?"  # 可能用 find_definition

clis run "show me the exact definition of UserService in auth.py" # 会用 lsp_definition
```

### 2. 结合使用

```bash
# 第一步：用 LSP 找到定义
clis run "find UserService definition with LSP"

# 第二步：用 LSP 找到所有引用
clis run "find all references to UserService"

# 第三步：用 edit_file 修改
clis run "rename UserService to AuthService in all files"
```

### 3. 性能优化

对于大型项目：

```bash
# 方法1：提供精确的文件和行号（最快）
clis run "find definition at src/main.py line 100 column 20"

# 方法2：限制搜索范围
clis run "find UserService in src/models/ directory"

# 方法3：如果只需要快速结果，用正则工具
clis run "quickly find UserService definition"  # 会用 find_definition
```

## ⚠️ 注意事项

### 1. Jedi 限制

- **仅支持 Python**：目前 LSP 工具只支持 Python 代码
- **项目复杂度**：非常大的项目可能需要几秒钟分析时间
- **虚拟环境**：确保在正确的 Python 环境中运行

### 2. 回退机制

如果 LSP 工具不可用，系统会自动提示：

```
Jedi not installed. Install with: pip install 'clis[lsp]'
Falling back to find_definition tool for regex-based search.
```

### 3. 最佳实践

- ✅ **提供上下文**：尽可能提供文件名和行号
- ✅ **使用项目根目录**：在项目根目录运行 CLIS
- ✅ **检查虚拟环境**：确保能访问项目的依赖
- ⚠️ **大型项目**：首次运行可能较慢（Jedi 需要分析代码）

## 🚀 下一步

### 扩展到其他语言

目前可以添加其他语言的 LSP 支持：

- **JavaScript/TypeScript**：使用 `typescript-language-server`
- **Go**：使用 `gopls`
- **Rust**：使用 `rust-analyzer`

### 与 IDE 集成

CLIS 的 LSP 工具使用与 IDE 相同的技术（Jedi），因此结果与 PyCharm、VSCode 一致。

## 📚 相关资源

- [Jedi 文档](https://jedi.readthedocs.io/)
- [LSP 规范](https://microsoft.github.io/language-server-protocol/)
- [CLIS 工具对比](TOOLS_COMPARISON.md)
