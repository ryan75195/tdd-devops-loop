"""Agent registry for discovery and creation of agents."""

import importlib
import inspect
import os
from typing import Any, Dict, List, Type, Optional, Callable
from pathlib import Path

from .agent import Agent
from .config import AgentConfig


class AgentRegistryError(Exception):
    """Base exception for agent registry errors."""
    pass


class AgentNotFoundError(AgentRegistryError):
    """Raised when an agent type is not found in the registry."""
    pass


class AgentRegistrationError(AgentRegistryError):
    """Raised when there's an error registering an agent."""
    pass


class AgentMetadata:
    """Metadata about a registered agent."""
    
    def __init__(
        self,
        agent_type: str,
        agent_class: Type[Agent],
        description: str = "",
        version: str = "1.0.0",
        author: str = "",
        tags: List[str] = None,
        config_schema: Dict[str, Any] = None
    ):
        self.agent_type = agent_type
        self.agent_class = agent_class
        self.description = description
        self.version = version
        self.author = author
        self.tags = tags or []
        self.config_schema = config_schema or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary."""
        return {
            "agent_type": self.agent_type,
            "class_name": self.agent_class.__name__,
            "module": self.agent_class.__module__,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "tags": self.tags,
            "config_schema": self.config_schema
        }


class AgentRegistry:
    """
    Registry for agent discovery, registration, and creation.
    
    Provides:
    - Agent registration and lookup
    - Automatic discovery from directories
    - Factory pattern for agent creation
    - Configuration validation
    - Plugin-style architecture
    """
    
    def __init__(self):
        """Initialize the agent registry."""
        self._agents: Dict[str, AgentMetadata] = {}
        self._factories: Dict[str, Callable[[AgentConfig], Agent]] = {}
    
    def register_agent(
        self,
        agent_type: str,
        agent_class: Type[Agent],
        description: str = "",
        version: str = "1.0.0",
        author: str = "",
        tags: List[str] = None,
        config_schema: Dict[str, Any] = None,
        factory: Optional[Callable[[AgentConfig], Agent]] = None
    ) -> None:
        """
        Register an agent in the registry.
        
        Args:
            agent_type: Unique identifier for the agent type
            agent_class: Agent class to register
            description: Human-readable description
            version: Agent version
            author: Agent author
            tags: List of tags for categorization
            config_schema: JSON schema for configuration validation
            factory: Optional custom factory function
        """
        if not issubclass(agent_class, Agent):
            raise AgentRegistrationError(f"Class {agent_class} must inherit from Agent")
        
        if agent_type in self._agents:
            raise AgentRegistrationError(f"Agent type '{agent_type}' is already registered")
        
        # Create metadata
        metadata = AgentMetadata(
            agent_type=agent_type,
            agent_class=agent_class,
            description=description,
            version=version,
            author=author,
            tags=tags,
            config_schema=config_schema
        )
        
        # Register agent
        self._agents[agent_type] = metadata
        
        # Register factory
        if factory:
            self._factories[agent_type] = factory
        else:
            # Default factory
            self._factories[agent_type] = lambda config: agent_class(config)
    
    def unregister_agent(self, agent_type: str) -> bool:
        """
        Unregister an agent from the registry.
        
        Args:
            agent_type: Agent type to unregister
            
        Returns:
            True if agent was unregistered, False if not found
        """
        if agent_type in self._agents:
            del self._agents[agent_type]
            del self._factories[agent_type]
            return True
        return False
    
    def get_agent_types(self) -> List[str]:
        """Get list of all registered agent types."""
        return list(self._agents.keys())
    
    def get_agent_metadata(self, agent_type: str) -> AgentMetadata:
        """Get metadata for a specific agent type."""
        if agent_type not in self._agents:
            raise AgentNotFoundError(f"Agent type '{agent_type}' not found")
        return self._agents[agent_type]
    
    def list_agents(self, tag: Optional[str] = None) -> List[AgentMetadata]:
        """
        List all registered agents, optionally filtered by tag.
        
        Args:
            tag: Optional tag to filter by
            
        Returns:
            List of agent metadata
        """
        agents = list(self._agents.values())
        
        if tag:
            agents = [agent for agent in agents if tag in agent.tags]
        
        return agents
    
    def create_agent(self, agent_type: str, config: AgentConfig) -> Agent:
        """
        Create an agent instance using the registry.
        
        Args:
            agent_type: Type of agent to create
            config: Configuration for the agent
            
        Returns:
            Agent instance
            
        Raises:
            AgentNotFoundError: If agent type is not registered
            AgentRegistrationError: If agent creation fails
        """
        if agent_type not in self._agents:
            raise AgentNotFoundError(f"Agent type '{agent_type}' not found")
        
        try:
            factory = self._factories[agent_type]
            agent = factory(config)
            
            # Validate that the created agent is of the expected type
            expected_class = self._agents[agent_type].agent_class
            if not isinstance(agent, expected_class):
                raise AgentRegistrationError(
                    f"Factory for '{agent_type}' returned wrong type: "
                    f"expected {expected_class}, got {type(agent)}"
                )
            
            return agent
            
        except Exception as e:
            raise AgentRegistrationError(f"Failed to create agent '{agent_type}': {e}")
    
    def validate_config(self, agent_type: str, config: AgentConfig) -> List[str]:
        """
        Validate configuration for a specific agent type.
        
        Args:
            agent_type: Agent type to validate for
            config: Configuration to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = config.validate()
        
        if agent_type not in self._agents:
            errors.append(f"Unknown agent type: {agent_type}")
            return errors
        
        # Get agent-specific schema
        metadata = self._agents[agent_type]
        schema = metadata.config_schema
        
        # Basic schema validation (could be extended with jsonschema library)
        if schema:
            for key, requirements in schema.items():
                if requirements.get("required", False) and key not in config.parameters:
                    errors.append(f"Required parameter '{key}' is missing")
                
                if key in config.parameters:
                    value = config.parameters[key]
                    expected_type = requirements.get("type")
                    
                    if expected_type == "string" and not isinstance(value, str):
                        errors.append(f"Parameter '{key}' must be a string")
                    elif expected_type == "integer" and not isinstance(value, int):
                        errors.append(f"Parameter '{key}' must be an integer")
                    elif expected_type == "boolean" and not isinstance(value, bool):
                        errors.append(f"Parameter '{key}' must be a boolean")
        
        return errors
    
    def discover_agents(self, search_paths: List[str]) -> int:
        """
        Discover and register agents from specified directories.
        
        Args:
            search_paths: List of directory paths to search
            
        Returns:
            Number of agents discovered and registered
        """
        discovered_count = 0
        
        for search_path in search_paths:
            path = Path(search_path)
            if not path.exists() or not path.is_dir():
                continue
            
            # Find Python files
            for py_file in path.rglob("*.py"):
                if py_file.name.startswith("__"):
                    continue
                
                try:
                    # Convert file path to module name
                    relative_path = py_file.relative_to(path.parent)
                    module_name = str(relative_path.with_suffix("")).replace(os.sep, ".")
                    
                    # Import the module
                    module = importlib.import_module(module_name)
                    
                    # Find Agent classes
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if (issubclass(obj, Agent) and 
                            obj != Agent and 
                            obj.__module__ == module.__name__):
                            
                            # Try to auto-register
                            agent_type = getattr(obj, 'AGENT_TYPE', name.lower())
                            description = getattr(obj, 'DESCRIPTION', obj.__doc__ or "")
                            version = getattr(obj, 'VERSION', "1.0.0")
                            author = getattr(obj, 'AUTHOR', "")
                            tags = getattr(obj, 'TAGS', [])
                            config_schema = getattr(obj, 'CONFIG_SCHEMA', {})
                            
                            if agent_type not in self._agents:
                                self.register_agent(
                                    agent_type=agent_type,
                                    agent_class=obj,
                                    description=description,
                                    version=version,
                                    author=author,
                                    tags=tags,
                                    config_schema=config_schema
                                )
                                discovered_count += 1
                
                except Exception as e:
                    # Skip files that can't be imported or processed
                    continue
        
        return discovered_count
    
    def get_registry_info(self) -> Dict[str, Any]:
        """Get comprehensive information about the registry."""
        return {
            "total_agents": len(self._agents),
            "agent_types": list(self._agents.keys()),
            "agents": [metadata.to_dict() for metadata in self._agents.values()]
        }


# Global registry instance
_global_registry = AgentRegistry()


def get_registry() -> AgentRegistry:
    """Get the global agent registry instance."""
    return _global_registry


def register_agent(*args, **kwargs) -> None:
    """Register an agent using the global registry."""
    _global_registry.register_agent(*args, **kwargs)


def create_agent(agent_type: str, config: AgentConfig) -> Agent:
    """Create an agent using the global registry."""
    return _global_registry.create_agent(agent_type, config)