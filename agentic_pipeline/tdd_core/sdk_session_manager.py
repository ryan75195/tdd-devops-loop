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
            async for message in query(
                prompt=initial_prompt, 
                options=options
            ):
                collected_messages.append(message)
                
                # Process each message for usage limits or other important info
                message_text = self._extract_message_text(message)
                # Note: message_text logging is handled in _extract_message_text
                
                # Check for usage limits in text messages
                if message_text:
                    epoch = self.usage_parser.parse_usage_limit_epoch(message_text)
                    if epoch:
                        usage_limit_reset_epoch = max(usage_limit_reset_epoch or 0, epoch)
            
            # No status check - just return success
            self.logger.info("✅ TDD iteration completed successfully")
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
                    user_message = lines[0][:200] if lines else "TDD iteration completed"
                    
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
                # Tool usage messages - show what tool is being used
                tool_name = getattr(message, 'tool_name', 'Unknown')
                self.logger.info(f"🔧 Using tool: {tool_name}")
                return ""
            elif message_type == "ToolResultMessage":
                # Tool result messages - show tool completion
                tool_name = getattr(message, 'tool_name', 'Unknown')
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
                    self.logger.info(f"💭 {content}")
                return content
            elif hasattr(message, 'text'):
                # Direct text message
                text = message.text
                if text.strip():
                    self.logger.info(f"💭 {text}")
                return text
            elif isinstance(message, str):
                # String message
                if message.strip():
                    self.logger.info(f"💭 {message}")
                return message
            else:
                # Unknown message type - log for debugging
                self.logger.debug(f"Unknown message type {message_type}: {str(message)[:100]}")
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
6. **Commit your changes** using git with a descriptive commit message

**CRITICAL RULES:**
- Write only ONE failing test per iteration, not a full test suite
- Choose the simplest/most fundamental test case first
- Implement only the minimal code needed to pass that specific test
- If the task is complex, focus on one small piece at a time
- ALWAYS commit your changes at the end with: `git add .` then `git commit -m "descriptive message"`

Start by exploring the codebase, then write your single failing test, implement the code, and commit."""
        
        return prompt
    
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