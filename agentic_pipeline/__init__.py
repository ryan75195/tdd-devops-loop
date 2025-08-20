"""
Agentic Pipeline - A generic framework for creating and orchestrating AI agents.

This package provides a flexible architecture for building iterative agentic workflows
with configurable terminal conditions, state management, and composition capabilities.
"""

__version__ = "1.0.0"
__author__ = "Agentic Pipeline Framework"

from .core.agent import Agent
from .core.pipeline import AgentPipeline
from .core.state import AgentState
from .core.config import AgentConfig
from .core.registry import AgentRegistry

__all__ = [
    'Agent', 
    'AgentPipeline', 
    'AgentState', 
    'AgentConfig', 
    'AgentRegistry'
]