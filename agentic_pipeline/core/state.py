"""State management for agents in the agentic pipeline framework."""

from typing import Any, Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field
import json


@dataclass
class StateSnapshot:
    """A snapshot of agent state at a specific point in time."""
    iteration: int
    timestamp: datetime
    data: Dict[str, Any]
    message: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert snapshot to dictionary."""
        return {
            "iteration": self.iteration,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "message": self.message
        }


class AgentState:
    """
    Manages the evolving state of an agent's execution.
    
    Provides:
    - Current state data storage
    - Historical snapshots
    - Metadata tracking
    - State serialization/deserialization
    """
    
    def __init__(self, initial_data: Optional[Dict[str, Any]] = None):
        """Initialize agent state."""
        self._data = initial_data or {}
        self._metadata = {
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        self._history: List[StateSnapshot] = []
        self._iteration = 0
    
    @property
    def data(self) -> Dict[str, Any]:
        """Get current state data."""
        return self._data.copy()
    
    @property
    def metadata(self) -> Dict[str, Any]:
        """Get state metadata."""
        return self._metadata.copy()
    
    @property
    def iteration(self) -> int:
        """Get current iteration number."""
        return self._iteration
    
    @property
    def history(self) -> List[StateSnapshot]:
        """Get state history."""
        return self._history.copy()
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from state data."""
        return self._data.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set a value in state data."""
        self._data[key] = value
        self._metadata["updated_at"] = datetime.now()
    
    def update(self, data: Dict[str, Any]) -> None:
        """Update state data with new values."""
        self._data.update(data)
        self._metadata["updated_at"] = datetime.now()
    
    def remove(self, key: str) -> Any:
        """Remove and return a value from state data."""
        value = self._data.pop(key, None)
        if value is not None:
            self._metadata["updated_at"] = datetime.now()
        return value
    
    def snapshot(self, message: str = "") -> StateSnapshot:
        """Create a snapshot of current state."""
        snapshot = StateSnapshot(
            iteration=self._iteration,
            timestamp=datetime.now(),
            data=self._data.copy(),
            message=message
        )
        self._history.append(snapshot)
        return snapshot
    
    def advance_iteration(self, message: str = "") -> None:
        """Advance to next iteration and create snapshot."""
        self.snapshot(message)
        self._iteration += 1
    
    def rollback_to_iteration(self, iteration: int) -> bool:
        """
        Rollback state to a specific iteration.
        
        Args:
            iteration: Iteration number to rollback to
            
        Returns:
            True if rollback was successful, False otherwise
        """
        if iteration < 0 or iteration >= len(self._history):
            return False
        
        snapshot = self._history[iteration]
        self._data = snapshot.data.copy()
        self._iteration = iteration
        self._metadata["updated_at"] = datetime.now()
        
        # Remove history entries after the rollback point
        self._history = self._history[:iteration + 1]
        return True
    
    def get_diff(self, from_iteration: int, to_iteration: int) -> Dict[str, Any]:
        """
        Get the difference between two iterations.
        
        Args:
            from_iteration: Starting iteration
            to_iteration: Ending iteration
            
        Returns:
            Dictionary showing changes between iterations
        """
        if (from_iteration < 0 or from_iteration >= len(self._history) or
            to_iteration < 0 or to_iteration >= len(self._history)):
            return {}
        
        from_data = self._history[from_iteration].data
        to_data = self._history[to_iteration].data
        
        diff = {}
        
        # Find added/modified keys
        for key, value in to_data.items():
            if key not in from_data:
                diff[f"+{key}"] = value
            elif from_data[key] != value:
                diff[f"~{key}"] = {"from": from_data[key], "to": value}
        
        # Find removed keys
        for key in from_data:
            if key not in to_data:
                diff[f"-{key}"] = from_data[key]
        
        return diff
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary representation."""
        return {
            "data": self._data,
            "metadata": {
                **self._metadata,
                "created_at": self._metadata["created_at"].isoformat(),
                "updated_at": self._metadata["updated_at"].isoformat()
            },
            "iteration": self._iteration,
            "history": [snapshot.to_dict() for snapshot in self._history]
        }
    
    def to_json(self) -> str:
        """Convert state to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentState':
        """Create AgentState from dictionary representation."""
        state = cls(data.get("data", {}))
        
        # Restore metadata
        metadata = data.get("metadata", {})
        if "created_at" in metadata:
            state._metadata["created_at"] = datetime.fromisoformat(metadata["created_at"])
        if "updated_at" in metadata:
            state._metadata["updated_at"] = datetime.fromisoformat(metadata["updated_at"])
        
        # Restore iteration
        state._iteration = data.get("iteration", 0)
        
        # Restore history
        history_data = data.get("history", [])
        state._history = []
        for snapshot_data in history_data:
            snapshot = StateSnapshot(
                iteration=snapshot_data["iteration"],
                timestamp=datetime.fromisoformat(snapshot_data["timestamp"]),
                data=snapshot_data["data"],
                message=snapshot_data["message"]
            )
            state._history.append(snapshot)
        
        return state
    
    @classmethod
    def from_json(cls, json_str: str) -> 'AgentState':
        """Create AgentState from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)