"""
TDD DevOps Loop - A clean, maintainable implementation for automated TDD workflows.

This package provides object-oriented tools for orchestrating Test-Driven Development
workflows with Claude Code integration.
"""

__version__ = "2.0.0"
__author__ = "Claude Code Refactored"

from .core.loop import TDDDevOpsLoop
from .core.config import Configuration

__all__ = ['TDDDevOpsLoop', 'Configuration']