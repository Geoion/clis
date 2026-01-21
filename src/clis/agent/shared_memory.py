"""
Shared Memory Module - Memory sharing mechanism for multi-Agent collaboration

Features:
- Support memory sharing between multiple Agent instances
- Simple file-system-based sharing mechanism
- Support memory locking and concurrency control
- Automatic synchronization and memory merging
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
    """Simple file-based lock (no external dependencies)"""
    
    def __init__(self, lock_file: str, timeout: int = 10):
        self.lock_file = Path(lock_file)
        self.timeout = timeout
    
    def __enter__(self):
        """Acquire lock"""
        start_time = time.time()
        while self.lock_file.exists():
            if time.time() - start_time > self.timeout:
                # Timeout, force delete lock (may be zombie lock)
                try:
                    self.lock_file.unlink()
                except:
                    pass
                break
            time.sleep(0.05)
        
        # Create lock file
        self.lock_file.touch()
        return self
    
    def __exit__(self, *args):
        """Release lock"""
        try:
            self.lock_file.unlink()
        except:
            pass


class SharedMemory:
    """
    Shared Memory - Memory sharing for multi-Agent collaboration
    
    Use cases:
    - Multiple Agent instances collaborate to complete tasks
    - Share discoveries and knowledge
    - Avoid duplicate work
    """
    
    def __init__(self, session_id: str, memory_dir: str = ".clis_memory"):
        self.session_id = session_id
        self.memory_dir = Path(memory_dir)
        self.shared_dir = self.memory_dir / "shared"
        self.session_file = self.shared_dir / f"session_{session_id}.json"
        self.lock_file = self.shared_dir / f"session_{session_id}.lock"
        
        # Ensure directory exists
        self.shared_dir.mkdir(parents=True, exist_ok=True)
        
        # Agent ID (auto-generated)
        self.agent_id = f"agent_{threading.current_thread().ident}"
        
        # Shared data
        self.shared_data: Dict[str, Any] = {}
        
        # Load shared data
        self._load_shared_data()
    
    def write_finding(self, finding: str, category: str = "general"):
        """
        Write finding to shared memory
        
        Args:
            finding: Finding content
            category: Category
        """
        try:
            with SimpleLock(str(self.lock_file), timeout=2):
                # Reload to get latest data
                self._load_shared_data()
                
                # Add finding
                if 'findings' not in self.shared_data:
                    self.shared_data['findings'] = []
                
                self.shared_data['findings'].append({
                    "agent_id": self.agent_id,
                    "category": category,
                    "content": finding,
                    "timestamp": datetime.now().isoformat()
                })
                
                # Save
                self._save_shared_data()
                
                logger.info(f"Agent {self.agent_id} added finding to shared memory")
        except Exception as e:
            logger.error(f"Failed to write finding: {e}")
            # Fallback: write directly without lock
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
        Read shared findings
        
        Args:
            category: Filter by category (optional)
            
        Returns:
            List of findings
        """
        try:
            with SimpleLock(str(self.lock_file), timeout=2):
                self._load_shared_data()
                
                findings = self.shared_data.get('findings', [])
                
                if category:
                    findings = [f for f in findings if f.get('category') == category]
                
                return findings
        except:
            # Fallback: read directly without lock
            self._load_shared_data()
            findings = self.shared_data.get('findings', [])
            if category:
                findings = [f for f in findings if f.get('category') == category]
            return findings
    
    def update_progress(self, task_name: str, status: str, details: Optional[str] = None):
        """
        Update task progress
        
        Args:
            task_name: Task name
            status: Status (pending, in_progress, completed, failed)
            details: Detailed information
        """
        try:
            with SimpleLock(str(self.lock_file), timeout=2):
                self._load_shared_data()
                
                # Initialize progress dictionary
                if 'progress' not in self.shared_data:
                    self.shared_data['progress'] = {}
                
                # Update progress
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
        Get task progress
        
        Args:
            task_name: Task name (optional, None returns all)
            
        Returns:
            Progress information
        """
        try:
            with SimpleLock(str(self.lock_file), timeout=2):
                self._load_shared_data()
                
                progress = self.shared_data.get('progress', {})
                
                if task_name:
                    return progress.get(task_name, {})
                
                return progress
        except:
            # Fallback: read directly
            self._load_shared_data()
            progress = self.shared_data.get('progress', {})
            return progress.get(task_name, {}) if task_name else progress
    
    def register_agent(self, capabilities: Optional[List[str]] = None):
        """
        Register Agent
        
        Args:
            capabilities: List of Agent capabilities
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
        Get list of active Agents
        
        Args:
            timeout_seconds: Agent timeout in seconds
            
        Returns:
            List of active Agent IDs
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
        """Update Agent heartbeat"""
        try:
            with SimpleLock(str(self.lock_file), timeout=2):
                self._load_shared_data()
                
                if 'agents' in self.shared_data and self.agent_id in self.shared_data['agents']:
                    self.shared_data['agents'][self.agent_id]['last_seen'] = datetime.now().isoformat()
                    self._save_shared_data()
        except:
            pass
    
    def to_markdown(self) -> str:
        """Convert to Markdown for injection into prompt"""
        try:
            with SimpleLock(str(self.lock_file), timeout=2):
                self._load_shared_data()
        except:
            self._load_shared_data()
            
            output = f"""## 🤝 Shared Memory (Session: {self.session_id})

**Active Agents**: {len(self.get_active_agents())}

### 📋 Shared Findings ({len(self.shared_data.get('findings', []))} items)

"""
            
            # Show recent findings
            findings = self.shared_data.get('findings', [])[-10:]  # Last 10 items
            for finding in findings:
                output += f"- **[{finding.get('category', 'general')}]** ({finding.get('agent_id', 'unknown')}): {finding.get('content', '')}\n"
            
            output += f"""

### 📊 Task Progress

"""
            
            # Show task progress
            progress = self.shared_data.get('progress', {})
            for task_name, info in progress.items():
                status_emoji = {"pending": "⏳", "in_progress": "🔄", "completed": "✅", "failed": "❌"}
                emoji = status_emoji.get(info.get('status', ''), "❓")
                output += f"- {emoji} **{task_name}**: {info.get('status', 'unknown')} ({info.get('agent_id', 'unknown')})\n"
            
            return output
    
    def _load_shared_data(self):
        """Load shared data (no locking, caller should lock)"""
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
        """Save shared data (no locking, caller should lock)"""
        try:
            with open(self.session_file, 'w', encoding='utf-8') as f:
                json.dump(self.shared_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving shared data: {e}")
