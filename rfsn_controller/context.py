"""Controller context object passed throughout execution.

This module defines ControllerContext, a single object that holds all
runtime state and eliminates global configuration drift.
"""

from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from .config import ControllerConfig
    from .repo_index import RepoIndex
    from .planner import PlanDAG
    from .policy_bandit import ThompsonBandit


@dataclass
class EventLog:
    """Append-only structured event log."""
    
    path: Path
    events: List[Dict[str, Any]] = field(default_factory=list)
    
    def __post_init__(self) -> None:
        """Ensure the output directory exists."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
    
    def emit(self, event_type: str, **data: Any) -> None:
        """Emit a structured event to the log.
        
        Args:
            event_type: Type of event (e.g., "step_start", "patch_applied").
            **data: Additional event data.
        """
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            **data,
        }
        self.events.append(event)
        
        # Append to file immediately for durability
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, default=str) + "\n")
    
    def get_events(self, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get events, optionally filtered by type.
        
        Args:
            event_type: Optional type to filter by.
            
        Returns:
            List of matching events.
        """
        if event_type is None:
            return self.events.copy()
        return [e for e in self.events if e.get("type") == event_type]


@dataclass
class ControllerContext:
    """Central context object passed throughout controller execution.
    
    This eliminates global state and ensures all components have access
    to the same configuration and runtime objects.
    """
    
    config: "ControllerConfig"
    event_log: EventLog
    rng: random.Random = field(init=False)
    
    # Lazy-initialized components
    _sandbox: Any = field(default=None, repr=False)
    _repo_index: Optional["RepoIndex"] = field(default=None, repr=False)
    _plan: Optional["PlanDAG"] = field(default=None, repr=False)
    _policy: Optional["ThompsonBandit"] = field(default=None, repr=False)
    
    def __post_init__(self) -> None:
        """Initialize the seeded RNG."""
        self.rng = random.Random(self.config.seed)
        self.event_log.emit("context_initialized", seed=self.config.seed)
    
    @property
    def output_dir(self) -> Path:
        """Get the output directory path."""
        return Path(self.config.output_dir)
    
    @property
    def sandbox(self) -> Any:
        """Get the sandbox instance."""
        return self._sandbox
    
    @sandbox.setter
    def sandbox(self, value: Any) -> None:
        """Set the sandbox instance."""
        self._sandbox = value
    
    @property
    def repo_index(self) -> Optional["RepoIndex"]:
        """Get the repo index if enabled and built."""
        return self._repo_index
    
    @repo_index.setter
    def repo_index(self, value: "RepoIndex") -> None:
        """Set the repo index."""
        self._repo_index = value
        self.event_log.emit("repo_index_set", files=len(value.files) if value else 0)
    
    @property
    def plan(self) -> Optional["PlanDAG"]:
        """Get the current execution plan."""
        return self._plan
    
    @plan.setter
    def plan(self, value: "PlanDAG") -> None:
        """Set the execution plan."""
        self._plan = value
        self.event_log.emit("plan_set", nodes=len(value.nodes) if value else 0)
    
    @property
    def policy(self) -> Optional["ThompsonBandit"]:
        """Get the learning policy."""
        return self._policy
    
    @policy.setter
    def policy(self, value: "ThompsonBandit") -> None:
        """Set the learning policy."""
        self._policy = value
        self.event_log.emit("policy_set", mode=self.config.policy_mode)
    
    def save_plan(self) -> Optional[str]:
        """Save the current plan to disk.
        
        Returns:
            Path to the saved plan file, or None if no plan.
        """
        if self._plan is None:
            return None
        
        plan_path = self.output_dir / self.config.plan_file
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(plan_path, "w", encoding="utf-8") as f:
            json.dump(self._plan.to_json(), f, indent=2)
        
        self.event_log.emit("plan_saved", path=str(plan_path))
        return str(plan_path)


def create_context(config: "ControllerConfig") -> ControllerContext:
    """Create a new ControllerContext from configuration.
    
    Args:
        config: The controller configuration.
        
    Returns:
        Initialized ControllerContext.
    """
    # Ensure output directory exists
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create event log
    events_path = output_dir / config.events_file
    event_log = EventLog(path=events_path)
    
    return ControllerContext(config=config, event_log=event_log)
