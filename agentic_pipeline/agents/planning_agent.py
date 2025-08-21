"""Planning Agent - Converts markdown specifications to Azure DevOps work items."""

import json
import subprocess
from typing import Any, Dict, List
from pathlib import Path

from ..core.agent import Agent, AgentResult, AgentStatus
from ..core.state import AgentState
from ..core.config import AgentConfig

from ..utils.logger import Logger
from ..utils.usage_parser import UsageLimitParser
from ..tdd_core.planning_session_manager import PlanningSessionManager
from ..tdd_core.config import Configuration


class PlanningAgent(Agent):
    """
    Planning Agent for converting markdown specifications to Azure DevOps work items.
    
    Takes a markdown specification file and uses Claude Code SDK to analyze it,
    then programmatically creates structured work items in Azure DevOps.
    """
    
    # Agent metadata for auto-discovery
    AGENT_TYPE = "planning"
    DESCRIPTION = "Converts natural language specs to Azure DevOps work items with BDD test cases"
    VERSION = "1.0.0"
    AUTHOR = "Agentic Pipeline Framework"
    TAGS = ["planning", "bdd", "azure-devops", "project-management"]
    CONFIG_SCHEMA = {
        "spec_file": {
            "type": "string",
            "required": True,
            "description": "Path to markdown specification file"
        },
        "project_name": {
            "type": "string", 
            "required": True,
            "description": "Azure DevOps project name"
        },
        "organization": {
            "type": "string",
            "required": True,
            "description": "Azure DevOps organization URL"
        },
        "parent_id": {
            "type": "integer",
            "required": False,
            "description": "Parent work item ID to link to"
        },
        "area_path": {
            "type": "string",
            "required": False,
            "description": "Area path for work items"
        },
        "iteration_path": {
            "type": "string",
            "required": False,
            "description": "Iteration path for work items"
        }
    }
    
    def __init__(self, config: AgentConfig):
        """Initialize the Planning agent."""
        super().__init__(config)
        
        # Planning-specific components
        self.logger = None
        self.usage_parser = None
        self.session_manager = None
        self.planning_config = None
        
        # Configuration parameters
        self.spec_file = config.get_parameter("spec_file")
        self.project_name = config.get_parameter("project_name")
        self.organization = config.get_parameter("organization")
        self.parent_id = config.get_parameter("parent_id")
        self.area_path = config.get_parameter("area_path")
        self.iteration_path = config.get_parameter("iteration_path")
        
        # State tracking
        self.spec_content = ""
        self.work_breakdown = {}
        self.created_work_items = []
    
    def initialize(self, context: Dict[str, Any]) -> None:
        """Initialize the planning agent."""
        self.log("info", "Initializing Planning Agent")
        
        # Validate required parameters
        if not self.spec_file or not self.project_name or not self.organization:
            raise ValueError("Planning Agent requires 'spec_file', 'project_name', and 'organization' parameters")
        
        # Load specification file
        spec_path = Path(self.spec_file)
        if not spec_path.exists():
            raise FileNotFoundError(f"Specification file not found: {spec_path}")
        
        with open(spec_path, 'r', encoding='utf-8') as f:
            self.spec_content = f.read()
        
        self.log("info", f"Loaded specification from: {spec_path}")
        
        # Setup planning infrastructure
        self.logger = Logger()
        self.usage_parser = UsageLimitParser()
        
        # Create planning configuration
        self.planning_config = Configuration()
        self.planning_config.max_iterations = 1  # Single analysis iteration
        
        # Initialize Claude Code SDK session manager for planning
        self.session_manager = PlanningSessionManager(
            self.planning_config,
            self.logger,
            self.usage_parser
        )
        
        self.status = AgentStatus.RUNNING
        self.log("info", "Planning Agent initialization completed")
    
    def execute_iteration(self, state: AgentState) -> AgentResult:
        """Execute planning iteration - analyze spec and create work items."""
        iteration_num = state.iteration + 1
        self.log("info", f"Executing planning iteration {iteration_num}")
        
        try:
            if iteration_num == 1:
                # Single iteration: analyze specification and create work items
                return self._analyze_and_create_work_items(state)
            else:
                # Should be terminal after first iteration
                return AgentResult(
                    status=AgentStatus.COMPLETED,
                    message="Planning completed successfully",
                    data={},
                    terminal=True
                )
                
        except Exception as e:
            self.log("error", f"Planning iteration failed: {e}")
            return AgentResult(
                status=AgentStatus.FAILED,
                message=f"Planning failed: {str(e)}",
                data={"error": str(e)},
                terminal=True,
                error=str(e)
            )
    
    def check_terminal_condition(self, state: AgentState) -> bool:
        """Check if planning should terminate."""
        # Terminal after first iteration when work items are created
        return state.iteration >= 1
    
    def finalize(self, state: AgentState) -> Dict[str, Any]:
        """Finalize and return summary."""
        base_result = super().finalize(state)
        base_result.update({
            "created_work_items": self.created_work_items,
            "work_breakdown": self.work_breakdown,
            "total_items_created": len(self.created_work_items)
        })
        return base_result
    
    def _analyze_and_create_work_items(self, state: AgentState) -> AgentResult:
        """Analyze specification and create Azure DevOps work items."""
        self.log("info", "Analyzing specification with Claude SDK...")
        
        # Step 1: Use Claude SDK to analyze specification
        self.work_breakdown = self.session_manager.analyze_specification(self.spec_content)
        
        if not self.work_breakdown:
            return AgentResult(
                status=AgentStatus.FAILED,
                message="Failed to analyze specification with Claude SDK",
                data={},
                terminal=True
            )
        
        # Step 2: Create Azure DevOps work items
        self.log("info", "Creating Azure DevOps work items...")
        self.created_work_items = self._create_azure_work_items(self.work_breakdown)
        
        # Step 3: Log results
        self.log("info", f"Successfully created {len(self.created_work_items)} work items")
        for item in self.created_work_items:
            self.log("info", f"Created: {item.get('type')} #{item.get('id')} - {item.get('title')}")
        
        return AgentResult(
            status=AgentStatus.COMPLETED,
            message=f"Successfully created {len(self.created_work_items)} work items in Azure DevOps",
            data={
                "work_breakdown": self.work_breakdown,
                "created_items": self.created_work_items,
                "total_items": len(self.created_work_items)
            },
            terminal=True
        )
    
    def _create_azure_work_items(self, work_breakdown: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create Azure DevOps work items from structured breakdown."""
        created_items = []
        
        try:
            # Step 1: Create Product Backlog Item (PBI)
            pbi_data = work_breakdown.get("product_backlog_item", {})
            pbi_id = self._create_pbi(pbi_data)
            
            if pbi_id:
                created_items.append({
                    "type": "Product Backlog Item",
                    "id": pbi_id,
                    "title": pbi_data.get("title", "")
                })
                
                # Step 2: Create Task work items linked to PBI
                tasks_data = work_breakdown.get("tasks", [])
                for task_data in tasks_data:
                    task_id = self._create_task(task_data, pbi_id)
                    if task_id:
                        created_items.append({
                            "type": "Task",
                            "id": task_id,
                            "title": task_data.get("title", ""),
                            "parent_id": pbi_id
                        })
            
            return created_items
            
        except Exception as e:
            self.log("error", f"Failed to create Azure DevOps work items: {e}")
            return created_items
    
    def _create_pbi(self, pbi_data: Dict[str, Any]) -> int:
        """Create a Product Backlog Item in Azure DevOps."""
        try:
            # Build az boards command for PBI
            cmd = [
                "az", "boards", "work-item", "create",
                "--type", "Product Backlog Item",
                "--title", pbi_data.get("title", ""),
                "--description", self._format_pbi_description(pbi_data),
                "--project", self.project_name,
                "--organization", self.organization
            ]
            
            # Add optional fields including acceptance criteria
            fields = []
            
            # Add acceptance criteria as separate field
            if pbi_data.get("acceptance_criteria"):
                ac_html = self._format_acceptance_criteria(pbi_data.get("acceptance_criteria"))
                fields.append(f"Microsoft.VSTS.Common.AcceptanceCriteria={ac_html}")
            
            if self.area_path:
                cmd.extend(["--area", self.area_path])
                
            if self.iteration_path:
                cmd.extend(["--iteration", self.iteration_path])
            
            # Add fields if any
            if fields:
                cmd.extend(["--fields", ";".join(fields)])
            
            # Execute command
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Parse work item ID from JSON response
            work_item = json.loads(result.stdout)
            pbi_id = work_item.get("id")
            
            # Link PBI to specified parent if provided
            if pbi_id and self.parent_id:
                self._link_task_to_parent(pbi_id, self.parent_id)
            
            self.log("info", f"Created PBI #{pbi_id}: {pbi_data.get('title', '')}")
            return pbi_id
            
        except subprocess.CalledProcessError as e:
            self.log("error", f"Failed to create PBI: {e.stderr}")
            return None
        except Exception as e:
            self.log("error", f"Error creating PBI: {e}")
            return None
    
    def _create_task(self, task_data: Dict[str, Any], parent_id: int) -> int:
        """Create a Task work item in Azure DevOps."""
        try:
            # Build az boards command for Task (without parent field)
            cmd = [
                "az", "boards", "work-item", "create",
                "--type", "Task",
                "--title", task_data.get("title", ""),
                "--description", self._format_task_description(task_data),
                "--project", self.project_name,
                "--organization", self.organization
            ]
            
            # Add area and iteration if specified
            if self.area_path:
                cmd.extend(["--area", self.area_path])
                
            if self.iteration_path:
                cmd.extend(["--iteration", self.iteration_path])
            
            # Skip effort field for now to focus on basic functionality
            
            # Execute command
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Parse work item ID from JSON response
            work_item = json.loads(result.stdout)
            task_id = work_item.get("id")
            
            # Create parent-child relationship
            if task_id and parent_id:
                self._link_task_to_parent(task_id, parent_id)
            
            self.log("info", f"Created Task #{task_id}: {task_data.get('title', '')}")
            return task_id
            
        except subprocess.CalledProcessError as e:
            self.log("error", f"Failed to create Task: {e.stderr}")
            return None
        except Exception as e:
            self.log("error", f"Error creating Task: {e}")
            return None
    
    def _link_task_to_parent(self, task_id: int, parent_id: int) -> bool:
        """Create parent-child relationship between task and PBI."""
        try:
            # Use az boards work-item relation add to link task to parent
            cmd = [
                "az", "boards", "work-item", "relation", "add",
                "--id", str(task_id),
                "--relation-type", "parent",
                "--target-id", str(parent_id),
                "--organization", self.organization
            ]
            
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            self.log("info", f"Linked Task #{task_id} to Parent #{parent_id}")
            return True
            
        except subprocess.CalledProcessError as e:
            self.log("error", f"Failed to link Task #{task_id} to Parent #{parent_id}: {e.stderr}")
            return False
        except Exception as e:
            self.log("error", f"Error linking Task to Parent: {e}")
            return False
    
    def _format_pbi_description(self, pbi_data: Dict[str, Any]) -> str:
        """Format PBI description with HTML for Azure DevOps (without acceptance criteria)."""
        description = pbi_data.get("description", "")
        
        html_parts = []
        
        # Add main description only
        if description:
            html_parts.append(f"<h3>Problem Statement</h3>")
            html_parts.append(f"<p>{description}</p>")
        
        return "".join(html_parts)
    
    def _format_acceptance_criteria(self, acceptance_criteria: List[str]) -> str:
        """Format acceptance criteria as HTML list for Azure DevOps AC field."""
        if not acceptance_criteria:
            return ""
        
        html_parts = ["<ul>"]
        for criteria in acceptance_criteria:
            html_parts.append(f"<li>{criteria}</li>")
        html_parts.append("</ul>")
        
        return "".join(html_parts)
    
    def _format_task_description(self, task_data: Dict[str, Any]) -> str:
        """Format Task description with BDD Given/When/Then format."""
        description = task_data.get("description", "")
        given = task_data.get("given", [])
        when = task_data.get("when", [])
        then = task_data.get("then", [])
        requirements = task_data.get("requirements", [])
        
        html_parts = []
        
        # Add task description
        if description:
            html_parts.append(f"<p>{description}</p>")
        
        # Add BDD scenario
        html_parts.append("<h4>BDD Test Scenario</h4>")
        
        if given:
            html_parts.append("<p><strong>Given:</strong></p>")
            html_parts.append("<ul>")
            for item in given:
                html_parts.append(f"<li>{item}</li>")
            html_parts.append("</ul>")
        
        if when:
            html_parts.append("<p><strong>When:</strong></p>")
            html_parts.append("<ul>")
            for item in when:
                html_parts.append(f"<li>{item}</li>")
            html_parts.append("</ul>")
        
        if then:
            html_parts.append("<p><strong>Then:</strong></p>")
            html_parts.append("<ul>")
            for item in then:
                html_parts.append(f"<li>{item}</li>")
            html_parts.append("</ul>")
        
        # Add implementation requirements
        if requirements:
            html_parts.append("<h4>Implementation Requirements</h4>")
            html_parts.append("<ul>")
            for req in requirements:
                html_parts.append(f"<li>{req}</li>")
            html_parts.append("</ul>")
        
        return "".join(html_parts)