"""Workflow builder with DSL support for creating complex agent workflows."""

import yaml
import json
from typing import Any, Dict, List, Optional, Callable, Union
from pathlib import Path

from ..core.agent import Agent
from ..core.config import AgentConfig
from ..core.registry import get_registry
from .composite import CompositeAgent, WorkflowMode, AgentStep


class WorkflowBuilder:
    """
    Builder for creating complex agent workflows with fluent API and YAML/JSON support.
    
    Supports:
    - Fluent API for programmatic workflow construction
    - YAML/JSON configuration files
    - Conditional execution
    - Loop workflows
    - Error handling strategies
    """
    
    def __init__(self, name: str = "workflow"):
        """Initialize the workflow builder."""
        self.name = name
        self.steps: List[Dict[str, Any]] = []
        self.workflow_mode = WorkflowMode.SEQUENTIAL
        self.global_config = {}
        self.registry = get_registry()
    
    def set_mode(self, mode: Union[WorkflowMode, str]) -> 'WorkflowBuilder':
        """Set the workflow execution mode."""
        if isinstance(mode, str):
            mode = WorkflowMode(mode)
        self.workflow_mode = mode
        return self
    
    def set_global_config(self, config: Dict[str, Any]) -> 'WorkflowBuilder':
        """Set global configuration for all agents."""
        self.global_config.update(config)
        return self
    
    def add_agent(
        self,
        agent_type: str,
        name: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        condition: Optional[str] = None,
        on_success: Optional[str] = None,
        on_failure: Optional[str] = None,
        max_iterations: Optional[int] = None
    ) -> 'WorkflowBuilder':
        """
        Add an agent to the workflow.
        
        Args:
            agent_type: Type of agent to create
            name: Optional name for the agent (defaults to agent_type)
            config: Configuration parameters for the agent
            condition: Python expression for conditional execution
            on_success: Next step on success (for conditional workflows)
            on_failure: Next step on failure (for conditional workflows)
            max_iterations: Override max iterations for this agent
            
        Returns:
            Self for method chaining
        """
        step_config = {
            "agent_type": agent_type,
            "name": name or f"{agent_type}_{len(self.steps) + 1}",
            "config": {**self.global_config, **(config or {})},
            "condition": condition,
            "on_success": on_success,
            "on_failure": on_failure,
            "max_iterations": max_iterations
        }
        
        self.steps.append(step_config)
        return self
    
    def then(
        self,
        agent_type: str,
        name: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        max_iterations: Optional[int] = None
    ) -> 'WorkflowBuilder':
        """Add an agent that executes after the previous one (sequential mode)."""
        return self.add_agent(
            agent_type=agent_type,
            name=name,
            config=config,
            max_iterations=max_iterations
        )
    
    def if_condition(
        self,
        condition: str,
        agent_type: str,
        name: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        on_success: Optional[str] = None,
        on_failure: Optional[str] = None
    ) -> 'WorkflowBuilder':
        """Add a conditional agent step."""
        return self.add_agent(
            agent_type=agent_type,
            name=name,
            config=config,
            condition=condition,
            on_success=on_success,
            on_failure=on_failure
        )
    
    def parallel_group(self, agent_configs: List[Dict[str, Any]]) -> 'WorkflowBuilder':
        """Add a group of agents to execute in parallel (future feature)."""
        # For now, just add them sequentially
        # In the future, this could create a special parallel composite agent
        for agent_config in agent_configs:
            self.add_agent(**agent_config)
        return self
    
    def build(self) -> CompositeAgent:
        """Build the composite agent from the workflow definition."""
        # Create composite agent configuration
        composite_config = AgentConfig.create_simple(
            name=self.name,
            agent_type="composite_workflow",
            max_iterations=self.global_config.get("max_iterations", 50)
        )
        
        # Create composite agent
        composite = CompositeAgent(composite_config)
        composite.set_workflow_mode(self.workflow_mode)
        
        # Create and add agent steps
        for step_config in self.steps:
            agent = self._create_agent_from_config(step_config)
            condition = self._compile_condition(step_config.get("condition"))
            
            composite.add_step(
                agent=agent,
                condition=condition,
                on_success=step_config.get("on_success"),
                on_failure=step_config.get("on_failure"),
                max_iterations=step_config.get("max_iterations")
            )
        
        return composite
    
    def _create_agent_from_config(self, step_config: Dict[str, Any]) -> Agent:
        """Create an agent from step configuration."""
        agent_type = step_config["agent_type"]
        agent_name = step_config["name"]
        agent_params = step_config["config"]
        
        # Create agent configuration
        config = AgentConfig.create_simple(
            name=agent_name,
            agent_type=agent_type,
            max_iterations=step_config.get("max_iterations", 50),
            **agent_params
        )
        
        # Create agent using registry
        return self.registry.create_agent(agent_type, config)
    
    def _compile_condition(self, condition_str: Optional[str]) -> Optional[Callable]:
        """Compile a condition string into a callable function."""
        if not condition_str:
            return None
        
        # Create a safe evaluation environment
        def condition_func(state):
            # Provide access to state data
            local_vars = {
                "state": state,
                "data": state.data,
                "iteration": state.iteration,
                "get": state.get
            }
            
            try:
                return eval(condition_str, {"__builtins__": {}}, local_vars)
            except Exception as e:
                print(f"Warning: Condition evaluation failed: {e}")
                return False
        
        return condition_func
    
    @classmethod
    def from_yaml(cls, yaml_path: Union[str, Path]) -> 'WorkflowBuilder':
        """Create a workflow from YAML configuration file."""
        with open(yaml_path, 'r') as f:
            config = yaml.safe_load(f)
        return cls.from_dict(config)
    
    @classmethod
    def from_json(cls, json_path: Union[str, Path]) -> 'WorkflowBuilder':
        """Create a workflow from JSON configuration file."""
        with open(json_path, 'r') as f:
            config = json.load(f)
        return cls.from_dict(config)
    
    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> 'WorkflowBuilder':
        """Create a workflow from dictionary configuration."""
        builder = cls(name=config.get("name", "workflow"))
        
        # Set workflow mode
        if "mode" in config:
            builder.set_mode(config["mode"])
        
        # Set global configuration
        if "global_config" in config:
            builder.set_global_config(config["global_config"])
        
        # Add steps
        for step_config in config.get("steps", []):
            builder.add_agent(**step_config)
        
        return builder
    
    def to_dict(self) -> Dict[str, Any]:
        """Export workflow configuration to dictionary."""
        return {
            "name": self.name,
            "mode": self.workflow_mode.value,
            "global_config": self.global_config,
            "steps": self.steps
        }
    
    def to_yaml(self, output_path: Union[str, Path]) -> None:
        """Export workflow configuration to YAML file."""
        with open(output_path, 'w') as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, indent=2)
    
    def to_json(self, output_path: Union[str, Path]) -> None:
        """Export workflow configuration to JSON file."""
        with open(output_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)


