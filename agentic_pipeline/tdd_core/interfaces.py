"""Abstract base classes and interfaces for TDD DevOps Loop."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Protocol

from .config import ExecutionContext


class ToolHandler(ABC):
    """Abstract base class for handling specific tool types."""
    
    @abstractmethod
    def handle(self, tool_input: Dict[str, Any], logger: 'Logger') -> None:
        """Handle a specific tool invocation."""
        pass


class JsonParser(ABC):
    """Abstract base class for JSON parsing strategies."""
    
    @abstractmethod
    def try_parse(self, text: str) -> Optional[Dict[str, Any]]:
        """Attempt to parse JSON from text. Return None if unable."""
        pass


class EventHandler(ABC):
    """Abstract base class for event handling."""
    
    @abstractmethod
    def handle(self, event: Dict[str, Any], context: ExecutionContext) -> Optional[int]:
        """Handle an event and optionally return usage limit epoch."""
        pass


class EventObserver(Protocol):
    """Protocol for event observers."""
    
    def on_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Called when an event occurs."""
        ...