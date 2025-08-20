"""Claude SDK-based session management."""

import asyncio
import json
from typing import Tuple, Optional, Dict, Any

import anyio
from claude_code_sdk import query, ClaudeCodeOptions

from .config import Configuration, ExecutionContext
from .response_processor import ResponseProcessor
from ..parsers.json_parsers import JsonParsingChain


class ClaudeSDKSessionManager:
    """SDK-based session manager that replaces subprocess calls with direct SDK integration."""
    
    def __init__(self, config: Configuration, logger, usage_parser):
        self.config = config
        self.logger = logger
        self.usage_parser = usage_parser
        
        # Initialize components we still need
        self.context = ExecutionContext(logger, usage_parser, config)
        self.parsing_chain = JsonParsingChain()
        self.response_processor = ResponseProcessor(self.parsing_chain, logger)
    
    def run_single_iteration(self, ticket_number: str) -> Tuple[Optional[Dict], Optional[int], int]:
        """Run a single TDD iteration using the Claude Code SDK."""
        try:
            # Run the async iteration in a sync context
            return anyio.run(self._async_run_single_iteration, ticket_number)
        except Exception as e:
            self.logger.error(f"Error running SDK iteration: {e}")
            return None, None, 1
    
    async def _async_run_single_iteration(self, ticket_number: str) -> Tuple[Optional[Dict], Optional[int], int]:
        """Async implementation of single TDD iteration."""
        # Initial TDD work
        initial_prompt = f"/tdd-devops {ticket_number}"
        
        usage_limit_reset_epoch = None
        collected_messages = []
        
        try:
            # Configure SDK options for the initial work
            options = ClaudeCodeOptions(
                system_prompt="You are an expert software engineer performing Test-Driven Development. "
                           "Work iteratively on the given ticket, following TDD best practices.",
                max_turns=1,  # Single iteration
                # Enable all tools for full Claude Code functionality
                allowed_tools=None,  # Allow all tools
                permission_mode="bypassPermissions"  # Equivalent to --dangerously-skip-permissions
            )
            
            # Stream the initial TDD work
            async for message in query(prompt=initial_prompt, options=options):
                collected_messages.append(message)
                
                # Process each message for usage limits or other important info
                message_text = self._extract_message_text(message)
                if message_text:
                    self.logger.assistant_message(message_text)
                    
                    # Check for usage limits
                    epoch = self.usage_parser.parse_usage_limit_epoch(message_text)
                    if epoch:
                        usage_limit_reset_epoch = max(usage_limit_reset_epoch or 0, epoch)
            
            # Now get the status update
            final_result = await self._async_run_followup_status_check(ticket_number)
            
            return final_result, usage_limit_reset_epoch, 0  # Success return code
            
        except Exception as e:
            self.logger.error(f"Error in SDK TDD iteration: {e}")
            return None, usage_limit_reset_epoch, 1
    
    async def _async_run_followup_status_check(self, ticket_number: str) -> Optional[Dict[str, Any]]:
        """Run a follow-up call to get JSON status from the previous TDD work."""
        self.logger.info("🔄 Getting status update...")
        
        try:
            # Create status prompt with JSON schema
            json_instructions = (
                f'Provide a JSON status update in this exact format: '
                f'{json.dumps(self.config.response_schema)}. Include user_message with '
                f'current status and complete (boolean) indicating if the ticket is fully done.'
            )
            
            status_prompt = "Provide a JSON status update on the TDD work completed."
            
            # Configure SDK for JSON response
            options = ClaudeCodeOptions(
                system_prompt=json_instructions,
                max_turns=1,
                permission_mode="bypassPermissions"
            )
            
            response_text = ""
            async for message in query(prompt=status_prompt, options=options):
                message_text = self._extract_message_text(message)
                if message_text:
                    response_text += message_text
            
            # Process the response to extract JSON
            return self.response_processor.process_followup_response(response_text)
            
        except Exception as e:
            self.logger.error(f"Error in SDK follow-up call: {e}")
            return None
    
    def _extract_message_text(self, message) -> str:
        """Extract text content from SDK message object."""
        try:
            # Handle different message types from SDK
            if hasattr(message, 'content'):
                # Message with content blocks
                text_parts = []
                for block in message.content:
                    if hasattr(block, 'text'):
                        text_parts.append(block.text)
                return ''.join(text_parts)
            elif hasattr(message, 'text'):
                # Direct text message
                return message.text
            elif isinstance(message, str):
                # String message
                return message
            elif hasattr(message, 'data') and isinstance(message.data, dict):
                # Handle system messages - log but don't return as text
                self.logger.info(f"💭 {message.__class__.__name__}({message.data})")
                return ""
            elif hasattr(message, 'result'):
                # Handle result messages
                self.logger.info(f"💭 {message.__class__.__name__}(result='{message.result}')")
                return str(message.result)
            else:
                # Try to convert to string for debugging
                message_str = str(message)
                self.logger.debug(f"Unknown message type: {message_str}")
                return message_str
        except Exception as e:
            # Fallback: try to stringify the entire message
            self.logger.debug(f"Error extracting message text: {e}")
            return str(message)