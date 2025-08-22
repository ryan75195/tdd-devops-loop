"""OpenAI Reflection Service for TDD quality gate evaluation."""

import json
import os
from typing import Dict, Any, Optional, Literal
from openai import OpenAI
from pydantic import BaseModel

import sys
from pathlib import Path
# Add config directory to path for imports
config_dir = Path(__file__).parent.parent.parent / "config"
sys.path.insert(0, str(config_dir))
from settings_manager import get_settings


class ReflectionResult(BaseModel):
    """Structured output model for TDD reflection results."""
    status: Literal["continue", "retry"]  # Enum constraint for valid statuses
    feedback: str  # Detailed feedback about the implementation


class OpenAIReflectionService:
    """OpenAI service for evaluating TDD implementations with structured JSON output."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize OpenAI client with API key from settings or environment."""
        # Get API key from multiple sources (parameter > settings > environment)
        if api_key:
            self.api_key = api_key
        else:
            settings = get_settings()
            self.api_key = settings.get_api_key('openai')
        
        if not self.api_key:
            raise ValueError(
                "OpenAI API key not found. Please set it in:\n"
                "1. config/settings.json under 'api_keys.openai_api_key', or\n"
                "2. OPENAI_API_KEY environment variable, or\n"
                "3. Pass it as a parameter to OpenAIReflectionService()"
            )
        
        self.client = OpenAI(api_key=self.api_key)
        
        # Use GPT-5 for best reflection quality
        self.model = self._get_best_available_model()
    
    def _get_best_available_model(self) -> str:
        """Get GPT-5 model for structured outputs."""
        return "gpt-5"
    
    def evaluate_tdd_implementation(
        self, 
        git_diff: str, 
        task_details: Dict[str, Any],
        bdd_scenarios: str,
        iteration_context: str = ""
    ) -> ReflectionResult:
        """
        Evaluate TDD implementation using OpenAI with structured JSON output.
        
        Args:
            git_diff: Git diff from the TDD iteration
            task_details: Azure DevOps task details
            bdd_scenarios: BDD scenarios from task acceptance criteria  
            iteration_context: Additional context about current iteration
            
        Returns:
            ReflectionResult with status ("continue"|"retry") and feedback
        """
        try:
            system_prompt = self._build_system_prompt()
            user_prompt = self._build_evaluation_prompt(
                git_diff, task_details, bdd_scenarios, iteration_context
            )
            
            # Use GPT-5 Responses API (the proper way for GPT-5)
            combined_prompt = f"{system_prompt}\n\n{user_prompt}\n\nRespond with valid JSON only in this exact format: {{\"status\": \"continue\" or \"retry\", \"feedback\": \"detailed feedback here\"}}"
            
            response = self.client.responses.create(
                model=self.model,
                input=combined_prompt,
                reasoning={"effort": "high"},  # High reasoning for thorough code evaluation
                text={"verbosity": "medium"}   # Medium verbosity for detailed feedback
            )
            
            # Parse the structured response from GPT-5
            response_content = response.output_text
            
            # Extract JSON from the response (GPT-5 may include additional text)
            json_start = response_content.find('{')
            if json_start >= 0:
                # Find the matching closing brace
                brace_count = 0
                json_end = json_start
                for i, char in enumerate(response_content[json_start:], json_start):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            break
                
                if json_end > json_start:
                    json_text = response_content[json_start:json_end]
                    result_data = json.loads(json_text)
                    
                    return ReflectionResult(
                        status=result_data["status"],
                        feedback=result_data["feedback"]
                    )
            
            # If no JSON found, create response based on content analysis
            if "continue" in response_content.lower():
                status = "continue"
            else:
                status = "retry"
            
            return ReflectionResult(
                status=status,
                feedback=response_content
            )
            
        except Exception as e:
            # No fallbacks - let the error propagate so it can be properly addressed
            raise Exception(f"GPT-5 reflection analysis failed: {str(e)}")
    
    def _build_system_prompt(self) -> str:
        """Build the system prompt for TDD reflection evaluation."""
        return """You are an expert code reviewer specializing in Test-Driven Development (TDD) quality assessment.

Your role is to evaluate whether a TDD implementation properly fulfills the BDD scenarios and follows TDD best practices.

EVALUATION CRITERIA:
1. **Test Quality**: Are tests testing real implementation (not mocks of main functionality)?
2. **BDD Alignment**: Do the changes align with the Given/When/Then scenarios?
3. **TDD Methodology**: Does the code follow Red-Green-Refactor principles?
4. **Completeness**: Are the BDD scenarios adequately addressed by the changes?
5. **Code Quality**: Is the implementation clean, maintainable, and follows good practices?

DECISION RULES:
- Return "continue" if implementation adequately addresses the BDD scenarios and follows TDD practices
- Return "retry" if there are significant issues that need to be addressed before moving on

FEEDBACK GUIDELINES:
- Be specific about what was done well or what needs improvement
- Reference specific parts of the git diff when possible
- Provide actionable suggestions for improvement when status is "retry"
- Keep feedback concise but thorough (under 500 words)

You must respond with valid JSON containing exactly two fields: "status" and "feedback"."""

    def _build_evaluation_prompt(
        self, 
        git_diff: str, 
        task_details: Dict[str, Any], 
        bdd_scenarios: str,
        iteration_context: str
    ) -> str:
        """Build the evaluation prompt with all context."""
        task_id = task_details.get('id', 'Unknown')
        task_title = task_details.get('title', 'Unknown Task')
        
        return f"""Please evaluate this TDD implementation:

**TASK BEING IMPLEMENTED:**
Task {task_id}: {task_title}

**BDD SCENARIOS TO FULFILL:**
{bdd_scenarios}

**ITERATION CONTEXT:**
{iteration_context or "Initial TDD iteration"}

**GIT DIFF FROM TDD ITERATION:**
```diff
{git_diff}
```

**EVALUATION QUESTION:**
Based on the git diff above, does this TDD iteration adequately progress toward fulfilling the BDD scenarios? Should we continue to the next task or retry this implementation with improvements?

Analyze:
1. Are the tests actually testing real implementation (not just mocked behavior)?
2. Do the changes align with the BDD Given/When/Then scenarios?
3. Is this a reasonable TDD progression (Red-Green-Refactor)?
4. Are there any obvious issues that should be fixed before proceeding?

Return your evaluation as JSON with "status" ("continue" or "retry") and detailed "feedback"."""
    
    def test_connection(self) -> bool:
        """Test if OpenAI API connection is working."""
        try:
            self.client.responses.create(
                model=self.model,
                input="Hello",
                reasoning={"effort": "minimal"},
                text={"verbosity": "low"}
            )
            return True
        except Exception:
            return False