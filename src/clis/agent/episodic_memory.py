"""
情景记忆模块 - 当前任务的持久化 Markdown 文档

特点:
- 持久化到 .clis_memory/ 目录
- 人类可读可编辑
- 结构化 Markdown (checklist, findings, next steps)
- 跨会话保留
"""

from pathlib import Path
from typing import Optional
from datetime import datetime
import re


class EpisodicMemory:
    """
    情景记忆 - 当前任务的持久化 Markdown 文档
    
    每个任务对应一个 Markdown 文件,包含:
    - 任务目标
    - 任务分解 (checklist)
    - 关键发现
    - 当前进度
    - 下一步行动
    - 执行日志
    """
    
    def __init__(self, task_id: str, memory_dir: str = ".clis_memory"):
        self.task_id = task_id
        self.memory_dir = Path(memory_dir)
        self.tasks_dir = self.memory_dir / "tasks" / "active"
        self.task_file = self.tasks_dir / f"task_{task_id}.md"
        
        # 确保目录存在
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
    
    def load_or_create(self, task_description: str) -> str:
        """
        加载现有任务文档或创建新文档
        
        Args:
            task_description: 用户的任务描述
            
        Returns:
            任务文档内容
        """
        if self.task_file.exists():
            return self.task_file.read_text(encoding='utf-8')
        else:
            return self._create_initial_doc(task_description)
    
    def _create_initial_doc(self, task_description: str) -> str:
        """创建初始任务文档"""
        doc = f"""# Task: {task_description}

**任务ID**: {self.task_id}  
**创建时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**状态**: 🔄 进行中

---

## 📋 任务目标

{task_description}

---

## ✅ 任务分解

<!-- 这里会自动更新任务步骤 -->
- [ ] 步骤将在执行中自动识别

---

## 🔍 关键发现

*(执行中会自动记录)*

---

## 📊 当前进度

**阶段**: 初始化  
**进度**: 0/0

---

## 🎯 下一步行动

开始执行任务...

---

## 📝 执行日志

"""
        self.task_file.write_text(doc, encoding='utf-8')
        return doc
    
    def update_step(self, step_description: str, status: str = "done"):
        """
        更新任务步骤状态
        
        Args:
            step_description: 步骤描述
            status: "done" | "in_progress" | "pending"
        """
        if not self.task_file.exists():
            return
        
        content = self.task_file.read_text(encoding='utf-8')
        
        # 查找任务分解区域
        checklist_pattern = r'(## ✅ 任务分解.*?)(##|\Z)'
        match = re.search(checklist_pattern, content, re.DOTALL)
        
        if match:
            checklist_section = match.group(1)
            
            # 检查是否已存在此步骤
            step_exists = step_description in checklist_section
            
            if not step_exists:
                # 添加新步骤
                checkbox = {
                    "done": "- [x]",
                    "in_progress": "- [ ] 🔄",
                    "pending": "- [ ]"
                }.get(status, "- [ ]")
                
                new_step = f"{checkbox} {step_description}\n"
                
                # 在下一个 ## 前插入
                next_section_pos = content.find('##', match.end(1))
                if next_section_pos != -1:
                    # 在找到的位置前插入
                    insert_pos = content.rfind('\n', match.start(1), next_section_pos)
                    if insert_pos == -1:
                        insert_pos = match.end(1)
                    content = content[:insert_pos] + '\n' + new_step + content[insert_pos:]
                else:
                    # 在结尾插入
                    content = content.rstrip() + '\n' + new_step + '\n'
                
                self.task_file.write_text(content, encoding='utf-8')
    
    def add_finding(self, finding: str, category: str = "general"):
        """
        添加关键发现
        
        Args:
            finding: 发现内容
            category: 分类标签
        """
        if not self.task_file.exists():
            return
        
        content = self.task_file.read_text(encoding='utf-8')
        
        # 查找关键发现区域
        findings_pattern = r'(## 🔍 关键发现.*?)(##|\Z)'
        match = re.search(findings_pattern, content, re.DOTALL)
        
        if match:
            # 添加新发现
            timestamp = datetime.now().strftime('%H:%M:%S')
            new_finding = f"- **[{category}]** ({timestamp}): {finding}\n"
            
            # 在下一个 ## 前插入
            next_section_pos = content.find('##', match.end(1))
            if next_section_pos != -1:
                insert_pos = content.rfind('\n', match.start(1), next_section_pos)
                if insert_pos == -1:
                    insert_pos = match.end(1)
                content = content[:insert_pos] + '\n' + new_finding + content[insert_pos:]
            else:
                content = content.rstrip() + '\n' + new_finding + '\n'
            
            self.task_file.write_text(content, encoding='utf-8')
    
    def update_progress(self, phase: str, progress: str):
        """更新当前进度"""
        if not self.task_file.exists():
            return
        
        content = self.task_file.read_text(encoding='utf-8')
        
        # 更新阶段
        content = re.sub(
            r'\*\*阶段\*\*:.*',
            f'**阶段**: {phase}',
            content
        )
        
        # 更新进度
        content = re.sub(
            r'\*\*进度\*\*:.*',
            f'**进度**: {progress}',
            content
        )
        
        self.task_file.write_text(content, encoding='utf-8')
    
    def update_next_action(self, action: str):
        """更新下一步行动建议"""
        if not self.task_file.exists():
            return
        
        content = self.task_file.read_text(encoding='utf-8')
        
        # 查找下一步行动区域
        next_action_pattern = r'(## 🎯 下一步行动.*?)(##|\Z)'
        match = re.search(next_action_pattern, content, re.DOTALL)
        
        if match:
            new_section = f"## 🎯 下一步行动\n\n{action}\n\n"
            content = content[:match.start(1)] + new_section + content[match.end(1):]
            self.task_file.write_text(content, encoding='utf-8')
    
    def append_log(self, log_entry: str):
        """添加执行日志"""
        if not self.task_file.exists():
            return
        
        content = self.task_file.read_text(encoding='utf-8')
        
        # 在执行日志区域追加
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_line = f"\n[{timestamp}] {log_entry}\n"
        
        content = content.rstrip() + log_line
        self.task_file.write_text(content, encoding='utf-8')
    
    def inject_to_prompt(self, include_log: bool = False) -> str:
        """
        将任务文档注入到 prompt
        
        Args:
            include_log: 是否包含执行日志 (较长)
            
        Returns:
            格式化的 prompt 文本
        """
        if not self.task_file.exists():
            return ""
        
        content = self.task_file.read_text(encoding='utf-8')
        
        if not include_log:
            # 移除执行日志部分 (节省 tokens)
            content = re.sub(r'## 📝 执行日志.*', '', content, flags=re.DOTALL)
        
        return f"""
╭──────────────────────────────────────────────────────────────╮
│              📖 任务记忆 (TASK MEMORY / MEMORY BANK)          │
╰──────────────────────────────────────────────────────────────╯

{content}

⚠️  重要提醒:
   • 检查上方的 ✅ 任务分解,看哪些步骤已完成
   • 查看 🔍 关键发现,已收集的信息就在这里
   • 参考 🎯 下一步行动的建议
   • 如果任务完成,调用 {{"type": "done", "summary": "..."}}
"""
    
    def get_file_path(self) -> Path:
        """获取任务文件路径"""
        return self.task_file
    
    def exists(self) -> bool:
        """检查任务文件是否存在"""
        return self.task_file.exists()
