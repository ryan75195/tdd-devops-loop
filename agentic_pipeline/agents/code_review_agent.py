"""Code Review Agent - Performs iterative code reviews."""

import subprocess
import json
from typing import Any, Dict

from ..core.agent import Agent, AgentResult, AgentStatus
from ..core.state import AgentState
from ..core.config import AgentConfig


class CodeReviewAgent(Agent):
    """
    Code Review Agent.
    
    Performs iterative code reviews with Claude Code integration,
    focusing on code quality, best practices, and improvement suggestions.
    """
    
    # Agent metadata
    AGENT_TYPE = "code_review"
    DESCRIPTION = "Performs iterative code reviews with improvement suggestions"
    VERSION = "1.0.0"
    AUTHOR = "Agentic Pipeline Framework"
    TAGS = ["review", "quality", "analysis"]
    CONFIG_SCHEMA = {
        "target_files": {
            "type": "array",
            "required": False,
            "description": "Specific files to review (optional)"
        },
        "review_criteria": {
            "type": "array",
            "required": False,
            "description": "Specific criteria to focus on"
        },
        "fix_issues": {
            "type": "boolean",
            "required": False,
            "description": "Whether to automatically fix found issues"
        }
    }
    
    def __init__(self, config: AgentConfig):
        """Initialize the Code Review agent."""
        super().__init__(config)
        self.target_files = None
        self.review_criteria = None
        self.fix_issues = False
        self.reviewed_files = []
        self.issues_found = []
    
    def initialize(self, context: Dict[str, Any]) -> None:
        """Initialize the Code Review agent."""
        self.log("info", "Initializing Code Review Agent")
        
        # Extract configuration
        self.target_files = self.config.get_parameter("target_files", [])
        self.review_criteria = self.config.get_parameter("review_criteria", [
            "code quality", "best practices", "performance", "security"
        ])
        self.fix_issues = self.config.get_parameter("fix_issues", False)
        
        self.status = AgentStatus.RUNNING
        self.log("info", f"Code Review Agent initialized with criteria: {self.review_criteria}")
    
    def execute_iteration(self, state: AgentState) -> AgentResult:
        """Execute one code review iteration."""
        iteration_num = state.iteration + 1
        self.log("info", f"Executing code review iteration {iteration_num}")
        
        try:
            # Build review prompt
            review_prompt = self._build_review_prompt(state)
            
            # Execute Claude command for code review
            cmd = [
                'claude',
                '--output-format', 'json',
                '--dangerously-skip-permissions',
                '-p', review_prompt
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
            
            # Parse response
            review_result = self._parse_review_response(stdout)
            
            # Process review results
            issues_found = review_result.get("issues_found", [])
            suggestions = review_result.get("suggestions", [])
            quality_score = review_result.get("quality_score", 0)
            
            self.issues_found.extend(issues_found)
            
            # Determine if review is complete
            is_complete = (
                len(issues_found) == 0 or 
                quality_score >= 8.0 or
                iteration_num >= self.config.max_iterations
            )
            
            if is_complete:
                self.status = AgentStatus.COMPLETED
                status_message = f"Code review completed. Quality score: {quality_score}"
            else:
                status_message = f"Found {len(issues_found)} issues to address"
            
            # Optionally fix issues
            if self.fix_issues and issues_found and not is_complete:
                self._attempt_fixes(issues_found)
            
            iteration_data = {
                "issues_found": issues_found,
                "suggestions": suggestions,
                "quality_score": quality_score,
                "files_reviewed": review_result.get("files_reviewed", []),
                "iteration_summary": review_result.get("summary", "")
            }
            
            return AgentResult(
                status=self.status,
                message=status_message,
                data=iteration_data,
                terminal=is_complete
            )
        
        except Exception as e:
            self.log("error", f"Code review iteration failed: {e}")
            return AgentResult(
                status=AgentStatus.FAILED,
                message=f"Code review failed: {e}",
                data={},
                terminal=True,
                error=str(e)
            )
    
    def check_terminal_condition(self, state: AgentState) -> bool:
        """Check if code review should terminate."""
        # Review is complete if no more issues or quality is high enough
        latest_data = state.data
        if latest_data:
            quality_score = latest_data.get("quality_score", 0)
            issues_count = len(latest_data.get("issues_found", []))
            return quality_score >= 8.0 or issues_count == 0
        return False
    
    def _build_review_prompt(self, state: AgentState) -> str:
        """Build the review prompt for Claude."""
        criteria_str = ", ".join(self.review_criteria)
        
        if self.target_files:
            files_str = ", ".join(self.target_files)
            file_instruction = f"Focus on these files: {files_str}"
        else:
            file_instruction = "Review all relevant code files in the project"
        
        prompt = f"""
        Perform a comprehensive code review focusing on: {criteria_str}
        
        {file_instruction}
        
        Please provide your response in JSON format with:
        {{
            "issues_found": [
                {{"file": "filename", "line": 123, "issue": "description", "severity": "high|medium|low"}}
            ],
            "suggestions": [
                {{"category": "performance", "suggestion": "description", "files": ["file1", "file2"]}}
            ],
            "quality_score": 7.5,
            "files_reviewed": ["file1.py", "file2.js"],
            "summary": "Overall review summary"
        }}
        
        Focus on identifying specific, actionable improvements.
        """
        
        return prompt
    
    def _parse_review_response(self, response: str) -> Dict[str, Any]:
        """Parse Claude's review response."""
        try:
            # Try to parse as JSON directly
            return json.loads(response.strip())
        except json.JSONDecodeError:
            # Try to extract JSON from the response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
            
            # Fallback to basic parsing
            return {
                "issues_found": [],
                "suggestions": [],
                "quality_score": 5.0,
                "files_reviewed": [],
                "summary": "Failed to parse detailed review results"
            }
    
    def _attempt_fixes(self, issues: list) -> None:
        """Attempt to automatically fix found issues."""
        self.log("info", f"Attempting to fix {len(issues)} issues")
        
        for issue in issues:
            if issue.get("severity") in ["high", "medium"]:
                fix_prompt = f"""
                Fix this code issue:
                File: {issue.get('file')}
                Line: {issue.get('line')}
                Issue: {issue.get('issue')}
                
                Please make the necessary changes to fix this issue.
                """
                
                try:
                    subprocess.run([
                        'claude',
                        '--dangerously-skip-permissions',
                        '-p', fix_prompt
                    ], check=True, capture_output=True)
                    
                    self.log("info", f"Fixed issue in {issue.get('file')}")
                except subprocess.CalledProcessError as e:
                    self.log("warning", f"Failed to fix issue in {issue.get('file')}: {e}")
    
    def finalize(self, state: AgentState) -> Dict[str, Any]:
        """Finalize the code review."""
        final_results = super().finalize(state)
        
        final_results.update({
            "total_issues_found": len(self.issues_found),
            "review_criteria": self.review_criteria,
            "fix_mode_enabled": self.fix_issues,
            "files_reviewed": list(set(self.reviewed_files))
        })
        
        return final_results