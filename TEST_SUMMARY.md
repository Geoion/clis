# Strategic Planning Architecture - Test Summary

## 测试场景

**任务**: 分析 src/clis/agent/ 目录中的 TODO 注释，按优先级分类，显示前 3 个最重要的

**预期流程**:
1. Phase 1.1: Read-only 探索（file_tree → grep → read_file）
2. Phase 1.2: 战略指导（基于探索结果）
3. Phase 2: ReAct 执行（灵活实现）

## 测试结果

### ✅ 成功的部分

1. **Phase 0: 任务分析**
   - R1 正确分析了任务复杂度（medium）
   - 选择了 hybrid 模式

2. **Phase 1.1: 探索启动**
   - 成功启动探索阶段
   - 工具选择合理（file_tree, list_files, grep）
   - 推理清晰且有逻辑

3. **架构设计**
   - 阶段分离清晰
   - 信息流向正确
   - 概念验证成功

### ❌ 发现的问题

#### 🔴 Critical (P0)

**1. API Timeout**
```
Problem: DeepSeek API 在 grep 探索时超时
Impact: 阻塞整个 planning 阶段
Evidence: 
  - Step 5: grep "TODO" → Request timed out
  - Retry 1/3 → timed out
  - Retry 2/3 → timed out
```

**2. Exploration Loop**
```
Problem: 重复执行相同工具 3 次
Impact: 浪费时间和 token
Evidence:
  - Step 2: list_files → truncated output
  - Step 3: list_files → same truncated output
  - Step 4: list_files → same truncated output
```

**3. Output Truncation**
```
Problem: 工具输出被截断，探索无法处理
Impact: 获取不完整信息，导致重试
Evidence:
  - file_tree: "...agent.cpytho..."
  - list_files: "...episodic_memory...."
```

#### 🟡 High Priority (P1)

**4. Exploration Strategy**
- 应该直接用 grep 而不是先 list_files
- 遇到截断应该立即改变策略

**5. Progress Indication**
- 用户不知道探索卡住了
- 需要超时警告

## 改进建议

### 立即实施 (P0)

#### 1. API Timeout 处理

```python
def _explore_environment_readonly(self, query: str):
    for i in range(max_steps):
        try:
            # 每个探索步骤设置 timeout
            result = self.tool_executor.execute(
                tool_name, 
                tool_params, 
                timeout=30  # 30秒超时
            )
        except TimeoutError:
            logger.warning(f"Exploration step {i+1} timed out")
            findings.append(f"**Step {i+1}**: Timed out, trying alternative")
            
            # 尝试更简单的替代方案
            if tool_name == "grep":
                # 降级到 read_file
                alternative_tool = "read_file"
                alternative_params = {"path": "known_file.py"}
                # 重试...
```

#### 2. 循环检测

```python
class ExplorationTracker:
    """跟踪探索历史，检测循环"""
    
    def __init__(self):
        self.attempts = []
        self.results = []
    
    def add_attempt(self, tool, params, result):
        signature = (tool, json.dumps(params, sort_keys=True))
        self.attempts.append(signature)
        self.results.append(result)
    
    def is_loop(self, tool, params):
        """检测是否重复相同的尝试"""
        signature = (tool, json.dumps(params, sort_keys=True))
        
        # 如果最近 2 次尝试相同
        if len(self.attempts) >= 2:
            if self.attempts[-1] == signature and self.attempts[-2] == signature:
                return True
        
        return False
    
    def suggest_alternative(self, failed_tool):
        """建议替代工具"""
        alternatives = {
            "list_files": "grep",  # 如果 list_files 失败，用 grep
            "file_tree": "list_files",
            "grep": "read_file"
        }
        return alternatives.get(failed_tool)
```

#### 3. 输出截断处理

```python
def _is_truncated(self, output: str) -> bool:
    """检测输出是否被截断"""
    truncation_indicators = [
        "...",
        "truncated",
        "(truncated)",
        "... (output truncated)",
    ]
    return any(indicator in output.lower() for indicator in truncation_indicators)

def _handle_truncated_output(self, tool, params, output):
    """处理截断的输出"""
    if tool == "list_files":
        # 改用 grep 直接搜索
        return ("grep", {"pattern": "TODO", "path": params["path"]})
    
    elif tool == "file_tree":
        # 改用 list_files
        return ("list_files", {"path": params["path"]})
    
    elif tool == "grep":
        # 添加 max_results 限制
        new_params = params.copy()
        new_params["max_results"] = 10
        return ("grep", new_params)
```

### 短期实施 (P1)

#### 4. 改进探索策略

```python
# 优先级顺序：最直接的工具优先
EXPLORATION_STRATEGY = {
    "find_todos": [
        ("grep", {"pattern": "TODO", "path": "target/"}),  # 最直接
        ("read_file", {"path": "known_file.py"}),          # 备选
        ("list_files", {"path": "target/"}),               # 最后
    ],
    "understand_structure": [
        ("file_tree", {"path": "target/", "max_depth": 2}),
        ("list_files", {"path": "target/"}),
    ]
}
```

#### 5. 进度指示

```python
def _explore_environment_readonly(self, query: str):
    yield {"type": "info", "content": "🔍 Starting exploration (max 5 steps)"}
    
    for i in range(max_steps):
        yield {"type": "progress", "content": f"Step {i+1}/{max_steps}"}
        
        # 如果超时
        if time_elapsed > 30:
            yield {"type": "warning", "content": "⚠️ Step taking longer than expected..."}
        
        # 如果检测到循环
        if tracker.is_loop(tool, params):
            yield {"type": "warning", "content": "⚠️ Detected loop, changing strategy..."}
```

## 测试数据

| Metric | Value | Status |
|--------|-------|--------|
| Total time | 4+ minutes | ❌ Too slow |
| Exploration steps | 5 | ✅ Within limit |
| Successful steps | 4 | ⚠️ 80% |
| Failed steps | 1 (timeout) | ❌ Critical |
| Loops detected | 1 (3x list_files) | ❌ Needs fix |
| Phase 1.2 reached | No | ❌ Blocked |
| Phase 2 reached | No | ❌ Blocked |

## 下一步行动

### 立即 (今天)
- [ ] 实现 API timeout 处理
- [ ] 实现循环检测
- [ ] 实现输出截断处理

### 短期 (本周)
- [ ] 改进探索策略
- [ ] 添加进度指示
- [ ] 重新运行完整测试

### 中期 (下周)
- [ ] 测试更多场景
- [ ] 优化 token 使用
- [ ] 性能基准测试

## 结论

**架构设计**: ✅ 正确且清晰  
**实现质量**: ⚠️ 需要改进错误处理  
**可行性**: ✅ 概念验证成功  

核心架构是正确的，主要需要增强：
1. 错误处理和恢复
2. 循环检测和避免
3. 输出处理和适配

修复这些问题后，架构应该能够正常工作。

---

**相关文件**:
- 详细观察: `TEST_OBSERVATIONS.md`
- 测试脚本: `test_strategic_planning.py`
- 更新记录: `docs/TODO.md`
