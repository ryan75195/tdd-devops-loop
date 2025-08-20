"""TDD Agent - Refactored from the original TDD DevOps Loop."""

import os
from typing import Any, Dict

from ..core.agent import Agent, AgentResult, AgentStatus
from ..core.state import AgentState
from ..core.config import AgentConfig, TerminalCondition, TerminalConditionType

# Import the TDD infrastructure
from ..utils.logger import Logger
from ..utils.usage_parser import UsageLimitParser
from ..tdd_core.sdk_session_manager import ClaudeSDKSessionManager
from ..tdd_core.config import Configuration, ExecutionContext


class TDDAgent(Agent):
    """
    Test-Driven Development Agent.
    
    Performs iterative TDD workflows using Claude Code integration.
    Refactored from the original monolithic TDD DevOps Loop.
    """
    
    # Agent metadata for auto-discovery
    AGENT_TYPE = "tdd"
    DESCRIPTION = "Performs iterative Test-Driven Development workflows"
    VERSION = "2.0.0"
    AUTHOR = "TDD DevOps Loop Refactored"
    TAGS = ["development", "testing", "tdd", "automation"]
    CONFIG_SCHEMA = {
        "project_path": {
            "type": "string",
            "required": True,
            "description": "Path to the project directory"
        },
        "ticket_number": {
            "type": "string",
            "required": True,
            "description": "Ticket or issue identifier for the TDD work"
        }
    }
    
    def __init__(self, config: AgentConfig):
        """Initialize the TDD agent."""
        super().__init__(config)
        
        # TDD-specific components
        self.logger = None
        self.usage_parser = None
        self.session_manager = None
        self.tdd_config = None
        
        # State tracking
        self.project_path = None
        self.ticket_number = None
    
    def initialize(self, context: Dict[str, Any]) -> None:
        """Initialize the TDD agent with project context."""
        self.log("info", "Initializing TDD Agent")
        
        # Extract configuration
        self.project_path = self.config.get_parameter("project_path")
        self.ticket_number = self.config.get_parameter("ticket_number")
        
        if not self.project_path or not self.ticket_number:
            raise ValueError("TDD Agent requires 'project_path' and 'ticket_number' parameters")
        
        # Setup TDD infrastructure
        self.logger = Logger()
        self.usage_parser = UsageLimitParser()
        
        # Create TDD configuration
        self.tdd_config = Configuration()
        self.tdd_config.max_iterations = self.config.max_iterations
        
        # Initialize Claude Code SDK session manager
        self.session_manager = ClaudeSDKSessionManager(
            self.tdd_config, 
            self.logger, 
            self.usage_parser
        )
        
        # Change to project directory
        if os.path.exists(self.project_path):
            os.chdir(self.project_path)
            self.log("info", f"Changed to project directory: {self.project_path}")
        else:
            raise ValueError(f"Project path does not exist: {self.project_path}")
        
        self.status = AgentStatus.RUNNING
        self.log("info", "TDD Agent initialization completed")
    
    def execute_iteration(self, state: AgentState) -> AgentResult:
        """Execute one TDD iteration."""
        iteration_num = state.iteration + 1
        self.log("info", f"Executing TDD iteration {iteration_num}")
        
        try:
            # Log iteration header (similar to original)
            self.logger.iteration_header(iteration_num)
            
            # Run TDD iteration using session manager
            final_result, usage_limit_epoch, return_code = self.session_manager.run_single_iteration(
                self.ticket_number
            )
            
            # Handle usage limits
            if usage_limit_epoch:
                self.log("warning", "Claude usage limit detected")
                self.usage_parser.sleep_until_reset(usage_limit_epoch, self.logger)
            
            # Process return code
            if return_code != 0:
                self.log("warning", f"TDD iteration exited with code {return_code}")
            
            # Determine if work is complete
            is_complete = False
            status_message = "TDD iteration completed"
            
            if final_result:
                status_message = final_result.get('user_message', 'TDD iteration completed')
                is_complete = final_result.get('complete', False)
                
                if is_complete:
                    self.log("info", "TDD work marked as complete")
                    self.status = AgentStatus.COMPLETED
                else:
                    self.log("info", "TDD work continuing to next iteration")
            else:
                self.log("warning", "No status response from TDD iteration")
            
            # Update state with iteration results
            iteration_data = {
                "iteration_result": final_result,
                "return_code": return_code,
                "usage_limit_epoch": usage_limit_epoch,
                "timestamp": self.logger.get_timestamp()
            }
            
            return AgentResult(
                status=self.status,
                message=status_message,
                data=iteration_data,
                terminal=is_complete
            )
        
        except Exception as e:
            self.log("error", f"TDD iteration failed: {e}")
            return AgentResult(
                status=AgentStatus.FAILED,
                message=f"TDD iteration failed: {e}",
                data={},
                terminal=True,
                error=str(e)
            )
    
    def check_terminal_condition(self, state: AgentState) -> bool:
        """Check if TDD work should terminate."""
        # Check if the TDD work was marked as complete
        latest_result = state.get("iteration_result")
        if latest_result and latest_result.get('complete', False):
            return True
        
        # Check standard terminal conditions
        return False
    
    def finalize(self, state: AgentState) -> Dict[str, Any]:
        """Finalize the TDD agent execution."""
        self.log("info", "Finalizing TDD Agent execution")
        
        # Get base finalization data
        final_results = super().finalize(state)
        
        # Add TDD-specific results
        final_results.update({
            "project_path": self.project_path,
            "ticket_number": self.ticket_number,
            "tdd_iterations": self.iteration_count,
            "final_tdd_status": self.status.value
        })
        
        # Include final iteration result if available
        latest_result = state.get("iteration_result")
        if latest_result:
            final_results["final_iteration_result"] = latest_result
        
        self.log("info", f"TDD Agent completed after {self.iteration_count} iterations")
        return final_results
    
    def pre_iteration_hook(self, state: AgentState) -> None:
        """Hook called before each TDD iteration."""
        # Log current state
        iteration_num = state.iteration + 1
        self.log("debug", f"Starting TDD iteration {iteration_num}")
    
    def post_iteration_hook(self, state: AgentState, result: AgentResult) -> None:
        """Hook called after each TDD iteration."""
        # Log iteration completion
        self.log("debug", f"Completed TDD iteration {state.iteration}")
        
        # Log any warnings or errors
        if result.error:
            self.log("warning", f"Iteration had error: {result.error}")


def create_tdd_agent(project_path: str, ticket_number: str, max_iterations: int = 50) -> TDDAgent:
    """
    Convenience function to create a TDD agent with simple parameters.
    
    Args:
        project_path: Path to the project directory
        ticket_number: Ticket or issue identifier
        max_iterations: Maximum number of iterations
        
    Returns:
        Configured TDD agent
    """
    config = AgentConfig.create_simple(
        name="tdd-agent",
        agent_type="tdd",
        max_iterations=max_iterations,
        project_path=project_path,
        ticket_number=ticket_number
    )
    
    return TDDAgent(config)