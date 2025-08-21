"""Planning Session Manager - Claude Code SDK integration for specification analysis."""

import json
from typing import Dict, Any, Optional

import anyio
from claude_code_sdk import query, ClaudeCodeOptions

from .config import Configuration


class PlanningSessionManager:
    """Claude Code SDK session manager for planning and specification analysis."""
    
    def __init__(self, config: Configuration, logger, usage_parser):
        self.config = config
        self.logger = logger
        self.usage_parser = usage_parser
        
        # Define the expected JSON schema for work breakdown
        self.work_breakdown_schema = {
            "product_backlog_item": {
                "title": "string - concise title for the main feature",
                "description": "string - problem statement and context",
                "acceptance_criteria": ["array of strings - high-level success criteria"],
                "priority": "integer 1-4 - priority level",
                "effort": "integer - story points or effort estimate"
            },
            "tasks": [
                {
                    "title": "string - test scenario title starting with 'Test: '",
                    "description": "string - brief description of what this test validates",
                    "given": ["array of strings - preconditions for the test"],
                    "when": ["array of strings - actions or events that trigger the test"],
                    "then": ["array of strings - expected outcomes and results"],
                    "requirements": ["array of strings - implementation requirements to satisfy this test"],
                    "effort": "integer - estimated hours or complexity"
                }
            ]
        }
    
    def analyze_specification(self, spec_content: str) -> Optional[Dict[str, Any]]:
        """Analyze specification content and return structured work breakdown."""
        try:
            # Run the async analysis in a sync context
            return anyio.run(self._async_analyze_specification, spec_content)
        except Exception as e:
            self.logger.error(f"Error analyzing specification: {e}")
            return None
    
    async def _async_analyze_specification(self, spec_content: str) -> Optional[Dict[str, Any]]:
        """Async implementation of specification analysis."""
        try:
            # Create the analysis prompt
            analysis_prompt = self._build_analysis_prompt(spec_content)
            
            # Configure SDK options for specification analysis
            options = ClaudeCodeOptions(
                system_prompt=self._build_system_prompt(),
                max_turns=1,  # Single analysis iteration
                permission_mode="bypassPermissions"
            )
            
            # Stream the analysis
            response_text = ""
            async for message in query(prompt=analysis_prompt, options=options):
                message_text = self._extract_message_text(message)
                if message_text:
                    response_text += message_text
                    self.logger.info(f"Analysis response: {message_text[:200]}...")
            
            # Parse the JSON response
            return self._parse_work_breakdown_response(response_text)
            
        except Exception as e:
            self.logger.error(f"Error in async specification analysis: {e}")
            return None
    
    def _build_system_prompt(self) -> str:
        """Build the system prompt for specification analysis."""
        return f"""You are an expert Business Analyst and Test Engineer specializing in converting natural language specifications into structured work items for agile development.

Your task is to analyze specification documents and create comprehensive work breakdowns that include:
1. A main Product Backlog Item (PBI) that captures the business problem and high-level solution
2. Detailed test case tasks using Behavior-Driven Development (BDD) format

CRITICAL: You must respond with ONLY valid JSON in exactly this format - no markdown formatting, no explanations, no extra text:

{json.dumps(self.work_breakdown_schema, indent=2)}

Your response should start with {{ and end with }}. Do not include any text before or after the JSON.

Guidelines:
- The PBI should focus on the business value and problem being solved
- Each task should be a specific test scenario that validates functionality
- Use Given/When/Then format for all test scenarios
- Focus on behavior and outcomes, not implementation details
- Include both happy path and error/edge case scenarios
- Ensure test scenarios cover all major requirements from the specification
- Provide realistic effort estimates (PBI: 1-13 points, Tasks: 1-8 hours)
- Make requirements specific enough to guide implementation without being prescriptive

Respond ONLY with the JSON structure - no additional text, explanations, or markdown formatting."""
    
    def _build_analysis_prompt(self, spec_content: str) -> str:
        """Build the prompt for analyzing the specification."""
        return f"""Please analyze this specification document and create a comprehensive work breakdown:

SPECIFICATION DOCUMENT:
{spec_content}

Create a Product Backlog Item and associated test case tasks that comprehensively cover all requirements in this specification. Focus on creating thorough BDD test scenarios that validate the functionality described.

Return valid JSON only - start your response with {{ and end with }}."""
    
    def _parse_work_breakdown_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Parse the work breakdown response from Claude."""
        try:
            # Clean up the response text
            response_text = response_text.strip()
            
            # Find JSON content (handle case where Claude adds extra text)
            json_start = response_text.find('{')
            if json_start >= 0:
                # Find the matching closing brace by counting braces
                brace_count = 0
                json_end = json_start
                for i, char in enumerate(response_text[json_start:], json_start):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            break
                
                if json_end > json_start:
                    json_text = response_text[json_start:json_end]
                    work_breakdown = json.loads(json_text)
                
                # Validate the structure
                if self._validate_work_breakdown(work_breakdown):
                    self.logger.info("Successfully parsed work breakdown from Claude analysis")
                    return work_breakdown
                else:
                    self.logger.warning("Work breakdown failed validation, using fallback structure")
                    return self._create_fallback_breakdown()
            else:
                self.logger.warning("No valid JSON found in Claude response, using fallback")
                return self._create_fallback_breakdown()
                
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parsing error: {e}")
            return self._create_fallback_breakdown()
        except Exception as e:
            self.logger.error(f"Error parsing work breakdown response: {e}")
            return self._create_fallback_breakdown()
    
    def _validate_work_breakdown(self, work_breakdown: Dict[str, Any]) -> bool:
        """Validate that the work breakdown has the expected structure."""
        try:
            # Check for required top-level keys
            if "product_backlog_item" not in work_breakdown or "tasks" not in work_breakdown:
                return False
            
            # Check PBI structure
            pbi = work_breakdown["product_backlog_item"]
            required_pbi_fields = ["title", "description", "acceptance_criteria"]
            if not all(field in pbi for field in required_pbi_fields):
                return False
            
            # Check tasks structure
            tasks = work_breakdown["tasks"]
            if not isinstance(tasks, list) or len(tasks) == 0:
                return False
            
            # Check first task structure
            task = tasks[0]
            required_task_fields = ["title", "given", "when", "then"]
            if not all(field in task for field in required_task_fields):
                return False
            
            return True
            
        except Exception:
            return False
    
    def _create_fallback_breakdown(self) -> Dict[str, Any]:
        """Create a basic fallback work breakdown if Claude analysis fails."""
        return {
            "product_backlog_item": {
                "title": "Implement specification requirements",
                "description": "Implement the functionality described in the provided specification document",
                "acceptance_criteria": [
                    "All functional requirements are implemented",
                    "All test scenarios pass",
                    "Code meets quality standards"
                ],
                "priority": 2,
                "effort": 8
            },
            "tasks": [
                {
                    "title": "Test: Core functionality works as expected",
                    "description": "Validate that the main functionality operates correctly",
                    "given": ["System is properly configured", "All dependencies are available"],
                    "when": ["User performs the primary action", "System processes the request"],
                    "then": ["Expected outcome is achieved", "System state is updated correctly"],
                    "requirements": ["Core business logic", "Data persistence", "User interface"],
                    "effort": 4
                },
                {
                    "title": "Test: Error conditions are handled gracefully",
                    "description": "Validate that error scenarios are properly managed",
                    "given": ["System is running", "Invalid input is provided"],
                    "when": ["User attempts the action", "System encounters the error"],
                    "then": ["Appropriate error message is shown", "System remains stable"],
                    "requirements": ["Error handling logic", "User feedback", "Logging"],
                    "effort": 3
                }
            ]
        }
    
    def _extract_message_text(self, message) -> str:
        """Extract text content from SDK message object."""
        try:
            # Handle different message types from SDK
            if hasattr(message, 'content'):
                # Message with content blocks
                text_parts = []
                for block in message.content:
                    if hasattr(block, 'text'):
                        text_parts.append(block.text)
                return ''.join(text_parts)
            elif hasattr(message, 'text'):
                # Direct text message
                return message.text
            elif isinstance(message, str):
                # String message
                return message
            elif hasattr(message, 'data') and isinstance(message.data, dict):
                # Handle system messages - log but don't return as text
                self.logger.info(f"System message: {message.__class__.__name__}({message.data})")
                return ""
            elif hasattr(message, 'result'):
                # Handle result messages
                self.logger.info(f"Result message: {message.__class__.__name__}(result='{message.result}')")
                return str(message.result)
            else:
                # Try to convert to string for debugging
                message_str = str(message)
                self.logger.info(f"Unknown message type: {message_str}")
                return message_str
        except Exception as e:
            # Fallback: try to stringify the entire message
            self.logger.info(f"Error extracting message text: {e}")
            return str(message)