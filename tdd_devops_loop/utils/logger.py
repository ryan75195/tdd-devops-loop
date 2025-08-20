"""Logging utility for TDD DevOps Loop."""

import time
import math
from datetime import datetime, timezone
from typing import Dict, Any


class Logger:
    """Handles timestamped console output with consistent formatting."""
    
    @staticmethod
    def get_timestamp() -> str:
        """Get current timestamp for logging."""
        return datetime.now().strftime("%H:%M:%S")
    
    def info(self, message: str) -> None:
        """Log an info message with timestamp."""
        timestamp = self.get_timestamp()
        print(f"[{timestamp}] {message}")
    
    def warning(self, message: str) -> None:
        """Log a warning message with timestamp."""
        timestamp = self.get_timestamp()
        print(f"[{timestamp}] ⚠️  {message}")
    
    def error(self, message: str) -> None:
        """Log an error message with timestamp."""
        timestamp = self.get_timestamp()
        print(f"[{timestamp}] ❌ {message}")
    
    def success(self, message: str) -> None:
        """Log a success message with timestamp."""
        timestamp = self.get_timestamp()
        print(f"[{timestamp}] ✅ {message}")
    
    def tool_action(self, tool_name: str, action_description: str) -> None:
        """Log tool usage with appropriate emoji and timestamp."""
        timestamp = self.get_timestamp()
        
        emoji_map = {
            'Read': '📖',
            'Edit': '✏️',
            'Write': '📝',
            'Bash': '🖥️',
            'Glob': '🔍',
            'Grep': '🔎',
            'TodoWrite': '📋'
        }
        
        emoji = emoji_map.get(tool_name, '🔧')
        print(f"\n[{timestamp}] {emoji} {tool_name}: {action_description}")
    
    def assistant_message(self, text: str) -> None:
        """Log assistant text output."""
        timestamp = self.get_timestamp()
        print(f"\n[{timestamp}] 💭 {text}")
    
    def iteration_header(self, iteration: int) -> None:
        """Log iteration header."""
        timestamp = self.get_timestamp()
        print(f"\n=== TDD DevOps Loop - Iteration {iteration} === [{timestamp}]")
    
    def session_info(self, session_data: Dict[str, Any]) -> None:
        """Log session initialization information."""
        print("=" * 60)
        print(f"🚀 Session started (ID: {session_data.get('session_id', 'unknown')[:8]}...)")
        print(f"📁 Working directory: {session_data.get('cwd', 'unknown')}")
        print(f"🤖 Model: {session_data.get('model', 'unknown')}")
        print(f"🔧 Tools available: {len(session_data.get('tools', []))}")
        print("=" * 60)