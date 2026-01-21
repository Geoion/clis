"""
Intelligent context management for ReAct agents.

Handles observation history compression and critical information retention.
"""

from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from enum import Enum

from clis.config import ConfigManager
from clis.utils.logger import get_logger

logger = get_logger(__name__)


class ObservationType(Enum):
    """Types of observations for prioritization."""
    TOOL_RESULT = "tool_result"
    COMMAND_RESULT = "command_result"
    ERROR = "error"
    REJECTION = "rejection"  # User rejected operation
    SUCCESS = "success"
    INFO = "info"


@dataclass
class Observation:
    """Structured observation with metadata."""
    content: str
    type: ObservationType
    iteration: int
    is_critical: bool = False
    tool_name: Optional[str] = None
    success: bool = True  # New: whether operation succeeded
    
    def __str__(self) -> str:
        """String representation for context."""
        prefix = "⚠️ CRITICAL" if self.is_critical else ""
        if prefix:
            return f"{prefix} [{self.type.value}] {self.content}"
        return f"[{self.type.value}] {self.content}"
    
    def get_signature(self) -> str:
        """Get observation signature for duplicate detection."""
        # Use tool name + first 100 chars of content as signature
        content_prefix = self.content[:100] if self.content else ""
        return f"{self.tool_name}:{content_prefix}"


