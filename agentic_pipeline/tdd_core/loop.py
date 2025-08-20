"""Main TDD DevOps Loop orchestrator."""

import os
from typing import Optional, Dict, Any

from .config import Configuration
from .sdk_session_manager import ClaudeSDKSessionManager
from ..utils.logger import Logger
from ..utils.usage_parser import UsageLimitParser


class TDDDevOpsLoop:
    """Main orchestrator for the TDD DevOps Loop."""
    
    def __init__(self, config: Configuration = None):
        self.config = config or Configuration()
        self.logger = Logger()
        self.usage_parser = UsageLimitParser()
        self.session_manager = ClaudeSDKSessionManager(self.config, self.logger, self.usage_parser)
    
    def print_iteration_result(self, final_result: Optional[Dict[str, Any]]) -> bool:
        """Print the result of an iteration and return whether the ticket is complete."""
        print("\n" + "=" * 60)
        
        if final_result:
            self.logger.info(f"📊 Status: {final_result.get('user_message', 'No message')}")
            is_complete = final_result.get('complete', False)
            
            if is_complete:
                self.logger.success("Ticket marked as complete. Exiting loop.")
            else:
                self.logger.info("🔄 Continuing to next iteration...")
            
            print("=" * 60)
            return is_complete
        else:
            self.logger.warning("No final JSON response found. Continuing...")
            print("=" * 60)
            return False
    
    def run(self, project_path: str, ticket_number: str) -> None:
        """Run the TDD DevOps loop."""
        os.chdir(project_path)
        
        iteration = 1
        
        while iteration <= self.config.max_iterations:
            self.logger.iteration_header(iteration)
            
            final_result, usage_limit_epoch, return_code = self.session_manager.run_single_iteration(ticket_number)
            
            is_complete = self.print_iteration_result(final_result)
            
            if return_code != 0:
                self.logger.warning(f"Process exited with code {return_code}")
            
            if usage_limit_epoch:
                self.usage_parser.sleep_until_reset(usage_limit_epoch, self.logger)
            
            if is_complete:
                break
            
            iteration += 1
        
        if iteration > self.config.max_iterations:
            self.logger.warning(f"🛑 Reached maximum iterations ({self.config.max_iterations}). Stopping.")