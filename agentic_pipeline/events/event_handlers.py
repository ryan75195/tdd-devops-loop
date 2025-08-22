"""Event handling components implementing Observer pattern."""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from ..core.interfaces import EventHandler, EventObserver
from ..tdd_core.config import ExecutionContext


class EventBus:
    """Event bus implementing Observer pattern."""
    
    def __init__(self):
        self.observers: List[EventObserver] = []
    
    def subscribe(self, observer: EventObserver) -> None:
        """Subscribe an observer to events."""
        self.observers.append(observer)
    
    def publish(self, event_type: str, data: Dict[str, Any]) -> None:
        """Publish an event to all observers."""
        for observer in self.observers:
            observer.on_event(event_type, data)


class LoggingObserver:
    """Observer that handles logging for various events."""
    
    def __init__(self, logger):
        self.logger = logger
    
    def on_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Handle events by logging appropriate information."""
        if event_type == 'session_init':
            self.logger.session_info(data)
        elif event_type == 'assistant_text':
            self.logger.assistant_message(data.get('text', ''))
        elif event_type == 'tool_result':
            result_content = data.get('content', '')
            if isinstance(result_content, str) and result_content.strip():
                self.logger.success(f"{result_content}")
                print("-" * 40)
            else:
                self.logger.success("Completed")
                print("-" * 40)


class SystemEventHandler(EventHandler):
    """Handles system events."""
    
    def handle(self, event: Dict[str, Any], context: ExecutionContext) -> Optional[int]:
        if event.get('subtype') == 'init':
            context.logger.session_info(event)
        return None


class AssistantEventHandler(EventHandler):
    """Handles assistant events."""
    
    def handle(self, event: Dict[str, Any], context: ExecutionContext) -> Optional[int]:
        message = event.get('message', {})
        content = message.get('content', [])
        usage_limit_epoch = None
        
        for item in content:
            if item.get('type') == 'text':
                text = item.get('text', '').strip()
                if text:
                    context.logger.assistant_message(text)
                    epoch = context.usage_parser.parse_usage_limit_epoch(text)
                    if epoch:
                        usage_limit_epoch = epoch
            elif item.get('type') == 'tool_use':
                # Tool handling is done separately by ToolHandlerRegistry
                # tool_name and tool_input would be extracted here if needed
                pass
                
        return usage_limit_epoch


class UserEventHandler(EventHandler):
    """Handles user events."""
    
    def handle(self, event: Dict[str, Any], context: ExecutionContext) -> Optional[int]:
        message = event.get('message', {})
        content = message.get('content', [])
        
        for item in content:
            if item.get('type') == 'tool_result':
                result_content = item.get('content', '')
                if isinstance(result_content, str) and result_content.strip():
                    context.logger.success(f"{result_content}")
                    print("-" * 40)
                else:
                    context.logger.success("Completed")
                    print("-" * 40)
        return None


class ResultEventHandler(EventHandler):
    """Handles result events."""
    
    def handle(self, event: Dict[str, Any], context: ExecutionContext) -> Optional[int]:
        result_str = event.get('result', '') or ''
        epoch = context.usage_parser.parse_usage_limit_epoch(result_str)
        if epoch:
            reset_time = datetime.fromtimestamp(epoch, tz=timezone.utc).astimezone()
            reset_str = reset_time.strftime("%Y-%m-%d %H:%M:%S %Z")
            context.logger.error(f"⛔️ Claude usage limit detected! Reset time: {reset_str} (epoch: {epoch})")
            context.logger.info(f"💬 Original message: {result_str}")
            return epoch
        else:
            context.logger.info(f"🔍 Result event: {event}")
            return None


class DefaultEventHandler(EventHandler):
    """Default handler for unknown events."""
    
    def handle(self, event: Dict[str, Any], context: ExecutionContext) -> Optional[int]:
        event_type = event.get('type', 'unknown')
        context.logger.info(f"🔍 Unknown event: {event_type} - {event}")
        return None


class EventHandlerFactory:
    """Factory for creating event handlers."""
    
    def __init__(self):
        self.handlers = {
            'system': SystemEventHandler(),
            'assistant': AssistantEventHandler(),
            'user': UserEventHandler(),
            'result': ResultEventHandler()
        }
        self.default_handler = DefaultEventHandler()
    
    def get_handler(self, event_type: str) -> EventHandler:
        """Get the appropriate handler for an event type."""
        return self.handlers.get(event_type, self.default_handler)