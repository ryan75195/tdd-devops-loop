"""Hybrid session manager that uses SDK when available, falls back to subprocess."""

import asyncio
import subprocess
from typing import Tuple, Optional, Dict, Any

import anyio
from claude_code_sdk import query, ClaudeCodeOptions

from .config import Configuration, ExecutionContext
from .session_manager import ClaudeSessionManager
from .sdk_session_manager import ClaudeSDKSessionManager


class HybridSessionManager:
    """
    Hybrid session manager that tries to use the Claude Code SDK first,
    but falls back to subprocess calls if the SDK is not available.
    """
    
    def __init__(self, config: Configuration, logger, usage_parser):
        self.config = config
        self.logger = logger
        self.usage_parser = usage_parser
        
        # Try to determine which session manager to use
        self._session_manager = self._select_session_manager()
    
    def _select_session_manager(self):
        """Select the appropriate session manager based on SDK availability."""
        # For now, always try SDK first and fallback at runtime if needed
        # This is more efficient than doing a test query during initialization
        self.logger.info("🚀 Attempting to use Claude Code SDK (with subprocess fallback)")
        return ClaudeSDKSessionManager(self.config, self.logger, self.usage_parser)
    
    def run_single_iteration(self, ticket_number: str) -> Tuple[Optional[Dict], Optional[int], int]:
        """Run a single TDD iteration using the selected session manager."""
        try:
            return self._session_manager.run_single_iteration(ticket_number)
        except Exception as e:
            # If SDK fails at runtime, log the error and potentially fallback
            if isinstance(self._session_manager, ClaudeSDKSessionManager):
                self.logger.warning(f"SDK execution failed: {e}")
                self.logger.info("🔄 Attempting fallback to subprocess method...")
                
                try:
                    # Create subprocess session manager as fallback
                    fallback_manager = ClaudeSessionManager(self.config, self.logger, self.usage_parser)
                    return fallback_manager.run_single_iteration(ticket_number)
                except Exception as fallback_error:
                    self.logger.error(f"Fallback also failed: {fallback_error}")
                    return None, None, 1
            else:
                # Subprocess method failed, no further fallback
                self.logger.error(f"Subprocess execution failed: {e}")
                return None, None, 1