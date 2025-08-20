"""Command builder for Claude commands."""

import json
from typing import List

from .config import Configuration


class ClaudeCommandBuilder:
    """Handles building Claude command arguments."""
    
    def __init__(self, config: Configuration):
        self.config = config
    
    def build_initial_command(self, ticket_number: str) -> List[str]:
        """Build the initial Claude command for TDD work."""
        return [
            'claude',
            '--output-format', 'stream-json',
            '--verbose',
            '--dangerously-skip-permissions',
            '-p', f'/tdd-devops {ticket_number}'
        ]
    
    def build_followup_command(self, ticket_number: str) -> List[str]:  # ticket_number unused but kept for interface consistency
        """Build a follow-up command to get JSON status."""
        json_instructions = (
            f'Provide a JSON status update in this exact format: '
            f'{json.dumps(self.config.response_schema)}. Include user_message with '
            f'current status and complete (boolean) indicating if the ticket is fully done.'
        )
        return [
            'claude',
            '--output-format', 'json',
            '--dangerously-skip-permissions',
            '--continue',
            '--append-system-prompt', json_instructions,
            '-p', 'Provide a JSON status update on the TDD work completed.'
        ]