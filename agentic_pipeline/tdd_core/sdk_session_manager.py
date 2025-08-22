"""Claude Code SDK session management - pure SDK implementation."""

import json
from typing import Tuple, Optional, Dict, Any

import anyio
from claude_code_sdk import query, ClaudeCodeOptions

from .config import Configuration, ExecutionContext
from .response_processor import ResponseProcessor
from ..parsers.json_parsers import JsonParsingChain


class ClaudeSDKSessionManager:
    """Pure Claude Code SDK session manager - no fallbacks, SDK only."""
    
    def __init__(self, config: Configuration, logger, usage_parser):
        self.config = config
        self.logger = logger
        self.usage_parser = usage_parser
        
        # Initialize components we still need
        self.context = ExecutionContext(logger, usage_parser, config)
        self.parsing_chain = JsonParsingChain()
        self.response_processor = ResponseProcessor(self.parsing_chain, logger)
    
    def run_single_iteration(self, task_details: Dict) -> Tuple[Optional[int], int]:
        """Run a single TDD iteration using the Claude Code SDK."""
        try:
            # Run the async iteration in a sync context
            return anyio.run(self._async_run_single_iteration, task_details)
        except Exception as e:
            self.logger.error(f"Error running SDK iteration: {e}")
            return None, 1
    
    async def _async_run_single_iteration(self, task_details: Dict) -> Tuple[Optional[int], int]:
        """Async implementation of single TDD iteration."""
        # Build structured TDD prompt from task details
        initial_prompt = self._build_tdd_prompt(task_details)
        
        usage_limit_reset_epoch = None
        collected_messages = []
        
        try:
            # Configure SDK options for the initial work
            options = ClaudeCodeOptions(
                system_prompt="You are an expert software engineer performing Test-Driven Development. "
                           "You must actively explore the codebase, write tests, and implement code. "
                           "Use all available tools to complete the task. Do not just analyze - take action!",
                # Enable all tools for full Claude Code functionality
                allowed_tools=None,  # Allow all tools
                permission_mode="bypassPermissions"  # Equivalent to --dangerously-skip-permissions
            )
            
            # Stream the initial TDD work
            self.logger.info("🚀 Starting Claude Code SDK session - tool usage will be embedded in responses")
            message_count = 0
            async for message in query(
                prompt=initial_prompt, 
                options=options
            ):
                message_count += 1
                collected_messages.append(message)
                
                # Process each message for usage limits or other important info
                message_text = self._extract_message_text(message)
                # Note: message_text logging is handled in _extract_message_text
                
                # Check for usage limits in text messages
                if message_text:
                    epoch = self.usage_parser.parse_usage_limit_epoch(message_text)
                    if epoch:
                        usage_limit_reset_epoch = max(usage_limit_reset_epoch or 0, epoch)
            
            # Log completion with message count
            self.logger.info(f"✅ TDD iteration completed successfully ({message_count} messages received)")
            self.logger.info("📝 Note: Tool usage details are embedded within Claude's responses above")
            return usage_limit_reset_epoch, 0  # Success return code
            
        except Exception as e:
            self.logger.error(f"Error in SDK TDD iteration: {e}")
            return usage_limit_reset_epoch, 1
    
    async def _async_run_followup_status_check(self, task_details: Dict) -> Optional[Dict[str, Any]]:
        """Run a follow-up call to get JSON status from the previous TDD work."""
        self.logger.info("🔄 Getting status update...")
        
        try:
            # Create status prompt with JSON schema
            json_schema = json.dumps(self.config.response_schema)
            json_instructions = (
                f'You must respond with ONLY valid JSON. No other text allowed.\n'
                f'Required format: {{"user_message": "description", "complete": boolean}}\n\n'
                f'Example: {{"user_message": "Implemented getCachedDocumentById method with tests passing", "complete": false}}\n'
                f'Example: {{"user_message": "All acceptance criteria met - task fully implemented", "complete": true}}\n\n'
                f'Rules:\n'
                f'- Your entire response must be valid JSON starting with {{ and ending with }}\n'
                f'- user_message: briefly describe what you accomplished in this TDD iteration\n'
                f'- complete: true only if ALL BDD scenarios for this task are fully implemented and tested\n'
                f'- complete: false if more TDD iterations are needed for this task'
            )
            
            status_prompt = f"Provide JSON status for the TDD work you just completed on Task {task_details.get('id')}:"
            
            # Configure SDK for JSON response
            options = ClaudeCodeOptions(
                system_prompt=json_instructions,
                permission_mode="bypassPermissions",
                output_format="json"  # Try to force JSON mode
            )
            
            response_text = ""
            async for message in query(
                prompt=status_prompt, 
                options=options
            ):
                message_text = self._extract_message_text(message)
                if message_text:
                    response_text += message_text
            
            # Process the response to extract JSON
            # If using output_format="json", the response might be wrapped in metadata
            try:
                # Try parsing as wrapped JSON first
                wrapped_response = json.loads(response_text)
                if isinstance(wrapped_response, dict) and 'result' in wrapped_response:
                    # Extract the inner result and parse it as JSON
                    inner_result = wrapped_response['result']
                    if isinstance(inner_result, str):
                        result = json.loads(inner_result)
                    else:
                        result = inner_result
                else:
                    # Fallback to regular parsing
                    result = self.response_processor.process_followup_response(response_text)
            except json.JSONDecodeError:
                # Fallback to regular parsing
                result = self.response_processor.process_followup_response(response_text)
            
            # If JSON parsing failed, create a fallback response
            if not result:
                self.logger.warning("JSON parsing failed, creating fallback response")
                
                # Handle the case where Claude returns "None" or empty response
                if not response_text.strip() or response_text.strip().lower() == "none":
                    result = {
                        "user_message": "TDD iteration completed - continuing with next iteration",
                        "complete": False  # Always continue if we got "None"
                    }
                    self.logger.info("Empty/None response - assuming iteration incomplete")
                else:
                    # Look for keywords in the response to determine completion status
                    response_lower = response_text.lower()
                    is_complete = any(keyword in response_lower for keyword in [
                        'complete', 'finished', 'done', 'implemented', 'all tests pass',
                        'task is complete', 'fully implemented'
                    ])
                    
                    # Extract a meaningful message from the response
                    lines = response_text.strip().split('\n')
                    user_message = lines[0] if lines else "TDD iteration completed"
                    
                    result = {
                        "user_message": user_message,
                        "complete": is_complete
                    }
                    self.logger.info(f"Fallback response created: complete={is_complete}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in SDK follow-up call: {e}")
            return None
    
    def _extract_message_text(self, message) -> str:
        """Extract text content from SDK message object."""
        try:
            message_type = type(message).__name__
            
            # Debug: log message types (comment out for less verbose logging)
            # attrs = [attr for attr in dir(message) if not attr.startswith('_')]
            # self.logger.debug(f"🔍 SDK Message: {message_type} (attrs: {attrs[:5]})")
            
            # Handle different message types based on SDK documentation
            if message_type == "ResultMessage":
                # Final result from Claude
                result_text = str(getattr(message, 'result', ''))
                self.logger.info(f"💭 {message_type}(result='{result_text}')")
                return result_text
            elif message_type == "SystemMessage":
                # System initialization/status messages - log but don't return as content
                data = getattr(message, 'data', {})
                self.logger.info(f"💭 {message_type}({data})")
                return ""
            elif message_type == "ToolUseMessage":
                # Tool usage messages - show what tool is being used with parameters
                tool_name = getattr(message, 'tool_name', 'Unknown')
                tool_input = getattr(message, 'tool_input', {})
                
                # Log tool usage with key parameters (truncate only very long values)
                if tool_input:
                    # Show key parameters for common tools
                    param_preview = self._format_tool_params(tool_name, tool_input)
                    self.logger.info(f"🔧 Using tool: {tool_name}({param_preview})")
                else:
                    self.logger.info(f"🔧 Using tool: {tool_name}")
                return ""
            elif message_type == "ToolResultMessage":
                # Tool result messages - show tool completion with result summary
                tool_name = getattr(message, 'tool_name', 'Unknown')
                tool_result = getattr(message, 'tool_result', None)
                
                # Show result summary for certain tools
                result_summary = self._format_tool_result(tool_name, tool_result)
                if result_summary:
                    self.logger.info(f"✅ Tool completed: {tool_name} → {result_summary}")
                else:
                    self.logger.info(f"✅ Tool completed: {tool_name}")
                return ""
            elif hasattr(message, 'content'):
                # Message with content blocks (typical assistant response)
                text_parts = []
                for block in message.content:
                    if hasattr(block, 'text'):
                        text_parts.append(block.text)
                content = ''.join(text_parts)
                if content.strip():
                    # Detect tool usage patterns in Claude's responses
                    self._detect_tool_usage_patterns(content)
                    self.logger.info(f"💭 {content}")
                return content
            elif hasattr(message, 'text'):
                # Direct text message
                text = message.text
                if text.strip():
                    # Detect tool usage patterns in text messages too
                    self._detect_tool_usage_patterns(text)
                    self.logger.info(f"💭 {text}")
                return text
            elif isinstance(message, str):
                # String message
                if message.strip():
                    # Detect tool usage patterns in string messages too
                    self._detect_tool_usage_patterns(message)
                    self.logger.info(f"💭 {message}")
                return message
            else:
                # Unknown message type - log for debugging
                self.logger.debug(f"Unknown message type {message_type}: {str(message)}")
                return ""
        except Exception as e:
            # Fallback: try to stringify the entire message
            self.logger.debug(f"Error extracting message text: {e}")
            return str(message)
    
    def _build_tdd_prompt(self, task_details: Dict) -> str:
        """Build a structured TDD prompt from task details."""
        task_id = task_details.get('id', 'Unknown')
        title = task_details.get('title', 'Unknown Task')
        description = task_details.get('description', '')
        acceptance_criteria = task_details.get('acceptance_criteria', '')
        
        # Clean up HTML from description and acceptance criteria
        description = self._clean_html(description)
        acceptance_criteria = self._clean_html(acceptance_criteria)
        
        prompt = f"""You are implementing Task {task_id}: {title}

**DESCRIPTION:**
{description}

**ACCEPTANCE CRITERIA/BDD SCENARIOS:**
{acceptance_criteria}

**TDD ITERATION OBJECTIVE:**
Follow strict TDD methodology for this single iteration:

1. **Explore** the codebase to understand existing structure (if first time working on this task)
2. **Write ONE failing test** that captures a specific aspect of the BDD scenarios above
3. **Run the test** to confirm it fails (Red phase)
4. **Write minimal code** to make ONLY that test pass (Green phase) 
5. **Refactor** if needed while keeping the test green (Refactor phase)

**CRITICAL RULES FOR REAL TESTING:**
- Write only ONE failing test per iteration, not a full test suite
- Choose the simplest/most fundamental test case first
- **ALWAYS TEST REAL IMPLEMENTATION**: Import and test the actual service/component/class - NEVER mock the primary functionality you're implementing
- Only mock external dependencies (APIs, databases, file system) - NOT the code you're testing
- Tests must call the real methods on the real classes to verify actual behavior
- If testing a service, import the service class and test its methods directly
- If testing a component, render the real component and test its behavior
- Implement only the minimal code needed to pass that specific test
- If the task is complex, focus on one small piece at a time
- DO NOT commit changes - the reflection system will handle commits after quality review

**TESTING EXAMPLES:**
❌ WRONG: `const mockService = {{ getCachedDocumentById: jest.fn() }}`
✅ CORRECT: `import {{ LibraryCacheService }} from './LibraryCacheService'; const service = new LibraryCacheService();`

❌ WRONG: Re-implementing logic in test to make it pass
✅ CORRECT: Testing the real implementation and letting failures guide development

Start by exploring the codebase, then write your single failing test that tests REAL implementation, and implement the code. Do not commit - the reflection system will review and commit approved changes."""
        
        return prompt
    
    def _detect_tool_usage_patterns(self, text: str) -> None:
        """Detect and log tool usage patterns in Claude's responses."""
        import re
        lower_text = text.lower()
        
        # Common tool usage patterns - using regex for more flexible matching
        patterns = [
            (r"let me read", "🔧 Tool Pattern: Reading file"),
            (r"let me check", "🔧 Tool Pattern: Checking/inspecting"),
            (r"let me examine", "🔧 Tool Pattern: Examining file"), 
            (r"let me look at", "🔧 Tool Pattern: Looking at file"),
            (r"let me run", "🔧 Tool Pattern: Running command"),
            (r"let me execute", "🔧 Tool Pattern: Executing command"),
            (r"let me create", "🔧 Tool Pattern: Creating file"),
            (r"let me write", "🔧 Tool Pattern: Writing file"),
            (r"let me edit", "🔧 Tool Pattern: Editing file"),
            (r"let me search", "🔧 Tool Pattern: Searching"),
            (r"let me grep", "🔧 Tool Pattern: Grepping"),
            (r"let me find", "🔧 Tool Pattern: Finding"),
            (r"now let me", "🔧 Tool Pattern: Next action"),
            (r"i'll use", "🔧 Tool Pattern: Using tool"),
            (r"i will use", "🔧 Tool Pattern: Using tool"),
            (r"using the bash", "🔧 Tool Pattern: Bash command"),
            (r"using the read", "🔧 Tool Pattern: Reading"),
            (r"using the edit", "🔧 Tool Pattern: Editing"),
            (r"using the write", "🔧 Tool Pattern: Writing"),
            (r"test.*fail", "🧪 Test Pattern: Failure detected"),
            (r"test.*pass", "🧪 Test Pattern: Success detected"),
            (r"run.*test", "🧪 Test Pattern: Running tests"),
            (r"npm run", "🔧 Tool Pattern: NPM command"),
            (r"git add", "🔧 Tool Pattern: Git add"),
            (r"git commit", "🔧 Tool Pattern: Git commit")
        ]
        
        for pattern, log_message in patterns:
            if re.search(pattern, lower_text):
                self.logger.info(log_message)
                break  # Only log the first match to avoid spam
    
    def _format_tool_params(self, tool_name: str, tool_input: dict) -> str:
        """Format tool parameters for logging display."""
        try:
            # Show key parameters for common tools
            if tool_name == "Bash":
                command = tool_input.get('command', '')
                if len(command) > 100:
                    return f"command='{command[:100]}...'"
                return f"command='{command}'"
            elif tool_name == "Read":
                file_path = tool_input.get('file_path', '')
                offset = tool_input.get('offset')
                limit = tool_input.get('limit')
                if offset is not None and limit is not None:
                    return f"file='{file_path}', lines={offset}-{offset+limit}"
                return f"file='{file_path}'"
            elif tool_name == "Write":
                file_path = tool_input.get('file_path', '')
                content_len = len(str(tool_input.get('content', '')))
                return f"file='{file_path}', {content_len} chars"
            elif tool_name == "Edit":
                file_path = tool_input.get('file_path', '')
                old_len = len(str(tool_input.get('old_string', '')))
                new_len = len(str(tool_input.get('new_string', '')))
                return f"file='{file_path}', {old_len}→{new_len} chars"
            elif tool_name == "Grep":
                pattern = tool_input.get('pattern', '')
                path = tool_input.get('path', '.')
                output_mode = tool_input.get('output_mode', 'files_with_matches')
                return f"pattern='{pattern}', path='{path}', mode={output_mode}"
            elif tool_name == "Glob":
                pattern = tool_input.get('pattern', '')
                path = tool_input.get('path', '.')
                return f"pattern='{pattern}', path='{path}'"
            elif tool_name == "LS":
                path = tool_input.get('path', '.')
                return f"path='{path}'"
            else:
                # For other tools, show first few key-value pairs
                items = []
                for key, value in list(tool_input.items())[:3]:
                    if isinstance(value, str) and len(value) > 50:
                        items.append(f"{key}='{value[:50]}...'")
                    else:
                        items.append(f"{key}={repr(value)}")
                return ", ".join(items)
        except Exception:
            return "..."
    
    def _format_tool_result(self, tool_name: str, tool_result) -> str:
        """Format tool results for logging display."""
        try:
            if not tool_result:
                return ""
            
            if tool_name == "Bash":
                # Show exit code and output summary
                if hasattr(tool_result, 'returncode'):
                    code = tool_result.returncode
                    output_len = len(str(getattr(tool_result, 'stdout', '')))
                    return f"exit_code={code}, {output_len} chars output"
                elif isinstance(tool_result, dict):
                    code = tool_result.get('returncode', 'unknown')
                    output_len = len(str(tool_result.get('stdout', '')))
                    return f"exit_code={code}, {output_len} chars output"
            elif tool_name in ["Read", "Write", "Edit"]:
                # Show success/failure for file operations
                if isinstance(tool_result, str):
                    return f"{len(tool_result)} chars"
                return "success"
            elif tool_name in ["Grep", "Glob"]:
                # Show number of matches
                if isinstance(tool_result, list):
                    return f"{len(tool_result)} matches"
                elif isinstance(tool_result, str):
                    lines = tool_result.count('\n') + 1
                    return f"{lines} lines"
            elif tool_name == "LS":
                # Show number of items listed
                if isinstance(tool_result, list):
                    return f"{len(tool_result)} items"
                elif isinstance(tool_result, str):
                    lines = tool_result.count('\n')
                    return f"{lines} items"
            
            # Generic result summary
            if isinstance(tool_result, str):
                return f"{len(tool_result)} chars"
            elif isinstance(tool_result, list):
                return f"{len(tool_result)} items"
            elif isinstance(tool_result, dict):
                return f"{len(tool_result)} fields"
            else:
                return "success"
        except Exception:
            return "completed"
    
    def _clean_html(self, text: str) -> str:
        """Remove HTML tags and decode entities from text."""
        if not text:
            return ""
        
        import re
        import html
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Decode HTML entities
        text = html.unescape(text)
        # Clean up extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text