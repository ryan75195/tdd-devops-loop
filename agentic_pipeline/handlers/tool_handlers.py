"""Tool handlers implementing Strategy pattern."""

from typing import Dict, Any

from ..core.interfaces import ToolHandler


class ReadToolHandler(ToolHandler):
    """Handles Read tool logging."""
    
    def handle(self, tool_input: Dict[str, Any], logger) -> None:
        logger.tool_action('Read', tool_input.get('file_path', ''))


class EditToolHandler(ToolHandler):
    """Handles Edit tool logging."""
    
    def handle(self, tool_input: Dict[str, Any], logger) -> None:
        logger.tool_action('Edit', tool_input.get('file_path', ''))


class WriteToolHandler(ToolHandler):
    """Handles Write tool logging."""
    
    def handle(self, tool_input: Dict[str, Any], logger) -> None:
        logger.tool_action('Write', tool_input.get('file_path', ''))


class BashToolHandler(ToolHandler):
    """Handles Bash tool logging."""
    
    def handle(self, tool_input: Dict[str, Any], logger) -> None:
        cmd_preview = tool_input.get('command', '')[:80]
        logger.tool_action('Bash', f"Running: {cmd_preview}")


class GlobToolHandler(ToolHandler):
    """Handles Glob tool logging."""
    
    def handle(self, tool_input: Dict[str, Any], logger) -> None:
        pattern = tool_input.get('pattern', '')
        path = tool_input.get('path', '.')
        logger.tool_action('Glob', f"Searching: {pattern} in {path}")


class GrepToolHandler(ToolHandler):
    """Handles Grep tool logging."""
    
    def handle(self, tool_input: Dict[str, Any], logger) -> None:
        pattern = tool_input.get('pattern', '')
        path = tool_input.get('path', '.')
        logger.tool_action('Grep', f"Grepping: '{pattern}' in {path}")


class TodoWriteToolHandler(ToolHandler):
    """Handles TodoWrite tool logging."""
    
    def handle(self, tool_input: Dict[str, Any], logger) -> None:
        todos = tool_input.get('todos', [])
        logger.tool_action('TodoWrite', f"Todo List ({len(todos)} items)")
        for todo in todos:
            status_emoji = {
                'pending': '⏳', 
                'in_progress': '🔄', 
                'completed': '✅'
            }.get(todo.get('status', 'pending'), '❓')
            content = todo.get('content', 'No description')[:60]
            if len(todo.get('content', '')) > 60:
                content += '...'
            print(f"     {status_emoji} {content}")


class DefaultToolHandler(ToolHandler):
    """Default handler for unknown tools."""
    
    def handle(self, tool_input: Dict[str, Any], logger) -> None:
        # tool_input is intentionally unused for unknown tools
        logger.tool_action('Unknown', "")


class ToolHandlerRegistry:
    """Registry for tool handlers using Strategy pattern."""
    
    def __init__(self):
        self.handlers = {
            'Read': ReadToolHandler(),
            'Edit': EditToolHandler(),
            'Write': WriteToolHandler(),
            'Bash': BashToolHandler(),
            'Glob': GlobToolHandler(),
            'Grep': GrepToolHandler(),
            'TodoWrite': TodoWriteToolHandler()
        }
        self.default_handler = DefaultToolHandler()
    
    def handle_tool(self, tool_name: str, tool_input: Dict[str, Any], logger) -> None:
        """Handle a tool invocation using the appropriate strategy."""
        handler = self.handlers.get(tool_name, self.default_handler)
        handler.handle(tool_input, logger)