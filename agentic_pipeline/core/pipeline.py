"""Agent pipeline orchestrator for the agentic pipeline framework."""

import os
import time
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime, timedelta

from .agent import Agent, AgentStatus, AgentResult
from .state import AgentState
from .config import AgentConfig, TerminalCondition, TerminalConditionType


class PipelineStatus:
    """Status tracking for pipeline execution."""
    
    def __init__(self):
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.current_iteration = 0
        self.total_iterations = 0
        self.agent_status = AgentStatus.INITIALIZING
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    @property
    def duration(self) -> Optional[timedelta]:
        """Get the duration of pipeline execution."""
        if self.started_at is None:
            return None
        end_time = self.completed_at or datetime.now()
        return end_time - self.started_at
    
    @property
    def is_running(self) -> bool:
        """Check if pipeline is currently running."""
        return (self.started_at is not None and 
                self.completed_at is None and 
                self.agent_status == AgentStatus.RUNNING)


class AgentPipeline:
    """
    Generic orchestrator for running agents with iteration control.
    
    Provides:
    - Agent lifecycle management
    - Terminal condition evaluation
    - State management
    - Error handling and recovery
    - Logging and monitoring
    - Hook system for extensions
    """
    
    def __init__(self, agent: Agent, logger=None):
        """
        Initialize the pipeline with an agent.
        
        Args:
            agent: The agent to execute
            logger: Optional logger for pipeline events
        """
        self.agent = agent
        self.logger = logger
        self.status = PipelineStatus()
        self.hooks = {
            'pre_pipeline': [],
            'post_pipeline': [],
            'pre_iteration': [],
            'post_iteration': [],
            'on_error': [],
            'on_terminal': []
        }
        
        # Set agent logger
        if logger:
            self.agent.set_logger(logger)
    
    def add_hook(self, hook_type: str, callback: Callable) -> None:
        """Add a hook callback for pipeline events."""
        if hook_type in self.hooks:
            self.hooks[hook_type].append(callback)
    
    def remove_hook(self, hook_type: str, callback: Callable) -> bool:
        """Remove a hook callback."""
        if hook_type in self.hooks and callback in self.hooks[hook_type]:
            self.hooks[hook_type].remove(callback)
            return True
        return False
    
    def _execute_hooks(self, hook_type: str, *args, **kwargs) -> None:
        """Execute all hooks of a given type."""
        for hook in self.hooks.get(hook_type, []):
            try:
                hook(*args, **kwargs)
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Hook {hook_type} failed: {e}")
    
    def _log(self, level: str, message: str) -> None:
        """Log a message if logger is available."""
        if self.logger:
            getattr(self.logger, level, self.logger.info)(message)
    
    def _evaluate_terminal_conditions(self, state: AgentState) -> bool:
        """
        Evaluate all terminal conditions for the agent.
        
        Args:
            state: Current agent state
            
        Returns:
            True if any terminal condition is met
        """
        config = self.agent.config
        
        for condition in config.terminal_conditions:
            if self._evaluate_single_condition(condition, state):
                self._log("info", f"Terminal condition met: {condition.description}")
                return True
        
        return False
    
    def _evaluate_single_condition(self, condition: TerminalCondition, state: AgentState) -> bool:
        """Evaluate a single terminal condition."""
        if condition.type == TerminalConditionType.MAX_ITERATIONS:
            return state.iteration >= condition.value
        
        elif condition.type == TerminalConditionType.SUCCESS_STATUS:
            return self.status.agent_status == AgentStatus.COMPLETED
        
        elif condition.type == TerminalConditionType.ERROR_STATUS:
            return self.status.agent_status == AgentStatus.FAILED
        
        elif condition.type == TerminalConditionType.TIMEOUT:
            if self.status.duration:
                return self.status.duration.total_seconds() >= condition.value
        
        elif condition.type == TerminalConditionType.STATE_CONDITION:
            # Evaluate state-based condition
            try:
                condition_func = condition.value
                if callable(condition_func):
                    return condition_func(state)
                elif isinstance(condition.value, dict):
                    # Simple key-value condition
                    for key, expected_value in condition.value.items():
                        if state.get(key) == expected_value:
                            return True
            except Exception as e:
                self._log("warning", f"Error evaluating state condition: {e}")
        
        elif condition.type == TerminalConditionType.CUSTOM_CONDITION:
            # Custom condition function
            try:
                condition_func = condition.value
                if callable(condition_func):
                    return condition_func(state, self.agent, self.status)
            except Exception as e:
                self._log("warning", f"Error evaluating custom condition: {e}")
        
        return False
    
    def _setup_environment(self, context: Dict[str, Any]) -> None:
        """Setup the execution environment."""
        config = self.agent.config
        
        # Set working directory
        if config.working_directory:
            try:
                os.chdir(config.working_directory)
                self._log("info", f"Changed working directory to: {config.working_directory}")
            except Exception as e:
                self._log("warning", f"Failed to change directory: {e}")
        
        # Set environment variables
        for key, value in config.environment_variables.items():
            os.environ[key] = value
            self._log("debug", f"Set environment variable: {key}")
    
    def run(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Run the agent pipeline.
        
        Args:
            context: Optional initialization context for the agent
            
        Returns:
            Dictionary containing final results and execution metadata
        """
        context = context or {}
        state = AgentState()
        
        try:
            # Initialize pipeline
            self.status.started_at = datetime.now()
            self.status.agent_status = AgentStatus.INITIALIZING
            self._log("info", f"Starting pipeline for agent: {self.agent.name}")
            
            # Execute pre-pipeline hooks
            self._execute_hooks('pre_pipeline', self.agent, state, context)
            
            # Setup environment
            self._setup_environment(context)
            
            # Initialize agent
            self.agent.initialize(context)
            self.status.agent_status = AgentStatus.RUNNING
            self._log("info", f"Agent {self.agent.name} initialized successfully")
            
            # Main execution loop
            while True:
                self.status.current_iteration = state.iteration
                self._log("info", f"Starting iteration {state.iteration + 1}")
                
                # Check terminal conditions before iteration
                if self._evaluate_terminal_conditions(state):
                    self._execute_hooks('on_terminal', self.agent, state, "Pre-iteration terminal condition")
                    break
                
                # Execute pre-iteration hooks
                self._execute_hooks('pre_iteration', self.agent, state)
                self.agent.pre_iteration_hook(state)
                
                try:
                    # Execute agent iteration
                    result = self.agent.execute_iteration(state)
                    self.agent.iteration_count += 1
                    
                    # Process result
                    if result.error:
                        self.status.errors.append(result.error)
                        self._log("error", f"Agent iteration failed: {result.error}")
                    
                    self._log("info", f"Iteration {state.iteration + 1} completed: {result.message}")
                    
                    # Update state
                    if result.data:
                        state.update(result.data)
                    state.advance_iteration(result.message)
                    
                    # Execute post-iteration hooks
                    self.agent.post_iteration_hook(state, result)
                    self._execute_hooks('post_iteration', self.agent, state, result)
                    
                    # Check if agent requested termination
                    if result.terminal:
                        self.status.agent_status = result.status
                        self._execute_hooks('on_terminal', self.agent, state, "Agent requested termination")
                        break
                    
                    # Check terminal conditions after iteration
                    if self._evaluate_terminal_conditions(state):
                        self._execute_hooks('on_terminal', self.agent, state, "Post-iteration terminal condition")
                        break
                
                except Exception as e:
                    # Handle agent execution error
                    self._log("error", f"Exception during agent execution: {e}")
                    error_result = self.agent.on_error(e, state)
                    
                    # Execute error hooks
                    self._execute_hooks('on_error', self.agent, state, e, error_result)
                    
                    if error_result.terminal:
                        self.status.agent_status = error_result.status
                        self.status.errors.append(str(e))
                        break
            
            # Finalize agent
            final_results = self.agent.finalize(state)
            self.status.completed_at = datetime.now()
            self.status.total_iterations = state.iteration
            
            if self.status.agent_status == AgentStatus.RUNNING:
                self.status.agent_status = AgentStatus.COMPLETED
            
            self._log("info", f"Pipeline completed for agent: {self.agent.name}")
            
            # Execute post-pipeline hooks
            self._execute_hooks('post_pipeline', self.agent, state, final_results)
            
            # Compile final results
            return {
                "agent_results": final_results,
                "pipeline_status": {
                    "started_at": self.status.started_at.isoformat(),
                    "completed_at": self.status.completed_at.isoformat(),
                    "duration_seconds": self.status.duration.total_seconds(),
                    "total_iterations": self.status.total_iterations,
                    "final_status": self.status.agent_status.value,
                    "errors": self.status.errors,
                    "warnings": self.status.warnings
                },
                "final_state": state.to_dict()
            }
        
        except Exception as e:
            # Handle pipeline-level error
            self.status.completed_at = datetime.now()
            self.status.agent_status = AgentStatus.FAILED
            self.status.errors.append(str(e))
            
            self._log("error", f"Pipeline failed: {e}")
            self._execute_hooks('on_error', self.agent, state, e, None)
            
            return {
                "agent_results": None,
                "pipeline_status": {
                    "started_at": self.status.started_at.isoformat() if self.status.started_at else None,
                    "completed_at": self.status.completed_at.isoformat(),
                    "duration_seconds": self.status.duration.total_seconds() if self.status.duration else 0,
                    "total_iterations": self.status.total_iterations,
                    "final_status": self.status.agent_status.value,
                    "errors": self.status.errors,
                    "warnings": self.status.warnings
                },
                "final_state": state.to_dict() if 'state' in locals() else None,
                "pipeline_error": str(e)
            }