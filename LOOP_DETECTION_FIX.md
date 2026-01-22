# Loop Detection Logic - Critical Fix

**Date**: 2026-01-22 13:50  
**Issue**: execute_command wrongly limited to 5 uses  
**Status**: ✅ Fixed

---

## Problem

### Original Issue
```
2026-01-22 13:41:13 - WARNING - Loop detected: Tool 'execute_command' has been used 6 times!
2026-01-22 13:41:13 - ERROR - Loop detected in Phase 2, ending this round
```

### Root Cause

**Old Logic** (working_memory.py, line 379-382):
```python
# Rule 2: Single tool used more than 5 times
for tool, count in self.tools_used.items():
    if count > 5:
        return True, f"Tool '{tool}' has been used {count} times!"
```

**Problem**:
- ALL tools limited to 5 uses
- execute_command, write_file, edit_file are common tools
- Using them 6+ times is NORMAL, not a loop
- This breaks ReAct's flexibility

### Why This is Wrong

**Scenario 1: Creating Multiple Files**
```python
write_file("file1.py", ...)  # 1
write_file("file2.py", ...)  # 2
write_file("file3.py", ...)  # 3
write_file("file4.py", ...)  # 4
write_file("file5.py", ...)  # 5
write_file("file6.py", ...)  # 6 → ❌ Loop detected! (WRONG)
```

**Scenario 2: Multiple Commands**
```python
execute_command("mkdir dir1")     # 1
execute_command("mkdir dir2")     # 2
execute_command("git init")       # 3
execute_command("git add .")      # 4
execute_command("git commit")     # 5
execute_command("git push")       # 6 → ❌ Loop detected! (WRONG)
```

**Scenario 3: Editing Multiple Files**
```python
edit_file("file1.py", ...)  # 1-6
# ❌ Loop detected after 6 edits (WRONG)
```

---

## Solution

### New Logic

```python
def detect_loop(self) -> Tuple[bool, str]:
    """
    Detect if stuck in a loop.
    
    Strategy: Focus on detecting ACTUAL loops (repeated failures),
    not just frequent use of common tools.
    """
    
    # Rule 1: Single file read more than 3 times (relaxed from 2)
    file_counts = Counter(self.files_read)
    for file, count in file_counts.items():
        if count > 3:
            return True, f"File '{file}' has been read {count} times!"
    
    # Rule 2: Tool usage (EXCLUDING common tools)
    common_tools_no_limit = {
        'execute_command',  # Different commands are normal
        'write_file',       # Multiple files are normal
        'edit_file',        # Multiple edits are normal
        'grep',             # Multiple searches are normal
        'read_file',        # Reading different files is normal
        'list_files',
        'git_add',
        'git_commit'
    }
    
    for tool, count in self.tools_used.items():
        if tool in common_tools_no_limit:
            continue  # Skip common tools
        
        if count > 10:  # Other tools limited to 10
            return True, f"Tool '{tool}' has been used {count} times!"
    
    # Rule 3: Reading same 1-2 files back and forth
    if len(self.files_read) >= 5:
        recent = self.files_read[-5:]
        unique_files = set(recent)
        if len(unique_files) <= 2 and len(recent) == 5:
            if recent.count(recent[0]) >= 3:
                return True, f"Repeatedly reading same files: {unique_files}"
    
    # Rule 4: IDENTICAL commands repeated (not just execute_command usage)
    if len(self.commands_run) >= 5:
        recent_cmds = [c['cmd'] for c in self.commands_run[-5:]]
        
        # Last 5 commands are IDENTICAL
        if len(set(recent_cmds)) == 1:
            return True, f"Executed identical command 5 times: {recent_cmds[0][:100]}"
        
        # Last 3 commands are IDENTICAL (stricter)
        if len(self.commands_run) >= 3:
            last_3 = [c['cmd'] for c in self.commands_run[-3:]]
            if len(set(last_3)) == 1:
                return True, f"Executed identical command 3 times: {last_3[0][:100]}"
    
    return False, ""
```

### Key Changes

