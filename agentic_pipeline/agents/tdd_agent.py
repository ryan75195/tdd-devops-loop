"""TDD Agent - Refactored from the original TDD DevOps Loop."""

import os
from typing import Any, Dict, List

from ..core.agent import Agent, AgentResult, AgentStatus
from ..core.state import AgentState
from ..core.config import AgentConfig

# Import the TDD infrastructure
from ..utils.logger import Logger
from ..utils.usage_parser import UsageLimitParser
from ..tdd_core.sdk_session_manager import ClaudeSDKSessionManager
from ..tdd_core.config import Configuration
from ..services.openai_reflection_service import OpenAIReflectionService
import sys
from pathlib import Path
# Add config directory to path for imports
config_dir = Path(__file__).parent.parent.parent / "config"
sys.path.insert(0, str(config_dir))
from settings_manager import get_settings


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
        },
        "max_reflection_retries": {
            "type": "integer",
            "required": False,
            "default": 3,
            "description": "Maximum number of retries for reflection feedback loop (default: 3)"
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
        self.reflection_service = None
        
        # State tracking
        self.project_path = None
        self.work_item_id = None
        self.organization = None
        self.max_reflection_retries = None
        self.current_tasks = []
        self.current_task_index = 0
    
    def initialize(self, context: Dict[str, Any] = None) -> None:
        """Initialize the TDD agent with project context."""
        self.log("info", "Initializing TDD Agent")
        
        # Extract configuration
        self.project_path = self.config.get_parameter("project_path")
        self.work_item_id = self.config.get_parameter("work_item_id")
        self.organization = self.config.get_parameter("organization")
        
        # Get reflection settings from config file
        settings = get_settings()
        tdd_config = settings.get_tdd_config()
        self.max_reflection_retries = self.config.get_parameter("max_reflection_retries", 
                                                                tdd_config.get('max_reflection_retries', 3))
        
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
        
        # Initialize OpenAI reflection service for quality gate
        settings = get_settings()
        tdd_config = settings.get_tdd_config()
        
        if tdd_config.get('enable_reflection', True):
            try:
                self.reflection_service = OpenAIReflectionService()
                if self.reflection_service.test_connection():
                    self.log("info", f"OpenAI reflection service initialized with model: {self.reflection_service.model}")
                else:
                    self.log("warning", "OpenAI reflection service connection test failed - continuing without reflection")
                    self.reflection_service = None
            except Exception as e:
                self.log("warning", f"Failed to initialize OpenAI reflection service: {e} - continuing without reflection")
                self.reflection_service = None
        else:
            self.log("info", "Reflection disabled in settings - continuing without reflection")
            self.reflection_service = None
        
        # Change to project directory
        if os.path.exists(self.project_path):
            os.chdir(self.project_path)
            self.log("info", f"Changed to project directory: {self.project_path}")
        else:
            raise ValueError(f"Project path does not exist: {self.project_path}")
        
        # Fetch work item and its tasks
        try:
            self.log("info", f"Fetching Azure DevOps work item: {self.work_item_id}")
            self._get_work_item_details(self.work_item_id)
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
            task_progress = f"{self.current_task_index + 1}/{len(self.current_tasks)}"
            
            self.log("info", "")
            self.log("info", "=" * 60)
            self.log("info", f"🎯 STARTING TASK {task_progress}: {current_task['id']}")
            self.log("info", f"📝 Title: {current_task['title']}")
            self.log("info", f"📋 State: {current_task.get('state', 'Unknown')}")
            self.log("info", "=" * 60)
            
            # Mark task as "In Progress" when starting work
            if current_task.get('state') not in ['In Progress', 'Done']:
                self.log("info", f"🔄 Marking task as In Progress...")
                self._update_task_status(current_task['id'], "In Progress")
                current_task['state'] = 'In Progress'  # Update local state
            
            # TDD iteration with reflection loop
            task_completed = self._execute_tdd_with_reflection(current_task)
            
            if not task_completed:
                # If we couldn't complete the task after max retries, log and continue
                self.log("warning", f"Task {current_task['id']} could not be completed after maximum reflection retries - moving to next task")
            
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
            
            # Log task completion and move to next task
            self.log("info", f"✅ TASK {current_task['id']} COMPLETED")
            self.current_task_index += 1
            
            # Check if all tasks are done
            if self.current_task_index >= len(self.current_tasks):
                self.log("info", "🎉 ALL TDD TASKS COMPLETED!")
                self.status = AgentStatus.COMPLETED
                status_message = "All TDD tasks completed successfully"
            else:
                next_task = self.current_tasks[self.current_task_index]
                self.log("info", f"➡️  ADVANCING TO NEXT TASK: {next_task['id']}")
                self.log("info", f"📝 Next task: {next_task.get('title', 'Unknown')}")
                status_message = f"Task {current_task['id']} completed. Next: {next_task['id']}"
            
            # Update state with iteration results
            iteration_data = {
                "task_completed": task_completed,
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
    
    def _execute_tdd_with_reflection(self, current_task: Dict[str, Any]) -> bool:
        """Execute TDD with OpenAI reflection quality gate."""
        retry_count = 0
        task_id = current_task['id']
        task_title = current_task.get('title', 'Unknown Task')
        
        self.log("info", "")
        self.log("info", "=" * 80)
        self.log("info", f"🎯 STARTING TDD + REFLECTION LOOP FOR TASK {task_id}")
        self.log("info", f"📋 Task: {task_title}")
        self.log("info", f"🔄 Max Attempts: {self.max_reflection_retries}")
        self.log("info", "=" * 80)
        
        while retry_count < self.max_reflection_retries:
            attempt_num = retry_count + 1
            self.log("info", "")
            self.log("info", f"🔄 ATTEMPT {attempt_num}/{self.max_reflection_retries} - TDD ITERATION")
            self.log("info", "-" * 50)
            
            # Run TDD iteration using session manager with task details
            self.log("info", f"🤖 Running Claude Code SDK TDD iteration...")
            usage_limit_epoch, return_code = self.session_manager.run_single_iteration(
                current_task
            )
            
            # Handle usage limits
            if usage_limit_epoch:
                self.log("warning", "⏱️  Claude usage limit detected - waiting for reset")
                self.usage_parser.sleep_until_reset(usage_limit_epoch, self.logger)
                import time
                time.sleep(2)
            
            # Process return code
            if return_code != 0:
                self.log("warning", f"⚠️  TDD iteration exited with code {return_code}")
            else:
                self.log("info", f"✅ TDD iteration completed successfully")
            
            # Get current uncommitted changes
            self.log("info", f"📊 Checking for working changes...")
            current_diff = self._get_git_working_changes()
            
            if not current_diff or len(current_diff.strip()) == 0:
                self.log("info", f"📭 No working changes detected - accepting iteration")
                self.log("info", f"✅ TASK {task_id} COMPLETED (no changes needed)")
                return True
            
            change_size = len(current_diff)
            lines_changed = current_diff.count('\n')
            self.log("info", f"📏 Working changes detected: {change_size} chars, {lines_changed} lines")
            
            # Skip reflection if no reflection service available
            if not self.reflection_service:
                self.log("warning", f"⚠️  No reflection service available - auto-approving changes")
                self._commit_changes(f"Task {task_id}: TDD iteration completed (no reflection)")
                self.log("info", f"✅ TASK {task_id} COMPLETED (no reflection)")
                return True
            
            # Run reflection quality gate
            self.log("info", "")
            self.log("info", f"🤖 STARTING GPT-5 REFLECTION ANALYSIS...")
            self.log("info", f"🔍 Evaluating changes against BDD scenarios...")
            
            try:
                bdd_scenarios = current_task.get('acceptance_criteria', '') or current_task.get('description', '')
                iteration_context = f"TDD iteration {attempt_num}/{self.max_reflection_retries}"
                
                reflection_result = self.reflection_service.evaluate_tdd_implementation(
                    git_diff=current_diff,
                    task_details=current_task,
                    bdd_scenarios=bdd_scenarios,
                    iteration_context=iteration_context
                )
                
                self.log("info", f"📊 REFLECTION COMPLETE")
                self.log("info", f"🎯 Status: {reflection_result.status.upper()}")
                
                # Show full feedback without truncation
                self.log("info", f"📝 Feedback (Full):")
                feedback_lines = reflection_result.feedback.split('\n')
                for line in feedback_lines:
                    if line.strip():
                        self.log("info", f"   {line.strip()}")
                
                if reflection_result.status == "continue":
                    self.log("info", "")
                    self.log("info", f"✅ REFLECTION APPROVED - COMMITTING CHANGES")
                    success = self._commit_changes(f"Task {task_id}: TDD iteration approved by reflection")
                    if success:
                        self.log("info", f"🎉 TASK {task_id} SUCCESSFULLY COMPLETED!")
                        self.log("info", "=" * 80)
                        return True
                    else:
                        self.log("error", f"❌ Commit failed - treating as completion anyway")
                        return True
                        
                elif reflection_result.status == "retry":
                    retry_count += 1
                    if retry_count < self.max_reflection_retries:
                        self.log("info", "")
                        self.log("info", f"🔄 REFLECTION REQUESTS RETRY ({retry_count}/{self.max_reflection_retries})")
                        self.log("info", f"🎯 Providing feedback to Claude for improvement...")
                        # Run another TDD iteration with the feedback (keep working changes uncommitted)
                        self._run_feedback_iteration(current_task, reflection_result.feedback)
                        continue  # Go to next iteration
                    else:
                        self.log("info", "")
                        self.log("warning", f"⚠️  MAXIMUM RETRIES REACHED ({self.max_reflection_retries}) - COMMITTING ANYWAY")
                        self._commit_changes(f"Task {task_id}: TDD iteration (max retries reached)")
                        self.log("info", f"⚠️  TASK {task_id} COMPLETED (with warnings)")
                        self.log("info", "=" * 80)
                        return False
                else:
                    self.log("warning", f"⚠️  Unknown reflection status: {reflection_result.status}")
                    self._commit_changes(f"Task {task_id}: TDD iteration completed")
                    self.log("info", f"✅ TASK {task_id} COMPLETED (unknown status)")
                    return True
                    
            except Exception as e:
                self.log("error", f"❌ REFLECTION ANALYSIS FAILED: {e}")
                self.log("info", f"🔄 Accepting iteration due to reflection failure")
                self._commit_changes(f"Task {task_id}: TDD iteration (reflection failed)")
                self.log("info", f"⚠️  TASK {task_id} COMPLETED (reflection failed)")
                self.log("info", "=" * 80)
                return True
        
        # Should not reach here, but just in case
        self.log("error", f"❌ Unexpected end of retry loop")
        return False
    
    def _get_git_working_changes(self) -> str:
        """Get current git working tree changes (staged + unstaged)."""
        import subprocess
        try:
            # Get all working tree changes (staged + unstaged)
            result = subprocess.run(
                ['git', 'diff', 'HEAD'], 
                capture_output=True, 
                text=True, 
                cwd=self.project_path
            )
            if result.returncode == 0:
                return result.stdout
            else:
                self.log("warning", f"Git diff failed: {result.stderr}")
                return ""
        except Exception as e:
            self.log("error", f"Error getting git working changes: {e}")
            return ""
    
    def _commit_changes(self, commit_message: str) -> bool:
        """Commit current working changes."""
        import subprocess
        try:
            self.log("info", f"💾 COMMITTING CHANGES...")
            self.log("info", f"📝 Message: {commit_message}")
            
            # Add all changes
            add_result = subprocess.run(
                ['git', 'add', '.'],
                capture_output=True,
                text=True,
                cwd=self.project_path
            )
            
            if add_result.returncode != 0:
                self.log("error", f"❌ Git add failed: {add_result.stderr}")
                return False
            
            # Show what's being committed
            status_result = subprocess.run(
                ['git', 'status', '--short'],
                capture_output=True,
                text=True,
                cwd=self.project_path
            )
            
            if status_result.returncode == 0 and status_result.stdout.strip():
                self.log("info", f"📋 Files to commit:")
                for line in status_result.stdout.strip().split('\n'):
                    if line.strip():
                        self.log("info", f"   {line}")
            
            # Commit changes
            commit_result = subprocess.run(
                ['git', 'commit', '-m', commit_message],
                capture_output=True,
                text=True,
                cwd=self.project_path
            )
            
            if commit_result.returncode == 0:
                # Get commit hash
                hash_result = subprocess.run(
                    ['git', 'rev-parse', '--short', 'HEAD'],
                    capture_output=True,
                    text=True,
                    cwd=self.project_path
                )
                commit_hash = hash_result.stdout.strip() if hash_result.returncode == 0 else "unknown"
                
                self.log("info", f"✅ COMMIT SUCCESSFUL!")
                self.log("info", f"🔗 Hash: {commit_hash}")
                return True
            else:
                self.log("warning", f"❌ Git commit failed: {commit_result.stderr}")
                return False
                
        except Exception as e:
            self.log("error", f"❌ Error committing changes: {e}")
            return False
    
    def _run_feedback_iteration(self, current_task: Dict[str, Any], feedback: str) -> None:
        """Run an additional TDD iteration with reflection feedback."""
        self.log("info", f"🔄 Running feedback iteration for task {current_task['id']}")
        
        # Create a modified task with feedback included
        feedback_task = current_task.copy()
        original_description = feedback_task.get('description', '')
        original_criteria = feedback_task.get('acceptance_criteria', '')
        
        # Add feedback to the task context
        feedback_context = f"\n\n**REFLECTION FEEDBACK FROM PREVIOUS ITERATION:**\n{feedback}\n\nPlease address this feedback in your next TDD iteration."
        
        feedback_task['description'] = original_description + feedback_context
        feedback_task['acceptance_criteria'] = original_criteria + feedback_context
        
        # Run the feedback iteration (without reflection to avoid infinite loops)
        try:
            usage_limit_epoch, return_code = self.session_manager.run_single_iteration(feedback_task)
            
            # Handle usage limits
            if usage_limit_epoch:
                self.log("warning", "Claude usage limit detected during feedback iteration")
                self.usage_parser.sleep_until_reset(usage_limit_epoch, self.logger)
                import time
                time.sleep(2)
            
            if return_code != 0:
                self.log("warning", f"Feedback iteration exited with code {return_code}")
                
        except Exception as e:
            self.log("error", f"Error during feedback iteration: {e}")

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
            
            subprocess.run(cmd, capture_output=True, text=True, check=True)
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