"""Stream processing for Claude output."""

import json
from typing import Tuple, Optional, Dict, Any

from .config import ExecutionContext
from ..handlers.tool_handlers import ToolHandlerRegistry
from ..events.event_handlers import EventHandlerFactory


class StreamProcessor:
    """Handles processing of Claude stream output."""
    
    def __init__(self, context: ExecutionContext, tool_registry: ToolHandlerRegistry, 
                 event_factory: EventHandlerFactory):
        self.context = context
        self.tool_registry = tool_registry
        self.event_factory = event_factory
    
    def process_line(self, line: str, collected_text: str) -> Tuple[Optional[Dict], Optional[int], str]:
        """Process a single line from the Claude stream output."""
        line = line.strip()
        if not line:
            return None, None, collected_text
        
        collected_text += line + "\n"
        
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            print(line)
            return None, None, collected_text
        
        if not (parsed and isinstance(parsed, dict)):
            print(line)
            return None, None, collected_text
        
        # Check if this is our target response schema
        if 'user_message' in parsed and 'complete' in parsed:
            return parsed, None, collected_text
        
        usage_limit_epoch = self._handle_event(parsed)
        return None, usage_limit_epoch, collected_text
    
    def _handle_event(self, event: Dict[str, Any]) -> Optional[int]:
        """Handle an event using the appropriate handler."""
        event_type = event.get('type')
        handler = self.event_factory.get_handler(event_type)
        
        # Handle tool use within assistant events
        if event_type == 'assistant':
            self._handle_tool_use_in_event(event)
        
        return handler.handle(event, self.context)
    
    def _handle_tool_use_in_event(self, event: Dict[str, Any]) -> None:
        """Extract and handle tool use from assistant events."""
        message = event.get('message', {})
        content = message.get('content', [])
        
        for item in content:
            if item.get('type') == 'tool_use':
                tool_name = item.get('name', 'unknown')
                tool_input = item.get('input', {})
                self.tool_registry.handle_tool(tool_name, tool_input, self.context.logger)