"""Configuration and data classes for TDD DevOps Loop."""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class Configuration:
    """Configuration settings for the TDD DevOps Loop."""
    
    response_schema: Dict[str, Any] = None
    max_iterations: int = 50
    
    def __post_init__(self):
        if self.response_schema is None:
            self.response_schema = {
                "type": "object",
                "properties": {
                    "user_message": {
                        "type": "string", 
                        "description": "Status message about the current loop iteration"
                    },
                    "complete": {
                        "type": "boolean", 
                        "description": "Whether the ticket is complete (true to stop loop, false to continue)"
                    }
                },
                "required": ["user_message", "complete"]
            }


@dataclass
class ExecutionContext:
    """Context object for passing dependencies around."""
    logger: 'Logger'
    usage_parser: 'UsageLimitParser'
    config: 'Configuration'