#### 1. Common Tools Exemption
```python
# These tools can be used unlimited times
common_tools_no_limit = {
    'execute_command',  # ⭐ Key fix
    'write_file',
    'edit_file',
    'grep',
    'read_file',
    'list_files',
    'git_add',
    'git_commit'
}
```

#### 2. Focus on Identical Repeats
```python
# Not just "execute_command used 6 times"
# But "same command executed 3 times"

# ✅ OK: Different commands
execute_command("ls")
execute_command("mkdir")
execute_command("git init")
# ... 100 times is fine

# ❌ Loop: Identical commands
execute_command("ls")
execute_command("ls")
execute_command("ls")  # Loop detected!
```

#### 3. Relaxed Limits
```python
# File reads: 2 → 3 times
# Tool usage: 5 → 10 times (for non-common tools)
# File read pattern: More intelligent detection
```

---

## Impact

### Before Fix
```
Scenario: Create 6 files
write_file("1.py")  # 1
write_file("2.py")  # 2
write_file("3.py")  # 3
write_file("4.py")  # 4
write_file("5.py")  # 5
write_file("6.py")  # 6
❌ Loop detected! Task failed.
```

### After Fix
```
Scenario: Create 6 files
write_file("1.py")  # 1
write_file("2.py")  # 2
write_file("3.py")  # 3
write_file("4.py")  # 4
write_file("5.py")  # 5
write_file("6.py")  # 6
✅ All files created successfully
```

### Real Loop Detection
```
Scenario: Stuck in actual loop
execute_command("ls")
execute_command("ls")
execute_command("ls")
❌ Loop detected! (Correct)
```

---

## Testing

### Test Cases

**1. Multiple Different Commands** (Should PASS)
```python
for i in range(10):
    execute_command(f"echo {i}")
# ✅ Should NOT trigger loop detection
```

**2. Multiple File Writes** (Should PASS)
```python
for i in range(10):
    write_file(f"file{i}.py", "content")
# ✅ Should NOT trigger loop detection
```

**3. Identical Commands** (Should FAIL)
```python
execute_command("ls")
execute_command("ls")
execute_command("ls")
# ❌ Should trigger loop detection
```

**4. Reading Same File** (Should FAIL)
```python
read_file("same.py")  # 1
read_file("same.py")  # 2
read_file("same.py")  # 3
read_file("same.py")  # 4
# ❌ Should trigger loop detection
```

---

## Benefits

### For ReAct Mode
- ✅ Can use execute_command freely
- ✅ Can create many files
- ✅ Can edit many files
- ✅ Not constrained by arbitrary limits

### For Loop Detection
- ✅ Still detects real loops (identical repeats)
- ✅ Still catches stuck patterns
- ✅ More intelligent detection
- ✅ Fewer false positives

### For User Experience
- ✅ Tasks don't fail due to false loop detection
- ✅ Can complete multi-file projects
- ✅ Can run many different commands
- ✅ Better success rate

---

## Configuration

### Common Tools (No Limit)
```python
{
    'execute_command',  # Different commands
    'write_file',       # Different files
    'edit_file',        # Different files
    'grep',             # Different patterns
    'read_file',        # Different files
    'list_files',       # Different directories
    'git_add',          # Multiple adds
    'git_commit'        # Multiple commits
}
```

### Loop Detection Rules
1. Same file read 4+ times → Loop
2. Non-common tool used 11+ times → Loop
3. Same 1-2 files read back and forth → Loop
4. Identical command 3+ times → Loop

---

## Related Changes

This fix complements the other improvements:
1. ✅ Exploration loop detection (in exploration phase)
2. ✅ Loop detection fix (in execution phase)
3. ✅ Truncation handling
4. ✅ Smart strategy
5. ✅ Progress indication

Together, these create a robust and flexible execution system.

---

## Files Modified

1. `src/clis/agent/working_memory.py` - Loop detection logic
2. `src/clis/agent/pevl_agent.py` - Exploration improvements
3. `docs/TODO.md` - Documentation

---

## Verification

Run test to verify:
```bash
clis run "create 10 Python files with different content"
```

Should NOT trigger loop detection (before it would fail at file 6).
