"""Composite agent for orchestrating multiple agents in workflows."""

from typing import Any, Dict, List, Optional, Callable, Union
from enum import Enum

from ..core.agent import Agent, AgentResult, AgentStatus
from ..core.state import AgentState
from ..core.config import AgentConfig
from ..core.pipeline import AgentPipeline


class WorkflowMode(Enum):
    """Modes for workflow execution."""
    SEQUENTIAL = "sequential"      # Execute agents one after another
    PARALLEL = "parallel"          # Execute agents concurrently (not implemented)
    CONDITIONAL = "conditional"    # Execute agents based on conditions
    LOOP = "loop"                 # Loop through agents until condition met


class AgentStep:
    """Represents a single step in a workflow."""
    
    def __init__(
        self,
        agent: Agent,
        condition: Optional[Callable[[AgentState], bool]] = None,
        on_success: Optional[str] = None,
        on_failure: Optional[str] = None,
        max_iterations: Optional[int] = None
    ):
        self.agent = agent
        self.condition = condition  # Condition to execute this step
        self.on_success = on_success  # Next step ID on success
        self.on_failure = on_failure  # Next step ID on failure
        self.max_iterations = max_iterations
        self.step_id = agent.name


class CompositeAgent(Agent):
    """
    Composite agent that orchestrates multiple agents in complex workflows.
    
    Supports:
    - Sequential execution
    - Conditional branching
    - Loop execution
    - State passing between agents
    - Error handling and recovery
    """
    
    def __init__(self, config: AgentConfig):
        """Initialize the composite agent."""
        super().__init__(config)
        self.workflow_mode = WorkflowMode.SEQUENTIAL
        self.steps: List[AgentStep] = []
        self.step_results: Dict[str, Dict[str, Any]] = {}
        self.current_step_index = 0
        self.completed_steps: List[str] = []
        self.failed_steps: List[str] = []
    
    def set_workflow_mode(self, mode: WorkflowMode) -> None:
        """Set the workflow execution mode."""
        self.workflow_mode = mode
    
    def add_step(
        self,
        agent: Agent,
        condition: Optional[Callable[[AgentState], bool]] = None,
        on_success: Optional[str] = None,
        on_failure: Optional[str] = None,
        max_iterations: Optional[int] = None
    ) -> 'CompositeAgent':
        """
        Add a step to the workflow.
        
        Args:
            agent: Agent to execute in this step
            condition: Optional condition to execute this step
            on_success: Next step ID on success (for conditional workflows)
            on_failure: Next step ID on failure (for conditional workflows)
            max_iterations: Override max iterations for this step
            
        Returns:
            Self for method chaining
        """
        step = AgentStep(
            agent=agent,
            condition=condition,
            on_success=on_success,
            on_failure=on_failure,
            max_iterations=max_iterations
        )
        self.steps.append(step)
        return self
    
    def initialize(self, context: Dict[str, Any]) -> None:
        """Initialize the composite agent and all sub-agents."""
        self.log("info", f"Initializing CompositeAgent with {len(self.steps)} steps")
        
        # Initialize all sub-agents
        for i, step in enumerate(self.steps):
            try:
                step.agent.initialize(context)
                self.log("info", f"Initialized step {i+1}: {step.agent.name}")
            except Exception as e:
                self.log("error", f"Failed to initialize step {i+1} ({step.agent.name}): {e}")
                raise
        
        self.status = AgentStatus.RUNNING
        self.log("info", "CompositeAgent initialization completed")
    
    def execute_iteration(self, state: AgentState) -> AgentResult:
        """Execute one iteration of the composite workflow."""
        iteration_num = state.iteration + 1
        self.log("info", f"Executing composite workflow iteration {iteration_num}")
        
        if self.workflow_mode == WorkflowMode.SEQUENTIAL:
            return self._execute_sequential(state)
        elif self.workflow_mode == WorkflowMode.CONDITIONAL:
            return self._execute_conditional(state)
        elif self.workflow_mode == WorkflowMode.LOOP:
            return self._execute_loop(state)
        else:
            raise NotImplementedError(f"Workflow mode {self.workflow_mode} not implemented")
    
    def _execute_sequential(self, state: AgentState) -> AgentResult:
        """Execute workflow sequentially."""
        if self.current_step_index >= len(self.steps):
            # All steps completed
            self.status = AgentStatus.COMPLETED
            return AgentResult(
                status=AgentStatus.COMPLETED,
                message="All workflow steps completed successfully",
                data={"completed_steps": self.completed_steps},
                terminal=True
            )
        
        # Execute current step
        current_step = self.steps[self.current_step_index]
        agent = current_step.agent
        
        self.log("info", f"Executing step {self.current_step_index + 1}: {agent.name}")
        
        try:
            # Create pipeline for this agent
            pipeline = AgentPipeline(agent, logger=self._logger)
            
            # Override max iterations if specified
            if current_step.max_iterations:
                agent.config.max_iterations = current_step.max_iterations
            
            # Run the agent pipeline
            step_context = self._build_step_context(state)
            results = pipeline.run(step_context)
            
            # Store step results
            self.step_results[agent.name] = results
            
            # Check if step succeeded
            pipeline_status = results.get("pipeline_status", {})
            step_successful = pipeline_status.get("final_status") == "completed"
            
            if step_successful:
                self.completed_steps.append(agent.name)
                self.current_step_index += 1
                
                # Merge agent's final state into composite state
                agent_state = results.get("final_state", {})
                if agent_state and "data" in agent_state:
                    state.update({f"{agent.name}_result": agent_state["data"]})
                
                message = f"Step {agent.name} completed successfully"
                
                # Check if this was the last step
                if self.current_step_index >= len(self.steps):
                    self.status = AgentStatus.COMPLETED
                    return AgentResult(
                        status=AgentStatus.COMPLETED,
                        message="All workflow steps completed",
                        data={"step_results": self.step_results},
                        terminal=True
                    )
                else:
                    return AgentResult(
                        status=AgentStatus.RUNNING,
                        message=message,
                        data={"current_step": self.current_step_index, "step_result": results},
                        terminal=False
                    )
            else:
                # Step failed
                self.failed_steps.append(agent.name)
                error_msg = f"Step {agent.name} failed"
                
                return AgentResult(
                    status=AgentStatus.FAILED,
                    message=error_msg,
                    data={"failed_step": agent.name, "step_result": results},
                    terminal=True,
                    error=error_msg
                )
        
        except Exception as e:
            self.failed_steps.append(agent.name)
            error_msg = f"Step {agent.name} failed with exception: {e}"
            self.log("error", error_msg)
            
            return AgentResult(
                status=AgentStatus.FAILED,
                message=error_msg,
                data={"failed_step": agent.name},
                terminal=True,
                error=str(e)
            )
    
    def _execute_conditional(self, state: AgentState) -> AgentResult:
        """Execute workflow with conditional branching."""
        # Find next step to execute based on conditions
        next_step = None
        
        for step in self.steps:
            if step.step_id in self.completed_steps:
                continue
            
            # Check if condition is met (or no condition)
            if step.condition is None or step.condition(state):
                next_step = step
                break
        
        if next_step is None:
            # No more steps to execute
            self.status = AgentStatus.COMPLETED
            return AgentResult(
                status=AgentStatus.COMPLETED,
                message="Conditional workflow completed",
                data={"completed_steps": self.completed_steps},
                terminal=True
            )
        
        # Execute the step
        self.log("info", f"Executing conditional step: {next_step.agent.name}")
        return self._execute_single_step(next_step, state)
    
    def _execute_loop(self, state: AgentState) -> AgentResult:
        """Execute workflow in a loop until condition is met."""
        # This is a simplified loop implementation
        # In practice, you might want more sophisticated loop control
        
        if not self.steps:
            return AgentResult(
                status=AgentStatus.COMPLETED,
                message="No steps to execute in loop",
                data={},
                terminal=True
            )
        
        # Execute steps in order, looping back to the beginning
        step_index = self.current_step_index % len(self.steps)
        current_step = self.steps[step_index]
        
        result = self._execute_single_step(current_step, state)
        
        # Advance to next step
        self.current_step_index = (self.current_step_index + 1) % len(self.steps)
        
        return result
    
    def _execute_single_step(self, step: AgentStep, state: AgentState) -> AgentResult:
        """Execute a single step."""
        agent = step.agent
        
        try:
            # Create pipeline for this agent
            pipeline = AgentPipeline(agent, logger=self._logger)
            
            # Override max iterations if specified
            if step.max_iterations:
                agent.config.max_iterations = step.max_iterations
            
            # Run the agent pipeline
            step_context = self._build_step_context(state)
            results = pipeline.run(step_context)
            
            # Store step results
            self.step_results[agent.name] = results
            
            # Process results
            pipeline_status = results.get("pipeline_status", {})
            step_successful = pipeline_status.get("final_status") == "completed"
            
            if step_successful:
                self.completed_steps.append(agent.name)
                
                # Merge results into state
                agent_state = results.get("final_state", {})
                if agent_state and "data" in agent_state:
                    state.update({f"{agent.name}_result": agent_state["data"]})
                
                return AgentResult(
                    status=AgentStatus.RUNNING,
                    message=f"Step {agent.name} completed",
                    data={"step_result": results},
                    terminal=False
                )
            else:
                self.failed_steps.append(agent.name)
                return AgentResult(
                    status=AgentStatus.FAILED,
                    message=f"Step {agent.name} failed",
                    data={"failed_step": agent.name, "step_result": results},
                    terminal=True
                )
        
        except Exception as e:
            self.failed_steps.append(agent.name)
            return AgentResult(
                status=AgentStatus.FAILED,
                message=f"Step {agent.name} failed: {e}",
                data={"failed_step": agent.name},
                terminal=True,
                error=str(e)
            )
    
    def _build_step_context(self, state: AgentState) -> Dict[str, Any]:
        """Build context for a step execution."""
        context = {
            "composite_state": state.data,
            "completed_steps": self.completed_steps,
            "step_results": self.step_results,
            "workflow_mode": self.workflow_mode.value
        }
        return context
    
    def check_terminal_condition(self, state: AgentState) -> bool:
        """Check if the composite workflow should terminate."""
        if self.workflow_mode == WorkflowMode.SEQUENTIAL:
            return self.current_step_index >= len(self.steps)
        elif self.workflow_mode == WorkflowMode.CONDITIONAL:
            # Check if any steps are left to execute
            remaining_steps = [
                step for step in self.steps 
                if step.step_id not in self.completed_steps and step.step_id not in self.failed_steps
            ]
            return len(remaining_steps) == 0
        else:
            # For loop mode, rely on iteration count or custom conditions
            return False
    
    def finalize(self, state: AgentState) -> Dict[str, Any]:
        """Finalize the composite workflow."""
        final_results = super().finalize(state)
        
        final_results.update({
            "workflow_mode": self.workflow_mode.value,
            "total_steps": len(self.steps),
            "completed_steps": len(self.completed_steps),
            "failed_steps": len(self.failed_steps),
            "step_names": [step.agent.name for step in self.steps],
            "step_results": self.step_results
        })
        
        return final_results