def create_tdd_workflow(project_path: str, ticket_number: str) -> CompositeAgent:
    """
    Create a comprehensive TDD workflow.
    
    Args:
        project_path: Path to the project
        ticket_number: Ticket identifier
        
    Returns:
        Composite agent implementing TDD workflow
    """
    return (WorkflowBuilder("comprehensive_tdd")
            .set_global_config({
                "project_path": project_path,
                "ticket_number": ticket_number
            })
            .add_agent("tdd", "tdd_implementation", max_iterations=30)
            .then("code_review", "post_tdd_review", {
                "fix_issues": True,
                "review_criteria": ["code quality", "test coverage", "best practices"]
            })
            .build())


def create_debug_workflow(error_description: str, test_command: str = None) -> CompositeAgent:
    """
    Create a systematic debugging workflow.
    
    Args:
        error_description: Description of the error to debug
        test_command: Optional test command to verify fixes
        
    Returns:
        Composite agent implementing debug workflow
    """
    workflow = (WorkflowBuilder("systematic_debug")
                .set_mode(WorkflowMode.SEQUENTIAL)
                .add_agent("debug", "initial_debug", {
                    "error_description": error_description,
                    "debug_mode": "systematic",
                    "test_command": test_command
                }, max_iterations=10))
    
    # Add conditional code review if debugging succeeds
    if test_command:
        workflow.if_condition(
            "state.get('debugging_successful', False)",
            "code_review",
            "post_debug_review",
            {"review_criteria": ["bug fixes", "code quality"]}
        )
    
    return workflow.build()


def create_quality_improvement_workflow(target_files: List[str] = None) -> CompositeAgent:
    """
    Create a code quality improvement workflow.
    
    Args:
        target_files: Optional list of files to focus on
        
    Returns:
        Composite agent implementing quality improvement workflow
    """
    config = {}
    if target_files:
        config["target_files"] = target_files
    
    return (WorkflowBuilder("quality_improvement")
            .set_mode(WorkflowMode.LOOP)
            .add_agent("code_review", "quality_analysis", {
                **config,
                "review_criteria": ["performance", "maintainability", "security"],
                "fix_issues": False
            })
            .then("debug", "fix_critical_issues", {
                "error_description": "Critical issues found in code review",
                "debug_mode": "systematic"
            })
            .build())