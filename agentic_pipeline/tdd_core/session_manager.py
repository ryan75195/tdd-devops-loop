"""Claude session management facade."""

import subprocess
import sys
from typing import Tuple, Optional, Dict, Any

from .config import Configuration, ExecutionContext
from .command_builder import ClaudeCommandBuilder
from .stream_processor import StreamProcessor
from .response_processor import ResponseProcessor
from ..handlers.tool_handlers import ToolHandlerRegistry
from ..events.event_handlers import EventHandlerFactory
from ..parsers.json_parsers import JsonParsingChain


class ClaudeSessionManager:
    """Facade that orchestrates all the focused components for Claude session management."""
    
    def __init__(self, config: Configuration, logger, usage_parser):
        self.config = config
        self.logger = logger
        self.usage_parser = usage_parser
        
        # Initialize all components
        self.context = ExecutionContext(logger, usage_parser, config)
        self.command_builder = ClaudeCommandBuilder(config)
        self.tool_registry = ToolHandlerRegistry()
        self.event_factory = EventHandlerFactory()
        self.stream_processor = StreamProcessor(self.context, self.tool_registry, self.event_factory)
        self.parsing_chain = JsonParsingChain()
        self.response_processor = ResponseProcessor(self.parsing_chain, logger)
    
    def run_single_iteration(self, ticket_number: str) -> Tuple[Optional[Dict], Optional[int], int]:
        """Run a single TDD iteration."""
        cmd = self.command_builder.build_initial_command(ticket_number)
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1
            )
            
            collected_text = ""
            usage_limit_reset_epoch = None
            
            for line in process.stdout:
                _, epoch, collected_text = self.stream_processor.process_line(line, collected_text)
                
                if epoch:
                    usage_limit_reset_epoch = max(usage_limit_reset_epoch or 0, epoch)
            
            process.wait()
            stderr_output = process.stderr.read()
            if stderr_output:
                print(f"STDERR: {stderr_output}", file=sys.stderr)
            
            # Get status via follow-up call
            final_result = self._run_followup_status_check(ticket_number)
            
            return final_result, usage_limit_reset_epoch, process.returncode
        
        except Exception as e:
            self.logger.error(f"Error running command: {e}")
            return None, None, 1
    
    def _run_followup_status_check(self, ticket_number: str) -> Optional[Dict[str, Any]]:
        """Run a follow-up call to get JSON status from the previous TDD work."""
        self.logger.info("🔄 Getting status update...")
        
        cmd = self.command_builder.build_followup_command(ticket_number)
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            stdout, stderr = process.communicate()
            
            if stderr:
                print(f"STDERR: {stderr}", file=sys.stderr)
            
            return self.response_processor.process_followup_response(stdout)
            
        except Exception as e:
            self.logger.error(f"Error in follow-up call: {e}")
            return None