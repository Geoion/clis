"""
共享记忆模块 - 多 Agent 协作的记忆共享机制

特点:
- 支持多个 Agent 实例之间的记忆共享
- 基于文件系统的简单共享机制
- 支持记忆锁定和并发控制
- 自动同步和合并记忆
"""

from pathlib import Path
from typing import Dict, List, Optional, Any
import json
import time
from datetime import datetime
import threading
import os

from clis.utils.logger import get_logger

logger = get_logger(__name__)


class SimpleLock:
    """简单的基于文件的锁（无需外部依赖）"""
    
    def __init__(self, lock_file: str, timeout: int = 10):
        self.lock_file = Path(lock_file)
        self.timeout = timeout
    
    def __enter__(self):
        """获取锁"""
        start_time = time.time()
        while self.lock_file.exists():
            if time.time() - start_time > self.timeout:
                # 超时，强制删除锁（可能是僵尸锁）
                try:
                    self.lock_file.unlink()
                except:
                    pass
                break
            time.sleep(0.05)
        
        # 创建锁文件
        self.lock_file.touch()
        return self
    
    def __exit__(self, *args):
        """释放锁"""
        try:
            self.lock_file.unlink()
        except:
            pass


class SharedMemory:
    """
    共享记忆 - 多 Agent 协作的记忆共享
    
    使用场景:
    - 多个 Agent 实例协作完成任务
    - 共享发现和知识
    - 避免重复工作
    """
    
    def __init__(self, session_id: str, memory_dir: str = ".clis_memory"):
        self.session_id = session_id
        self.memory_dir = Path(memory_dir)
        self.shared_dir = self.memory_dir / "shared"
        self.session_file = self.shared_dir / f"session_{session_id}.json"
        self.lock_file = self.shared_dir / f"session_{session_id}.lock"
        
        # 确保目录存在
        self.shared_dir.mkdir(parents=True, exist_ok=True)
        
        # Agent ID（自动生成）
        self.agent_id = f"agent_{threading.current_thread().ident}"
        
        # 共享数据
        self.shared_data: Dict[str, Any] = {}
        
        # 加载共享数据
        self._load_shared_data()
    
    def write_finding(self, finding: str, category: str = "general"):
        """
        写入发现到共享记忆
        
        Args:
            finding: 发现内容
            category: 分类
        """
        try:
            with SimpleLock(str(self.lock_file), timeout=2):
                # 重新加载以获取最新数据
                self._load_shared_data()
                
                # 添加发现
                if 'findings' not in self.shared_data:
                    self.shared_data['findings'] = []
                
                self.shared_data['findings'].append({
                    "agent_id": self.agent_id,
                    "category": category,
                    "content": finding,
                    "timestamp": datetime.now().isoformat()
                })
                
                # 保存
                self._save_shared_data()
                
                logger.info(f"Agent {self.agent_id} added finding to shared memory")
        except Exception as e:
            logger.error(f"Failed to write finding: {e}")
            # 降级：直接写入不加锁
            self._load_shared_data()
            if 'findings' not in self.shared_data:
                self.shared_data['findings'] = []
            self.shared_data['findings'].append({
                "agent_id": self.agent_id,
                "category": category,
                "content": finding,
                "timestamp": datetime.now().isoformat()
            })
            self._save_shared_data()
    
    def read_findings(self, category: Optional[str] = None) -> List[Dict]:
        """
        读取共享的发现
        
        Args:
            category: 过滤分类（可选）
            
        Returns:
            发现列表
        """
        try:
            with SimpleLock(str(self.lock_file), timeout=2):
                self._load_shared_data()
                
                findings = self.shared_data.get('findings', [])
                
                if category:
                    findings = [f for f in findings if f.get('category') == category]
                
                return findings
        except:
            # 降级：直接读取不加锁
            self._load_shared_data()
            findings = self.shared_data.get('findings', [])
            if category:
                findings = [f for f in findings if f.get('category') == category]
            return findings
    
    def update_progress(self, task_name: str, status: str, details: Optional[str] = None):
        """
        更新任务进度
        
        Args:
            task_name: 任务名称
            status: 状态（pending, in_progress, completed, failed）
            details: 详细信息
        """
        try:
            with SimpleLock(str(self.lock_file), timeout=2):
                self._load_shared_data()
                
                # 初始化进度字典
                if 'progress' not in self.shared_data:
                    self.shared_data['progress'] = {}
                
                # 更新进度
                self.shared_data['progress'][task_name] = {
                    "agent_id": self.agent_id,
                    "status": status,
                    "details": details,
                    "updated_at": datetime.now().isoformat()
                }
                
                self._save_shared_data()
                
                logger.info(f"Agent {self.agent_id} updated progress: {task_name} -> {status}")
        except Exception as e:
            logger.error(f"Failed to update progress: {e}")
    
    def get_progress(self, task_name: Optional[str] = None) -> Dict:
        """
        获取任务进度
        
        Args:
            task_name: 任务名称（可选，None 返回所有）
            
        Returns:
            进度信息
        """
        try:
            with SimpleLock(str(self.lock_file), timeout=2):
                self._load_shared_data()
                
                progress = self.shared_data.get('progress', {})
                
                if task_name:
                    return progress.get(task_name, {})
                
                return progress
        except:
            # 降级：直接读取
            self._load_shared_data()
            progress = self.shared_data.get('progress', {})
            return progress.get(task_name, {}) if task_name else progress
    
    def register_agent(self, capabilities: Optional[List[str]] = None):
        """
        注册 Agent
        
        Args:
            capabilities: Agent 的能力列表
        """
        try:
            with SimpleLock(str(self.lock_file), timeout=2):
                self._load_shared_data()
                
                if 'agents' not in self.shared_data:
                    self.shared_data['agents'] = {}
                
                self.shared_data['agents'][self.agent_id] = {
                    "capabilities": capabilities or [],
                    "registered_at": datetime.now().isoformat(),
                    "last_seen": datetime.now().isoformat()
                }
                
                self._save_shared_data()
                
                logger.info(f"Agent {self.agent_id} registered")
        except Exception as e:
            logger.error(f"Failed to register agent: {e}")
    
    def get_active_agents(self, timeout_seconds: int = 300) -> List[str]:
        """
        获取活跃的 Agent 列表
        
        Args:
            timeout_seconds: Agent 超时时间（秒）
            
        Returns:
            活跃的 Agent ID 列表
        """
        try:
            with SimpleLock(str(self.lock_file), timeout=2):
                self._load_shared_data()
                
                agents = self.shared_data.get('agents', {})
                cutoff = datetime.now().timestamp() - timeout_seconds
                
                active = []
                for agent_id, info in agents.items():
                    last_seen = datetime.fromisoformat(info.get('last_seen', info['registered_at']))
                    if last_seen.timestamp() > cutoff:
                        active.append(agent_id)
                
                return active
        except:
            return []
    
    def heartbeat(self):
        """更新 Agent 心跳"""
        try:
            with SimpleLock(str(self.lock_file), timeout=2):
                self._load_shared_data()
                
                if 'agents' in self.shared_data and self.agent_id in self.shared_data['agents']:
                    self.shared_data['agents'][self.agent_id]['last_seen'] = datetime.now().isoformat()
                    self._save_shared_data()
        except:
            pass
    
    def to_markdown(self) -> str:
        """转换为 Markdown 用于注入到 prompt"""
        try:
            with SimpleLock(str(self.lock_file), timeout=2):
                self._load_shared_data()
        except:
            self._load_shared_data()
            
            output = f"""## 🤝 共享记忆 (Session: {self.session_id})

**活跃 Agents**: {len(self.get_active_agents())}

### 📋 共享发现 ({len(self.shared_data.get('findings', []))} 条)

"""
            
            # 显示最近的发现
            findings = self.shared_data.get('findings', [])[-10:]  # 最近 10 条
            for finding in findings:
                output += f"- **[{finding.get('category', 'general')}]** ({finding.get('agent_id', 'unknown')}): {finding.get('content', '')}\n"
            
            output += f"""

### 📊 任务进度

"""
            
            # 显示任务进度
            progress = self.shared_data.get('progress', {})
            for task_name, info in progress.items():
                status_emoji = {"pending": "⏳", "in_progress": "🔄", "completed": "✅", "failed": "❌"}
                emoji = status_emoji.get(info.get('status', ''), "❓")
                output += f"- {emoji} **{task_name}**: {info.get('status', 'unknown')} ({info.get('agent_id', 'unknown')})\n"
            
            return output
    
    def _load_shared_data(self):
        """加载共享数据（不加锁，由调用者加锁）"""
        if not self.session_file.exists():
            self.shared_data = {
                "session_id": self.session_id,
                "created_at": datetime.now().isoformat(),
                "findings": [],
                "progress": {},
                "agents": {}
            }
            return
        
        try:
            with open(self.session_file, 'r', encoding='utf-8') as f:
                self.shared_data = json.load(f)
        except Exception as e:
            logger.error(f"Error loading shared data: {e}")
            self.shared_data = {}
    
    def _save_shared_data(self):
        """保存共享数据（不加锁，由调用者加锁）"""
        try:
            with open(self.session_file, 'w', encoding='utf-8') as f:
                json.dump(self.shared_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving shared data: {e}")
