"""Configuration management for agents in the agentic pipeline framework."""

from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
import json


class TerminalConditionType(Enum):
    """Types of terminal conditions for agents."""
    MAX_ITERATIONS = "max_iterations"
    SUCCESS_STATUS = "success_status"
    ERROR_STATUS = "error_status"
    CUSTOM_CONDITION = "custom_condition"
    TIMEOUT = "timeout"
    STATE_CONDITION = "state_condition"


@dataclass
class TerminalCondition:
    """Configuration for a terminal condition."""
    type: TerminalConditionType
    value: Any
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.type.value,
            "value": self.value,
            "description": self.description
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TerminalCondition':
        """Create from dictionary."""
        return cls(
            type=TerminalConditionType(data["type"]),
            value=data["value"],
            description=data.get("description", "")
        )


@dataclass
class AgentConfig:
    """
    Configuration for an agent in the agentic pipeline framework.
    
    Provides:
    - Agent identification (name, type)
    - Execution parameters
    - Terminal conditions
    - Agent-specific parameters
    - Hooks and extensions
    """
    
    # Core identification
    name: str
    agent_type: str
    description: str = ""
    
    # Execution parameters
    max_iterations: int = 50
    timeout_seconds: Optional[int] = None
    enable_logging: bool = True
    log_level: str = "INFO"
    
    # Terminal conditions
    terminal_conditions: List[TerminalCondition] = field(default_factory=list)
    
    # Agent-specific parameters
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Environment and context
    working_directory: Optional[str] = None
    environment_variables: Dict[str, str] = field(default_factory=dict)
    
    # Hooks and extensions
    pre_hooks: List[str] = field(default_factory=list)
    post_hooks: List[str] = field(default_factory=list)
    error_hooks: List[str] = field(default_factory=list)
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize default terminal conditions if none provided."""
        if not self.terminal_conditions:
            self.terminal_conditions.append(
                TerminalCondition(
                    type=TerminalConditionType.MAX_ITERATIONS,
                    value=self.max_iterations,
                    description=f"Stop after {self.max_iterations} iterations"
                )
            )
    
    def get_parameter(self, key: str, default: Any = None) -> Any:
        """Get an agent-specific parameter."""
        return self.parameters.get(key, default)
    
    def set_parameter(self, key: str, value: Any) -> None:
        """Set an agent-specific parameter."""
        self.parameters[key] = value
    
    def add_terminal_condition(self, condition: TerminalCondition) -> None:
        """Add a terminal condition."""
        self.terminal_conditions.append(condition)
    
    def remove_terminal_condition(self, condition_type: TerminalConditionType) -> bool:
        """Remove terminal conditions of a specific type."""
        original_length = len(self.terminal_conditions)
        self.terminal_conditions = [
            tc for tc in self.terminal_conditions 
            if tc.type != condition_type
        ]
        return len(self.terminal_conditions) < original_length
    
    def get_terminal_conditions(self, condition_type: TerminalConditionType) -> List[TerminalCondition]:
        """Get terminal conditions of a specific type."""
        return [tc for tc in self.terminal_conditions if tc.type == condition_type]
    
    def validate(self) -> List[str]:
        """
        Validate the configuration.
        
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        if not self.name:
            errors.append("Agent name is required")
        
        if not self.agent_type:
            errors.append("Agent type is required")
        
        if self.max_iterations <= 0:
            errors.append("max_iterations must be positive")
        
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            errors.append("timeout_seconds must be positive")
        
        if self.log_level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            errors.append("log_level must be a valid logging level")
        
        # Validate terminal conditions
        for i, tc in enumerate(self.terminal_conditions):
            if tc.type == TerminalConditionType.MAX_ITERATIONS and not isinstance(tc.value, int):
                errors.append(f"Terminal condition {i}: MAX_ITERATIONS value must be an integer")
            elif tc.type == TerminalConditionType.TIMEOUT and not isinstance(tc.value, (int, float)):
                errors.append(f"Terminal condition {i}: TIMEOUT value must be a number")
        
        return errors
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "name": self.name,
            "agent_type": self.agent_type,
            "description": self.description,
            "max_iterations": self.max_iterations,
            "timeout_seconds": self.timeout_seconds,
            "enable_logging": self.enable_logging,
            "log_level": self.log_level,
            "terminal_conditions": [tc.to_dict() for tc in self.terminal_conditions],
            "parameters": self.parameters,
            "working_directory": self.working_directory,
            "environment_variables": self.environment_variables,
            "pre_hooks": self.pre_hooks,
            "post_hooks": self.post_hooks,
            "error_hooks": self.error_hooks,
            "tags": self.tags,
            "metadata": self.metadata
        }
    
    def to_json(self) -> str:
        """Convert configuration to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentConfig':
        """Create configuration from dictionary."""
        # Extract terminal conditions
        terminal_conditions = []
        for tc_data in data.get("terminal_conditions", []):
            terminal_conditions.append(TerminalCondition.from_dict(tc_data))
        
        return cls(
            name=data["name"],
            agent_type=data["agent_type"],
            description=data.get("description", ""),
            max_iterations=data.get("max_iterations", 50),
            timeout_seconds=data.get("timeout_seconds"),
            enable_logging=data.get("enable_logging", True),
            log_level=data.get("log_level", "INFO"),
            terminal_conditions=terminal_conditions,
            parameters=data.get("parameters", {}),
            working_directory=data.get("working_directory"),
            environment_variables=data.get("environment_variables", {}),
            pre_hooks=data.get("pre_hooks", []),
            post_hooks=data.get("post_hooks", []),
            error_hooks=data.get("error_hooks", []),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {})
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> 'AgentConfig':
        """Create configuration from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    @classmethod
    def create_simple(
        cls, 
        name: str, 
        agent_type: str, 
        max_iterations: int = 50,
        **parameters
    ) -> 'AgentConfig':
        """Create a simple configuration with common defaults."""
        return cls(
            name=name,
            agent_type=agent_type,
            max_iterations=max_iterations,
            parameters=parameters
        )