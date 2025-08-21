"""TDD Agent - Refactored from the original TDD DevOps Loop."""

import os
from typing import Any, Dict, List

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
        "work_item_id": {
            "type": "string",
            "required": True,
            "description": "Azure DevOps PBI work item ID for TDD implementation"
        },
        "organization": {
            "type": "string",
            "required": False,
            "description": "Azure DevOps organization URL (optional if configured globally)"
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
        self.work_item_id = None
        self.organization = None
        self.current_tasks = []
        self.current_task_index = 0
    
    def initialize(self, context: Dict[str, Any]) -> None:
        """Initialize the TDD agent with project context."""
        self.log("info", "Initializing TDD Agent")
        
        # Extract configuration
        self.project_path = self.config.get_parameter("project_path")
        self.work_item_id = self.config.get_parameter("work_item_id")
        self.organization = self.config.get_parameter("organization")
        
        if not self.project_path or not self.work_item_id:
            raise ValueError("TDD Agent requires 'project_path' and 'work_item_id' parameters")
        
        # Setup TDD infrastructure
        self.logger = Logger()
        self.usage_parser = UsageLimitParser()
        
        # Create TDD configuration
        self.tdd_config = Configuration()
        # No max iterations limit - let TDD work continue until tasks are complete
        
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
        
        # Fetch work item and its tasks
        try:
            self.log("info", f"Fetching Azure DevOps work item: {self.work_item_id}")
            work_item_details = self._get_work_item_details(self.work_item_id)
            self.current_tasks = self._get_child_tasks(self.work_item_id)
            
            if not self.current_tasks:
                raise ValueError(f"No child tasks found for work item {self.work_item_id}")
            
            self.log("info", f"Found {len(self.current_tasks)} tasks to implement")
            for i, task in enumerate(self.current_tasks, 1):
                self.log("info", f"  {i}. Task {task['id']}: {task['title']}")
        
        except Exception as e:
            raise ValueError(f"Failed to fetch work item details: {e}")
        
        self.status = AgentStatus.RUNNING
        self.log("info", "TDD Agent initialization completed")
    
    def execute_iteration(self, state: AgentState) -> AgentResult:
        """Execute one TDD iteration."""
        iteration_num = state.iteration + 1
        self.log("info", f"Executing TDD iteration {iteration_num}")
        
        try:
            # Log iteration header (similar to original)
            self.logger.iteration_header(iteration_num)
            
            # Find next incomplete task
            while self.current_task_index < len(self.current_tasks):
                current_task = self.current_tasks[self.current_task_index]
                
                # Check current state in Azure DevOps (not cached state)
                try:
                    fresh_task_details = self._get_work_item_details(current_task['id'])
                    current_state = fresh_task_details.get('fields', {}).get('System.State', '')
                    
                    # Skip tasks that are already completed
                    if current_state == 'Done':
                        self.log("info", f"⏭️  Skipping task {current_task['id']} - already completed (state: {current_state})")
                        self.current_task_index += 1
                        continue
                    
                    # Update local cache with current state
                    current_task['state'] = current_state
                    
                except Exception as e:
                    self.log("warning", f"Could not check current state of task {current_task['id']}: {e}")
                    # Continue with cached state if API call fails
                
                # Found an incomplete task
                break
            
            # Check if all tasks are completed
            if self.current_task_index >= len(self.current_tasks):
                self.log("info", "All tasks completed")
                return AgentResult(
                    status=AgentStatus.COMPLETED,
                    message="All TDD tasks completed successfully",
                    data={"completed_tasks": len(self.current_tasks)},
                    terminal=True
                )
            
            # Get current incomplete task
            current_task = self.current_tasks[self.current_task_index]
            self.log("info", f"Processing task {current_task['id']}: {current_task['title']}")
            
            # Mark task as "In Progress" when starting work
            if current_task.get('state') not in ['In Progress', 'Done']:
                self.log("info", f"🔄 Starting work on task {current_task['id']} - marking as In Progress")
                self._update_task_status(current_task['id'], "In Progress")
                current_task['state'] = 'In Progress'  # Update local state
            
            # Run TDD iteration using session manager with task details
            usage_limit_epoch, return_code = self.session_manager.run_single_iteration(
                current_task
            )
            
            # Handle usage limits
            if usage_limit_epoch:
                self.log("warning", "Claude usage limit detected")
                self.usage_parser.sleep_until_reset(usage_limit_epoch, self.logger)
                # Add extra delay between tasks to avoid rate limits
                import time
                time.sleep(2)
            
            # Process return code
            if return_code != 0:
                self.log("warning", f"TDD iteration exited with code {return_code}")
            
            # Auto-advance to next task after each iteration
            self.log("info", f"TDD iteration completed for task {current_task['id']} - auto-advancing to next task")
            
            # Mark current task as done in Azure DevOps
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    if self._update_task_status(current_task['id'], "Done"):
                        break
                    else:
                        self.log("warning", f"Failed to update task status (attempt {attempt + 1}/{max_retries})")
                        if attempt < max_retries - 1:
                            import time
                            time.sleep(1)  # Brief delay before retry
                except Exception as e:
                    self.log("error", f"Error updating task status (attempt {attempt + 1}/{max_retries}): {e}")
                    if attempt == max_retries - 1:
                        self.log("error", f"Failed to update task {current_task['id']} status after {max_retries} attempts")
            
            # Move to next task
            self.current_task_index += 1
            
            # Check if all tasks are done
            if self.current_task_index >= len(self.current_tasks):
                self.status = AgentStatus.COMPLETED
                status_message = "All TDD tasks completed successfully"
            else:
                next_task = self.current_tasks[self.current_task_index]
                status_message = f"Task {current_task['id']} completed. Next: {next_task['id']}"
            
            # Update state with iteration results
            iteration_data = {
                "return_code": return_code,
                "usage_limit_epoch": usage_limit_epoch,
                "timestamp": self.logger.get_timestamp(),
                "current_task": current_task,
                "task_index": self.current_task_index,
                "total_tasks": len(self.current_tasks),
                "auto_advanced": True
            }
            
            return AgentResult(
                status=self.status,
                message=status_message,
                data=iteration_data,
                terminal=self.status == AgentStatus.COMPLETED
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
            "work_item_id": self.work_item_id,
            "tdd_iterations": self.iteration_count,
            "final_tdd_status": self.status.value,
            "total_tasks": len(self.current_tasks),
            "completed_tasks": self.current_task_index
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
    
    def _get_work_item_details(self, work_item_id: str) -> Dict[str, Any]:
        """Fetch work item details from Azure DevOps."""
        import subprocess
        import json
        
        try:
            cmd = ["az", "boards", "work-item", "show", "--id", work_item_id]
            if self.organization:
                cmd.extend(["--organization", self.organization])
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            work_item = json.loads(result.stdout)
            
            self.log("debug", f"Fetched work item {work_item_id}: {work_item.get('fields', {}).get('System.Title', 'Unknown')}")
            return work_item
            
        except subprocess.CalledProcessError as e:
            self.log("error", f"Failed to fetch work item {work_item_id}: {e}")
            raise
        except json.JSONDecodeError as e:
            self.log("error", f"Failed to parse work item JSON: {e}")
            raise
    
    def _get_child_tasks(self, parent_id: str) -> List[Dict[str, Any]]:
        """Get all child task work items for a parent PBI."""
        import subprocess
        import json
        
        try:
            # Query for child work items
            query = f"SELECT [System.Id], [System.Title], [System.Description], [System.State] FROM WorkItems WHERE [System.Parent] = {parent_id} AND [System.WorkItemType] = 'Task'"
            
            cmd = ["az", "boards", "query", "--wiql", query]
            if self.organization:
                cmd.extend(["--organization", self.organization])
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            query_result = json.loads(result.stdout)
            
            self.log("debug", f"Query result type: {type(query_result)}, content: {query_result}")
            
            tasks = []
            # Handle different possible response formats
            work_items = []
            if isinstance(query_result, list):
                # If the result is directly a list of work items
                work_items = query_result
            elif isinstance(query_result, dict):
                # If the result is wrapped in a dictionary
                work_items = query_result.get("workItems", [])
            
            for item in work_items:
                task_id = str(item["id"])
                # Get full task details
                task_details = self._get_work_item_details(task_id)
                
                fields = task_details.get("fields", {})
                task_info = {
                    "id": task_id,
                    "title": fields.get("System.Title", ""),
                    "description": fields.get("System.Description", ""),
                    "state": fields.get("System.State", ""),
                    "acceptance_criteria": fields.get("Microsoft.VSTS.Common.AcceptanceCriteria", ""),
                    "full_details": task_details
                }
                tasks.append(task_info)
            
            # Sort tasks by ID for consistent processing order
            tasks.sort(key=lambda x: int(x["id"]))
            return tasks
            
        except subprocess.CalledProcessError as e:
            self.log("error", f"Failed to query child tasks for {parent_id}: {e}")
            raise
        except json.JSONDecodeError as e:
            self.log("error", f"Failed to parse query results: {e}")
            raise
    
    def _update_task_status(self, task_id: str, state: str) -> bool:
        """Update task status in Azure DevOps."""
        import subprocess
        
        try:
            cmd = [
                "az", "boards", "work-item", "update", 
                "--id", task_id, 
                "--state", state
            ]
            if self.organization:
                cmd.extend(["--organization", self.organization])
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            self.log("info", f"✅ Updated task {task_id} to '{state}' status")
            return True
            
        except subprocess.CalledProcessError as e:
            self.log("error", f"Failed to update task {task_id} status: {e}")
            return False


def create_tdd_agent(project_path: str, work_item_id: str, organization: str = None) -> TDDAgent:
    """
    Convenience function to create a TDD agent with simple parameters.
    
    Args:
        project_path: Path to the project directory
        work_item_id: Azure DevOps PBI work item ID
        organization: Azure DevOps organization URL (optional)
        
    Returns:
        Configured TDD agent
    """
    params = {
        "project_path": project_path,
        "work_item_id": work_item_id
    }
    
    if organization:
        params["organization"] = organization
    
    config = AgentConfig.create_simple(
        name="tdd-agent",
        agent_type="tdd",
        **params
    )
    
    return TDDAgent(config)