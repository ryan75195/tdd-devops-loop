"""Abstract base class for all agents in the agentic pipeline framework."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass
from enum import Enum

from .state import AgentState
from .config import AgentConfig


class AgentStatus(Enum):
    """Status of an agent's execution."""
    INITIALIZING = "initializing"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass
class AgentResult:
    """Result of an agent's execution iteration."""
    status: AgentStatus
    message: str
    data: Dict[str, Any]
    terminal: bool = False
    error: Optional[str] = None


class Agent(ABC):
    """
    Abstract base class for all agents in the agentic pipeline framework.
    
    Agents follow a standard lifecycle:
    1. initialize() - Setup the agent with configuration and context
    2. execute_iteration() - Perform one iteration of the agent's work
    3. check_terminal_condition() - Determine if the agent should stop
    4. finalize() - Cleanup and prepare final results
    """
    
    def __init__(self, config: AgentConfig):
        """Initialize the agent with configuration."""
        self.config = config
        self.status = AgentStatus.INITIALIZING
        self.iteration_count = 0
        self._logger = None
    
    @property
    def name(self) -> str:
        """Get the agent's name."""
        return self.config.name
    
    @property
    def agent_type(self) -> str:
        """Get the agent's type identifier."""
        return self.config.agent_type
    
    def set_logger(self, logger) -> None:
        """Set the logger for this agent."""
        self._logger = logger
    
    def log(self, level: str, message: str) -> None:
        """Log a message if logger is available."""
        if self._logger:
            getattr(self._logger, level, self._logger.info)(f"[{self.name}] {message}")
    
    @abstractmethod
    def initialize(self, context: Dict[str, Any]) -> None:
        """
        Initialize the agent with the given context.
        
        Args:
            context: Dictionary containing initialization context
                    (e.g., project_path, working_directory, etc.)
        """
        pass
    
    @abstractmethod
    def execute_iteration(self, state: AgentState) -> AgentResult:
        """
        Execute one iteration of the agent's work.
        
        Args:
            state: Current state of the agent's execution
            
        Returns:
            AgentResult containing the outcome of this iteration
        """
        pass
    
    @abstractmethod
    def check_terminal_condition(self, state: AgentState) -> bool:
        """
        Check if the agent should terminate based on current state.
        
        Args:
            state: Current state of the agent's execution
            
        Returns:
            True if the agent should stop, False to continue
        """
        pass
    
    def finalize(self, state: AgentState) -> Dict[str, Any]:
        """
        Finalize the agent's execution and return final results.
        
        Args:
            state: Final state of the agent's execution
            
        Returns:
            Dictionary containing final results and metadata
        """
        return {
            "agent_name": self.name,
            "agent_type": self.agent_type,
            "iterations": self.iteration_count,
            "final_status": self.status.value,
            "final_state": state.to_dict()
        }
    
    def pre_iteration_hook(self, state: AgentState) -> None:
        """Hook called before each iteration. Override for custom behavior."""
        pass
    
    def post_iteration_hook(self, state: AgentState, result: AgentResult) -> None:
        """Hook called after each iteration. Override for custom behavior."""
        pass
    
    def on_error(self, error: Exception, state: AgentState) -> AgentResult:
        """
        Handle errors during agent execution.
        
        Args:
            error: The exception that occurred
            state: Current state when error occurred
            
        Returns:
            AgentResult describing how to handle the error
        """
        self.status = AgentStatus.FAILED
        return AgentResult(
            status=AgentStatus.FAILED,
            message=f"Agent {self.name} encountered an error",
            data={},
            terminal=True,
            error=str(error)
        )