"""Debug Agent - Performs iterative debugging workflows."""

import subprocess
import json
import re
from typing import Any, Dict, List

from ..core.agent import Agent, AgentResult, AgentStatus
from ..core.state import AgentState
from ..core.config import AgentConfig


class DebugAgent(Agent):
    """
    Debug Agent.
    
    Performs iterative debugging by analyzing errors, investigating root causes,
    and implementing fixes in a systematic manner.
    """
    
    # Agent metadata
    AGENT_TYPE = "debug"
    DESCRIPTION = "Performs iterative debugging with systematic error analysis"
    VERSION = "1.0.0"
    AUTHOR = "Agentic Pipeline Framework"
    TAGS = ["debug", "troubleshooting", "error-analysis"]
    CONFIG_SCHEMA = {
        "error_description": {
            "type": "string",
            "required": True,
            "description": "Description of the error or issue to debug"
        },
        "reproduction_steps": {
            "type": "array",
            "required": False,
            "description": "Steps to reproduce the issue"
        },
        "test_command": {
            "type": "string",
            "required": False,
            "description": "Command to run to test if issue is fixed"
        },
        "debug_mode": {
            "type": "string",
            "required": False,
            "description": "Debug approach: 'systematic', 'bisect', 'hypothesis'"
        }
    }
    
    def __init__(self, config: AgentConfig):
        """Initialize the Debug agent."""
        super().__init__(config)
        self.error_description = None
        self.reproduction_steps = []
        self.test_command = None
        self.debug_mode = "systematic"
        self.hypotheses = []
        self.tests_performed = []
        self.solutions_attempted = []
    
    def initialize(self, context: Dict[str, Any]) -> None:
        """Initialize the Debug agent."""
        self.log("info", "Initializing Debug Agent")
        
        # Extract configuration
        self.error_description = self.config.get_parameter("error_description")
        self.reproduction_steps = self.config.get_parameter("reproduction_steps", [])
        self.test_command = self.config.get_parameter("test_command")
        self.debug_mode = self.config.get_parameter("debug_mode", "systematic")
        
        if not self.error_description:
            raise ValueError("Debug Agent requires 'error_description' parameter")
        
        self.status = AgentStatus.RUNNING
        self.log("info", f"Debug Agent initialized for issue: {self.error_description}")
    
    def execute_iteration(self, state: AgentState) -> AgentResult:
        """Execute one debugging iteration."""
        iteration_num = state.iteration + 1
        self.log("info", f"Executing debug iteration {iteration_num}")
        
        try:
            # Build debugging prompt based on current state
            debug_prompt = self._build_debug_prompt(state, iteration_num)
            
            # Execute Claude command for debugging
            cmd = [
                'claude',
                '--output-format', 'json',
                '--dangerously-skip-permissions',
                '-p', debug_prompt
            ]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            stdout, stderr = process.communicate()
            
            if stderr:
                self.log("warning", f"Claude stderr: {stderr}")
            
            # Parse debugging response
            debug_result = self._parse_debug_response(stdout)
            
            # Process debugging results
            analysis = debug_result.get("analysis", "")
            hypothesis = debug_result.get("hypothesis", "")
            solution = debug_result.get("solution", "")
            confidence = debug_result.get("confidence", 0.5)
            
            # Record this iteration's work
            if hypothesis:
                self.hypotheses.append(hypothesis)
            
            # Test the solution if provided
            solution_works = False
            if solution:
                solution_works = self._test_solution(solution)
                self.solutions_attempted.append({
                    "solution": solution,
                    "works": solution_works,
                    "iteration": iteration_num
                })
            
            # Run test command if available
            test_passed = False
            if self.test_command:
                test_passed = self._run_test_command()
                self.tests_performed.append({
                    "command": self.test_command,
                    "passed": test_passed,
                    "iteration": iteration_num
                })
            
            # Determine if debugging is complete
            is_complete = (
                solution_works or 
                test_passed or 
                confidence >= 0.9 or
                iteration_num >= self.config.max_iterations
            )
            
            if is_complete and (solution_works or test_passed):
                self.status = AgentStatus.COMPLETED
                status_message = "Bug successfully fixed!"
            elif is_complete:
                self.status = AgentStatus.COMPLETED
                status_message = "Debugging completed (may require manual intervention)"
            else:
                status_message = f"Debugging in progress - investigating: {hypothesis[:100]}"
            
            iteration_data = {
                "analysis": analysis,
                "hypothesis": hypothesis,
                "solution": solution,
                "confidence": confidence,
                "solution_works": solution_works,
                "test_passed": test_passed,
                "debug_approach": debug_result.get("debug_approach", "")
            }
            
            return AgentResult(
                status=self.status,
                message=status_message,
                data=iteration_data,
                terminal=is_complete
            )
        
        except Exception as e:
            self.log("error", f"Debug iteration failed: {e}")
            return AgentResult(
                status=AgentStatus.FAILED,
                message=f"Debug iteration failed: {e}",
                data={},
                terminal=True,
                error=str(e)
            )
    
    def check_terminal_condition(self, state: AgentState) -> bool:
        """Check if debugging should terminate."""
        # Debug is complete if solution works or test passes
        latest_data = state.data
        if latest_data:
            return (latest_data.get("solution_works", False) or 
                   latest_data.get("test_passed", False))
        return False
    
    def _build_debug_prompt(self, state: AgentState, iteration: int) -> str:
        """Build the debugging prompt for Claude."""
        
        # Build context from previous iterations
        context = []
        if self.hypotheses:
            context.append(f"Previous hypotheses tested: {'; '.join(self.hypotheses[-3:])}")
        
        if self.solutions_attempted:
            recent_attempts = [
                f"Iteration {s['iteration']}: {s['solution'][:100]} ({'worked' if s['works'] else 'failed'})"
                for s in self.solutions_attempted[-2:]
            ]
            context.append(f"Recent solution attempts: {'; '.join(recent_attempts)}")
        
        context_str = "\n".join(context) if context else "This is the first debugging iteration."
        
        reproduction_str = ""
        if self.reproduction_steps:
            reproduction_str = f"Reproduction steps: {'; '.join(self.reproduction_steps)}"
        
        prompt = f"""
        DEBUG SESSION - Iteration {iteration}
        
        Error/Issue: {self.error_description}
        {reproduction_str}
        Debug Mode: {self.debug_mode}
        
        CONTEXT FROM PREVIOUS ITERATIONS:
        {context_str}
        
        Please analyze this issue systematically and provide a JSON response with:
        {{
            "analysis": "Detailed analysis of the current state and findings",
            "hypothesis": "Current hypothesis about the root cause",
            "solution": "Specific code changes or commands to try",
            "confidence": 0.8,
            "debug_approach": "Explain your debugging strategy for this iteration",
            "next_steps": "If this solution doesn't work, what to try next"
        }}
        
        Focus on:
        1. Understanding the root cause
        2. Providing testable solutions
        3. Building on previous iterations
        4. Being systematic in your approach
        """
        
        return prompt
    
    def _parse_debug_response(self, response: str) -> Dict[str, Any]:
        """Parse Claude's debugging response."""
        try:
            # Try to parse as JSON directly
            return json.loads(response.strip())
        except json.JSONDecodeError:
            # Try to extract JSON from the response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
            
            # Fallback to basic parsing
            return {
                "analysis": response[:500] + "..." if len(response) > 500 else response,
                "hypothesis": "Unable to parse structured response",
                "solution": "",
                "confidence": 0.3,
                "debug_approach": "Manual analysis required",
                "next_steps": "Review the full response manually"
            }
    
    def _test_solution(self, solution: str) -> bool:
        """Test if a proposed solution works."""
        self.log("info", f"Testing solution: {solution[:100]}...")
        
        # This is a simplified implementation
        # In practice, this would apply the solution and test it
        try:
            # For now, just execute the solution as a command
            if solution.startswith(('git ', 'python ', 'npm ', 'pip ')):
                result = subprocess.run(
                    solution.split(),
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                return result.returncode == 0
            else:
                # If it's not a command, assume it's code changes
                # In a real implementation, this would apply the changes
                # and run tests
                return False
        except Exception as e:
            self.log("warning", f"Solution test failed: {e}")
            return False
    
    def _run_test_command(self) -> bool:
        """Run the test command to check if issue is fixed."""
        try:
            self.log("info", f"Running test command: {self.test_command}")
            result = subprocess.run(
                self.test_command.split(),
                capture_output=True,
                text=True,
                timeout=60
            )
            passed = result.returncode == 0
            self.log("info", f"Test {'passed' if passed else 'failed'}")
            return passed
        except Exception as e:
            self.log("warning", f"Test command failed: {e}")
            return False
    
    def finalize(self, state: AgentState) -> Dict[str, Any]:
        """Finalize the debugging session."""
        final_results = super().finalize(state)
        
        # Determine final status
        successful_solutions = [s for s in self.solutions_attempted if s["works"]]
        successful_tests = [t for t in self.tests_performed if t["passed"]]
        
        final_results.update({
            "error_description": self.error_description,
            "debug_mode": self.debug_mode,
            "total_hypotheses": len(self.hypotheses),
            "total_solutions_attempted": len(self.solutions_attempted),
            "successful_solutions": len(successful_solutions),
            "total_tests_run": len(self.tests_performed),
            "successful_tests": len(successful_tests),
            "final_hypothesis": self.hypotheses[-1] if self.hypotheses else None,
            "debugging_successful": len(successful_solutions) > 0 or len(successful_tests) > 0
        })
        
        return final_results