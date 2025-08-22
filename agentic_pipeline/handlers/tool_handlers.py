"""Tool handlers implementing Strategy pattern."""

from typing import Dict, Any

from ..core.interfaces import ToolHandler


class ReadToolHandler(ToolHandler):
    """Handles Read tool logging."""
    
    def handle(self, tool_input: Dict[str, Any], logger) -> None:
        file_path = tool_input.get('file_path', '')
        offset = tool_input.get('offset')
        limit = tool_input.get('limit')
        if offset is not None and limit is not None:
            logger.tool_action('Read', f"Reading {file_path} (lines {offset}-{offset+limit})")
        else:
            logger.tool_action('Read', f"Reading {file_path}")


class EditToolHandler(ToolHandler):
    """Handles Edit tool logging."""
    
    def handle(self, tool_input: Dict[str, Any], logger) -> None:
        file_path = tool_input.get('file_path', '')
        old_len = len(str(tool_input.get('old_string', '')))
        new_len = len(str(tool_input.get('new_string', '')))
        logger.tool_action('Edit', f"Editing {file_path} ({old_len}→{new_len} chars)")


class WriteToolHandler(ToolHandler):
    """Handles Write tool logging."""
    
    def handle(self, tool_input: Dict[str, Any], logger) -> None:
        file_path = tool_input.get('file_path', '')
        content_len = len(str(tool_input.get('content', '')))
        logger.tool_action('Write', f"Writing {file_path} ({content_len} chars)")


class BashToolHandler(ToolHandler):
    """Handles Bash tool logging."""
    
    def handle(self, tool_input: Dict[str, Any], logger) -> None:
        command = tool_input.get('command', '')
        logger.tool_action('Bash', f"Running: {command}")


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
        output_mode = tool_input.get('output_mode', 'files_with_matches')
        logger.tool_action('Grep', f"Searching '{pattern}' in {path} (mode: {output_mode})")


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


class MultiEditToolHandler(ToolHandler):
    """Handles MultiEdit tool logging."""
    
    def handle(self, tool_input: Dict[str, Any], logger) -> None:
        file_path = tool_input.get('file_path', '')
        edits = tool_input.get('edits', [])
        logger.tool_action('MultiEdit', f"Applying {len(edits)} edits to {file_path}")


class LSToolHandler(ToolHandler):
    """Handles LS tool logging."""
    
    def handle(self, tool_input: Dict[str, Any], logger) -> None:
        path = tool_input.get('path', '.')
        ignore = tool_input.get('ignore', [])
        if ignore:
            logger.tool_action('LS', f"Listing {path} (ignoring {len(ignore)} patterns)")
        else:
            logger.tool_action('LS', f"Listing {path}")


class WebFetchToolHandler(ToolHandler):
    """Handles WebFetch tool logging."""
    
    def handle(self, tool_input: Dict[str, Any], logger) -> None:
        url = tool_input.get('url', '')
        prompt = tool_input.get('prompt', '')
        logger.tool_action('WebFetch', f"Fetching {url} with prompt: {prompt[:50]}...")


class TaskToolHandler(ToolHandler):
    """Handles Task tool logging."""
    
    def handle(self, tool_input: Dict[str, Any], logger) -> None:
        description = tool_input.get('description', '')
        subagent_type = tool_input.get('subagent_type', '')
        logger.tool_action('Task', f"Starting {subagent_type} agent: {description}")


class DefaultToolHandler(ToolHandler):
    """Default handler for unknown tools."""
    
    def handle(self, tool_input: Dict[str, Any], logger) -> None:
        # Show tool name and basic info for unknown tools
        tool_keys = list(tool_input.keys())[:3] if tool_input else []
        if tool_keys:
            logger.tool_action('Unknown', f"Tool with params: {', '.join(tool_keys)}")
        else:
            logger.tool_action('Unknown', "Tool with no parameters")


class ToolHandlerRegistry:
    """Registry for tool handlers using Strategy pattern."""
    
    def __init__(self):
        self.handlers = {
            'Read': ReadToolHandler(),
            'Edit': EditToolHandler(),
            'Write': WriteToolHandler(),
            'MultiEdit': MultiEditToolHandler(),
            'Bash': BashToolHandler(),
            'Glob': GlobToolHandler(),
            'Grep': GrepToolHandler(),
            'LS': LSToolHandler(),
            'WebFetch': WebFetchToolHandler(),
            'Task': TaskToolHandler(),
            'TodoWrite': TodoWriteToolHandler()
        }
        self.default_handler = DefaultToolHandler()
    
    def handle_tool(self, tool_name: str, tool_input: Dict[str, Any], logger) -> None:
        """Handle a tool invocation using the appropriate strategy."""
        handler = self.handlers.get(tool_name, self.default_handler)
        if handler == self.default_handler:
            # For unknown tools, pass the tool name to the handler
            self._handle_unknown_tool(tool_name, tool_input, logger)
        else:
            handler.handle(tool_input, logger)
    
    def _handle_unknown_tool(self, tool_name: str, tool_input: Dict[str, Any], logger) -> None:
        """Handle unknown tool with proper tool name logging."""
        tool_keys = list(tool_input.keys())[:3] if tool_input else []
        if tool_keys:
            logger.tool_action(tool_name, f"Tool with params: {', '.join(tool_keys)}")
        else:
            logger.tool_action(tool_name, "Tool with no parameters")