class ContextManager:
    """
    Intelligent context manager for ReAct agents.
    
    Features:
    - Automatic compression when observations exceed threshold
    - Critical information retention (errors, rejections)
    - Recent observations always kept
    - Summarization of middle observations
    """
    
    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """
        Initialize context manager.
        
        Args:
            config_manager: Configuration manager
        """
        self.config_manager = config_manager or ConfigManager()
        
        # Load configuration
        try:
            safety_config = self.config_manager.load_safety_config()
            self.context_config = safety_config.context_management
        except Exception as e:
            logger.warning(f"Failed to load context config: {e}, using defaults")
            from clis.config.models import ContextManagementConfig
            self.context_config = ContextManagementConfig()
        
        # Observation storage
        self.observations: List[Observation] = []
        self.current_iteration = 0
        
        # Duplicate operation detection
        self.recent_failed_operations: List[str] = []  # Recent failed operation signatures
        self.duplicate_warning_count = 0  # Duplicate warning count
    
    def add_observation(
        self,
        content: str,
        obs_type: ObservationType = ObservationType.INFO,
        is_critical: bool = False,
        tool_name: Optional[str] = None,
        success: bool = True
    ) -> None:
        """
        Add an observation to the context.
        
        Args:
            content: Observation content
            obs_type: Type of observation
            is_critical: Whether this is critical information
            tool_name: Name of tool if this is a tool result
            success: Whether the operation succeeded
        """
        if not self.context_config.enabled:
            # Simple mode: just append
            self.observations.append(Observation(
                content=content,
                type=obs_type,
                iteration=self.current_iteration,
                is_critical=is_critical,
                tool_name=tool_name,
                success=success
            ))
            return
        
        # Mark errors and rejections as critical automatically
        if obs_type in [ObservationType.ERROR, ObservationType.REJECTION]:
            is_critical = True
        
        obs = Observation(
            content=content,
            type=obs_type,
            iteration=self.current_iteration,
            is_critical=is_critical,
            tool_name=tool_name,
            success=success
        )
        
        # Detect duplicate failed operations
        if not success and tool_name:
            signature = obs.get_signature()
            self.recent_failed_operations.append(signature)
            
            # Keep only the last 5 failed operations
            if len(self.recent_failed_operations) > 5:
                self.recent_failed_operations = self.recent_failed_operations[-5:]
            
            # Detect if duplicate failure (same operation appears 2 times in last 3 attempts)
            recent_3 = self.recent_failed_operations[-3:]
            if recent_3.count(signature) >= 2:
                self.duplicate_warning_count += 1
                logger.warning(f"Detected duplicate failed operation: {tool_name}, count: {self.duplicate_warning_count}")
        
        self.observations.append(obs)
        
        # Compress if needed (intelligent compression of duplicate invalid operations)
        if len(self.observations) > self.context_config.compression_threshold:
            self._compress()
    
    def add_rejection(self, command: str, reason: str = "User rejected") -> None:
        """
        Add a user rejection to context.
        
        Args:
            command: The rejected command
            reason: Reason for rejection
        """
        content = f"{reason}: {command}"
        self.add_observation(
            content=content,
            obs_type=ObservationType.REJECTION,
            is_critical=True
        )
        logger.info(f"Recorded rejection: {command}")
    
    def next_iteration(self) -> None:
        """Mark the start of a new iteration."""
        self.current_iteration += 1
    
    def get_context(self, max_observations: Optional[int] = None) -> str:
        """
        Get formatted context for LLM.
        
        Args:
            max_observations: Maximum observations to include (None = use config)
            
        Returns:
            Formatted context string
        """
        if not self.observations:
            return "No previous observations."
        
        max_obs = max_observations or self.context_config.max_observations
        
        # Get observations to include
        if len(self.observations) <= max_obs:
            obs_to_include = self.observations
        else:
            obs_to_include = self._select_observations(max_obs)
        
        # Format observations
        formatted = []
        for i, obs in enumerate(obs_to_include, 1):
            formatted.append(f"{i}. {obs}")
        
        return "\n".join(formatted)
    
    def _select_observations(self, max_count: int) -> List[Observation]:
        """
        Select most important observations to keep.
        
        Strategy:
        1. Always keep critical observations
        2. Always keep recent N observations
        3. Fill remaining with important observations
        
        Args:
            max_count: Maximum observations to return
            
        Returns:
            Selected observations
        """
        # 1. Critical observations
        critical = [obs for obs in self.observations if obs.is_critical]
        
        # 2. Recent observations
        keep_recent = self.context_config.keep_recent
        recent = self.observations[-keep_recent:]
        
        # Combine (avoid duplicates)
        selected = []
        seen_content = set()
        
        # Add critical first
        for obs in critical:
            if obs.content not in seen_content:
                selected.append(obs)
                seen_content.add(obs.content)
        
        # Add recent
        for obs in recent:
            if obs.content not in seen_content:
                selected.append(obs)
                seen_content.add(obs.content)
        
        # If we still have space, add other observations
        remaining_space = max_count - len(selected)
        if remaining_space > 0:
            other = [
                obs for obs in self.observations
                if obs not in selected
            ]
            # Take from middle (not too old, not too recent)
            if len(other) > remaining_space:
                # Sample evenly from middle
                step = len(other) // remaining_space
                other = other[::step][:remaining_space]
            
            selected.extend(other)
        
        # Sort by iteration to maintain chronological order
        selected.sort(key=lambda obs: obs.iteration)
        
        return selected[:max_count]
    
    def _compress(self) -> None:
        """
        Compress observations when threshold is exceeded.
        
        Strategy:
        - Keep critical observations
        - Keep recent observations
        - Remove duplicate failed operations (intelligent compression)
        - Summarize/remove middle observations
        """
        if not self.context_config.keep_critical:
            # Simple truncation
            max_obs = self.context_config.max_observations
            self.observations = self.observations[-max_obs:]
            logger.debug(f"Compressed observations to {len(self.observations)}")
            return
        
        # Intelligent compression
        critical = [obs for obs in self.observations if obs.is_critical]
        keep_recent = self.context_config.keep_recent
        recent = self.observations[-keep_recent:]
        
        # Middle observations (not critical, not recent)
        middle = [
            obs for obs in self.observations
            if obs not in critical and obs not in recent
        ]
        
        # Intelligent compression: remove duplicate failed operations
        middle_compressed = self._remove_duplicate_failures(middle)
        compressed_count = len(middle) - len(middle_compressed)
        if compressed_count > 0:
            logger.info(f"Compressed {compressed_count} duplicate failed operations")
        
        # Calculate how many middle observations we can keep
        max_obs = self.context_config.max_observations
        available_space = max_obs - len(critical) - len(recent)
        
        if available_space > 0 and len(middle_compressed) > available_space:
            # Sample middle observations
            step = len(middle_compressed) // available_space
            middle_compressed = middle_compressed[::step][:available_space]
        elif available_space <= 0:
            middle_compressed = []
        
        # Rebuild observations list
        self.observations = critical + middle_compressed + recent
        
        logger.info(
            f"Compressed context: {len(critical)} critical, "
            f"{len(middle_compressed)} middle, {len(recent)} recent"
        )
    
    def _remove_duplicate_failures(self, observations: List[Observation]) -> List[Observation]:
        """
        Remove duplicate failed operations, keeping only first and last occurrences.
        
        Args:
            observations: List of observations
            
        Returns:
            Compressed observation list
        """
        if len(observations) <= 3:
            return observations
        
        # Count occurrences of each signature
        signature_occurrences: Dict[str, List[Observation]] = {}
        for obs in observations:
            if not obs.success and obs.tool_name:
                sig = obs.get_signature()
                if sig not in signature_occurrences:
                    signature_occurrences[sig] = []
                signature_occurrences[sig].append(obs)
        
        # For duplicate failed operations, keep only first and last occurrences
        kept_observations = []
        removed_signatures = set()
        
        for obs in observations:
            sig = obs.get_signature() if (not obs.success and obs.tool_name) else None
            
            if sig and sig in signature_occurrences:
                occurrences = signature_occurrences[sig]
                # If repeated more than 2 times, keep only first and last
                if len(occurrences) > 2:
                    if obs == occurrences[0] or obs == occurrences[-1]:
                        kept_observations.append(obs)
                    elif sig not in removed_signatures:
                        # Add a summary observation when first removing duplicates
                        summary = f"[Compressed] {obs.tool_name} failed {len(occurrences)-2} times (compressed)"
                        kept_observations.append(Observation(
                            content=summary,
                            type=ObservationType.INFO,
                            iteration=obs.iteration,
                            is_critical=False,
                            tool_name=obs.tool_name,
                            success=False
                        ))
                        removed_signatures.add(sig)
                else:
                    kept_observations.append(obs)
            else:
                kept_observations.append(obs)
        
        return kept_observations
    
    def get_summary(self) -> Dict[str, int]:
        """
        Get summary statistics.
        
        Returns:
            Dictionary with statistics
        """
        return {
            "total": len(self.observations),
            "critical": sum(1 for obs in self.observations if obs.is_critical),
            "errors": sum(1 for obs in self.observations if obs.type == ObservationType.ERROR),
            "rejections": sum(1 for obs in self.observations if obs.type == ObservationType.REJECTION),
            "iterations": self.current_iteration,
            "duplicate_warnings": self.duplicate_warning_count
        }
    
    def has_duplicate_failures(self) -> bool:
        """
        Check if there are duplicate failed operations.
        
        Returns:
            True if duplicate failures detected
        """
        return self.duplicate_warning_count >= 2
    
    def get_duplicate_warning_message(self) -> Optional[str]:
        """
        Get duplicate operation warning message.
        
        Returns:
            Warning message if duplicates detected, None otherwise
        """
        if self.duplicate_warning_count >= 3:
            return (
                "🚨 Detected multiple duplicate failed operations! Try a different approach:\n"
                "1. Check if prerequisites are met (e.g., files/directories exist)\n"
                "2. Try using different tools or commands\n"
                "3. Analyze failure reasons and adjust strategy"
            )
        elif self.duplicate_warning_count >= 2:
            return (
                "⚠️ Detected duplicate failed operations, suggest changing strategy:\n"
                "- Check operation prerequisites\n"
                "- Try different implementation approaches"
            )
        return None
    
    def clear(self) -> None:
        """Clear all observations."""
        self.observations.clear()
        self.current_iteration = 0
        logger.debug("Cleared context")
