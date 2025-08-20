#!/usr/bin/env python3

"""
TDD DevOps Loop - Refactored with clean class architecture.

This module provides a clean, maintainable implementation of the TDD DevOps loop
using object-oriented design principles and separation of concerns.
"""

import subprocess
import os
import json
import sys
import re
import time
import math
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass


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


class Logger:
    """Handles timestamped console output with consistent formatting."""
    
    @staticmethod
    def get_timestamp() -> str:
        """Get current timestamp for logging."""
        return datetime.now().strftime("%H:%M:%S")
    
    def info(self, message: str) -> None:
        """Log an info message with timestamp."""
        timestamp = self.get_timestamp()
        print(f"[{timestamp}] {message}")
    
    def warning(self, message: str) -> None:
        """Log a warning message with timestamp."""
        timestamp = self.get_timestamp()
        print(f"[{timestamp}] ⚠️  {message}")
    
    def error(self, message: str) -> None:
        """Log an error message with timestamp."""
        timestamp = self.get_timestamp()
        print(f"[{timestamp}] ❌ {message}")
    
    def success(self, message: str) -> None:
        """Log a success message with timestamp."""
        timestamp = self.get_timestamp()
        print(f"[{timestamp}] ✅ {message}")
    
    def tool_action(self, tool_name: str, action_description: str) -> None:
        """Log tool usage with appropriate emoji and timestamp."""
        timestamp = self.get_timestamp()
        
        emoji_map = {
            'Read': '📖',
            'Edit': '✏️',
            'Write': '📝',
            'Bash': '🖥️',
            'Glob': '🔍',
            'Grep': '🔎',
            'TodoWrite': '📋'
        }
        
        emoji = emoji_map.get(tool_name, '🔧')
        print(f"\n[{timestamp}] {emoji} {tool_name}: {action_description}")
    
    def assistant_message(self, text: str) -> None:
        """Log assistant text output."""
        timestamp = self.get_timestamp()
        print(f"\n[{timestamp}] 💭 {text}")
    
    def iteration_header(self, iteration: int) -> None:
        """Log iteration header."""
        timestamp = self.get_timestamp()
        print(f"\n=== TDD DevOps Loop - Iteration {iteration} === [{timestamp}]")
    
    def session_info(self, session_data: Dict[str, Any]) -> None:
        """Log session initialization information."""
        print("=" * 60)
        print(f"🚀 Session started (ID: {session_data.get('session_id', 'unknown')[:8]}...)")
        print(f"📁 Working directory: {session_data.get('cwd', 'unknown')}")
        print(f"🤖 Model: {session_data.get('model', 'unknown')}")
        print(f"🔧 Tools available: {len(session_data.get('tools', []))}")
        print("=" * 60)


class UsageLimitParser:
    """Handles parsing of Claude usage limit messages and time calculations."""
    
    @staticmethod
    def parse_time_to_next_occurrence(time_str: str) -> Optional[int]:
        """Parse time like '11am' or '2pm' and return epoch of next occurrence."""
        match = re.match(r'(\d{1,2})(am|pm)', time_str.lower())
        if not match:
            return None
        
        hour = int(match.group(1))
        is_pm = match.group(2) == 'pm'
        
        # Convert to 24-hour format
        if is_pm and hour != 12:
            hour += 12
        elif not is_pm and hour == 12:
            hour = 0
        
        # Get current time and target time
        now = datetime.now()
        target_time = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        
        # If target time has already passed today, move to tomorrow
        if target_time <= now:
            target_time = target_time.replace(day=target_time.day + 1)
        
        return int(target_time.timestamp())
    
    def parse_usage_limit_epoch(self, text: str) -> Optional[int]:
        """Parse usage limit messages and return epoch timestamp of reset time."""
        # Try original format first: "usage limit reached|1234567890"
        match = re.search(r'usage limit reached\|(\d+)', text, re.I)
        if match:
            return int(match.group(1))
        
        # Try new format: "5-hour limit reached ∙ resets 11am"
        match = re.search(r'(?:5-hour limit reached|usage limit reached).*?resets\s+(\d{1,2}(?:am|pm))', text, re.I)
        if match:
            time_str = match.group(1)
            return self.parse_time_to_next_occurrence(time_str)
        
        # Try other variants
        match = re.search(r'limit reached.*?(\d{1,2}(?:am|pm))', text, re.I)
        if match:
            time_str = match.group(1)
            return self.parse_time_to_next_occurrence(time_str)
        
        return None
    
    def sleep_until_reset(self, epoch: Optional[int], logger: Logger) -> None:
        """Sleep until the usage limit resets."""
        if not epoch:
            return
        
        now = int(time.time())
        wait_seconds = max(0, int(epoch) - now)
        
        if wait_seconds > 0:
            reset_time = datetime.fromtimestamp(epoch, tz=timezone.utc).astimezone()
            reset_str = reset_time.strftime("%Y-%m-%d %H:%M:%S %Z")
            wait_minutes = math.ceil(wait_seconds / 60)
            
            logger.info(f"⏳ Claude limit hit. Sleeping {wait_minutes} min (until {reset_str}).")
            time.sleep(wait_seconds)


class ClaudeExecutor:
    """Handles Claude command execution and response parsing."""
    
    def __init__(self, config: Configuration, logger: Logger, usage_parser: UsageLimitParser):
        self.config = config
        self.logger = logger
        self.usage_parser = usage_parser
    
    def build_claude_command(self, ticket_number: str, is_followup: bool = False) -> List[str]:
        """Build the Claude command arguments."""
        if is_followup:
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
        else:
            return [
                'claude',
                '--output-format', 'stream-json',
                '--verbose',
                '--dangerously-skip-permissions',
                '-p', f'/tdd-devops {ticket_number}'
            ]
    
    def handle_tool_use(self, tool_name: str, tool_input: Dict[str, Any]) -> None:
        """Handle tool usage logging."""
        if tool_name == 'Read':
            self.logger.tool_action('Read', tool_input.get('file_path', ''))
        elif tool_name == 'Edit':
            self.logger.tool_action('Edit', tool_input.get('file_path', ''))
        elif tool_name == 'Write':
            self.logger.tool_action('Write', tool_input.get('file_path', ''))
        elif tool_name == 'Bash':
            cmd_preview = tool_input.get('command', '')[:80]
            self.logger.tool_action('Bash', f"Running: {cmd_preview}")
        elif tool_name == 'Glob':
            pattern = tool_input.get('pattern', '')
            path = tool_input.get('path', '.')
            self.logger.tool_action('Glob', f"Searching: {pattern} in {path}")
        elif tool_name == 'Grep':
            pattern = tool_input.get('pattern', '')
            path = tool_input.get('path', '.')
            self.logger.tool_action('Grep', f"Grepping: '{pattern}' in {path}")
        elif tool_name == 'TodoWrite':
            todos = tool_input.get('todos', [])
            self.logger.tool_action('TodoWrite', f"Todo List ({len(todos)} items)")
            for todo in todos:
                status_emoji = {
                    'pending': '⏳', 
                    'in_progress': '🔄', 
                    'completed': '✅'
                }.get(todo.get('status', 'pending'), '❓')
                content = todo.get('content', 'No description')[:60]
                if len(todo.get('content', '')) > 60:
                    content += '...'
                print(f"     {status_emoji} {content}")
        else:
            self.logger.tool_action(tool_name, "")
    
    def process_stream_line(self, line: str, collected_text: str) -> Tuple[Optional[Dict], Optional[int], str]:
        """Process a single line from the Claude stream output."""
        line = line.strip()
        if not line:
            return None, None, collected_text
        
        collected_text += line + "\n"
        
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            print(line)
            return None, None, collected_text
        
        if not (parsed and isinstance(parsed, dict)):
            print(line)
            return None, None, collected_text
        
        # Check if this is our target response schema
        if 'user_message' in parsed and 'complete' in parsed:
            return parsed, None, collected_text
        
        usage_limit_epoch = self._handle_event(parsed)
        return None, usage_limit_epoch, collected_text
    
    def _handle_event(self, parsed: Dict[str, Any]) -> Optional[int]:
        """Handle different types of events from Claude stream."""
        event_type = parsed.get('type')
        
        if event_type == 'system':
            self._handle_system_event(parsed)
        elif event_type == 'assistant':
            return self._handle_assistant_event(parsed)
        elif event_type == 'user':
            self._handle_user_event(parsed)
        elif event_type == 'result':
            return self._handle_result_event(parsed)
        else:
            self.logger.info(f"🔍 Unknown event: {event_type} - {parsed}")
        
        return None
    
    def _handle_system_event(self, parsed: Dict[str, Any]) -> None:
        """Handle system events."""
        if parsed.get('subtype') == 'init':
            self.logger.session_info(parsed)
    
    def _handle_assistant_event(self, parsed: Dict[str, Any]) -> Optional[int]:
        """Handle assistant events."""
        message = parsed.get('message', {})
        content = message.get('content', [])
        usage_limit_epoch = None
        
        for item in content:
            if item.get('type') == 'text':
                text = item.get('text', '').strip()
                if text:
                    self.logger.assistant_message(text)
                    epoch = self.usage_parser.parse_usage_limit_epoch(text)
                    if epoch:
                        usage_limit_epoch = epoch
            elif item.get('type') == 'tool_use':
                tool_name = item.get('name', 'unknown')
                tool_input = item.get('input', {})
                self.handle_tool_use(tool_name, tool_input)
        
        return usage_limit_epoch
    
    def _handle_user_event(self, parsed: Dict[str, Any]) -> None:
        """Handle user events."""
        message = parsed.get('message', {})
        content = message.get('content', [])
        
        for item in content:
            if item.get('type') == 'tool_result':
                result_content = item.get('content', '')
                if isinstance(result_content, str) and len(result_content) > 80:
                    self.logger.success(f"{result_content[:80]}...")
                    print("-" * 40)
                else:
                    self.logger.success("Completed")
                    print("-" * 40)
    
    def _handle_result_event(self, parsed: Dict[str, Any]) -> Optional[int]:
        """Handle result events."""
        result_str = parsed.get('result', '') or ''
        epoch = self.usage_parser.parse_usage_limit_epoch(result_str)
        if epoch:
            reset_time = datetime.fromtimestamp(epoch, tz=timezone.utc).astimezone()
            reset_str = reset_time.strftime("%Y-%m-%d %H:%M:%S %Z")
            self.logger.error(f"⛔️ Claude usage limit detected! Reset time: {reset_str} (epoch: {epoch})")
            self.logger.info(f"💬 Original message: {result_str}")
            return epoch
        else:
            self.logger.info(f"🔍 Result event: {parsed}")
            return None
    
    def extract_json_from_markdown(self, collected_text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from markdown code blocks."""
        # Try different patterns for JSON blocks
        patterns = [
            r'```json\s*\n(.*?)\n```',  # Standard ```json block
            r'```json(.*?)```',          # Without newlines
            r'```\s*\n(\{.*?\})\s*\n```', # Generic code block with JSON
        ]
        
        for pattern in patterns:
            json_blocks = re.findall(pattern, collected_text, re.DOTALL)
            for block in json_blocks:
                try:
                    json_obj = json.loads(block.strip())
                    if (isinstance(json_obj, dict) and 
                        'user_message' in json_obj and 
                        'complete' in json_obj):
                        return json_obj
                except json.JSONDecodeError:
                    continue
        return None
    
    def run_followup_status_check(self, ticket_number: str) -> Optional[Dict[str, Any]]:
        """Run a follow-up call to get JSON status from the previous TDD work."""
        self.logger.info("🔄 Getting status update...")
        
        cmd = self.build_claude_command(ticket_number, is_followup=True)
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            stdout, stderr = process.communicate()
            
            if stderr:
                print(f"STDERR: {stderr}", file=sys.stderr)
            
            # Try multiple parsing strategies
            result = self._parse_followup_response(stdout)
            if result:
                return result
            
            self.logger.warning(f"Failed to parse JSON from follow-up. Raw output: {stdout[:200]}...")
            return None
            
        except Exception as e:
            self.logger.error(f"Error in follow-up call: {e}")
            return None
    
    def _parse_followup_response(self, stdout: str) -> Optional[Dict[str, Any]]:
        """Parse the follow-up response using multiple strategies."""
        try:
            # First try to parse the outer JSON structure
            outer_result = json.loads(stdout.strip())
            
            # Check if it's our target schema directly
            if (isinstance(outer_result, dict) and 
                'user_message' in outer_result and 
                'complete' in outer_result):
                return outer_result
            
            # Check if it's a Claude Code result wrapper with nested content
            if isinstance(outer_result, dict) and 'result' in outer_result:
                nested_result = outer_result['result']
                
                # Try to extract JSON from the nested result (which might be markdown)
                extracted = self.extract_json_from_markdown(nested_result)
                if extracted:
                    return extracted
                
                # Try to parse the nested result directly as JSON
                try:
                    parsed_nested = json.loads(nested_result)
                    if (isinstance(parsed_nested, dict) and 
                        'user_message' in parsed_nested and 
                        'complete' in parsed_nested):
                        return parsed_nested
                except json.JSONDecodeError:
                    pass
            
        except json.JSONDecodeError:
            pass
        
        # Final fallback: try to extract from the entire output
        return self.extract_json_from_markdown(stdout)
    
    def run_single_iteration(self, ticket_number: str) -> Tuple[Optional[Dict], Optional[int], int]:
        """Run a single TDD iteration."""
        cmd = self.build_claude_command(ticket_number)
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1
            )
            
            collected_text = ""
            usage_limit_reset_epoch = None
            
            for line in process.stdout:
                _, epoch, collected_text = self.process_stream_line(line, collected_text)
                
                if epoch:
                    usage_limit_reset_epoch = max(usage_limit_reset_epoch or 0, epoch)
            
            process.wait()
            stderr_output = process.stderr.read()
            if stderr_output:
                print(f"STDERR: {stderr_output}", file=sys.stderr)
            
            # Get status via follow-up call
            final_result = self.run_followup_status_check(ticket_number)
            
            return final_result, usage_limit_reset_epoch, process.returncode
        
        except Exception as e:
            self.logger.error(f"Error running command: {e}")
            return None, None, 1


class TDDDevOpsLoop:
    """Main orchestrator for the TDD DevOps Loop."""
    
    def __init__(self, config: Configuration = None):
        self.config = config or Configuration()
        self.logger = Logger()
        self.usage_parser = UsageLimitParser()
        self.executor = ClaudeExecutor(self.config, self.logger, self.usage_parser)
    
    def print_iteration_result(self, final_result: Optional[Dict[str, Any]]) -> bool:
        """Print the result of an iteration and return whether the ticket is complete."""
        print("\n" + "=" * 60)
        
        if final_result:
            self.logger.info(f"📊 Status: {final_result.get('user_message', 'No message')}")
            is_complete = final_result.get('complete', False)
            
            if is_complete:
                self.logger.success("Ticket marked as complete. Exiting loop.")
            else:
                self.logger.info("🔄 Continuing to next iteration...")
            
            print("=" * 60)
            return is_complete
        else:
            self.logger.warning("No final JSON response found. Continuing...")
            print("=" * 60)
            return False
    
    def run(self, project_path: str, ticket_number: str) -> None:
        """Run the TDD DevOps loop."""
        os.chdir(project_path)
        
        iteration = 1
        
        while iteration <= self.config.max_iterations:
            self.logger.iteration_header(iteration)
            
            final_result, usage_limit_epoch, return_code = self.executor.run_single_iteration(ticket_number)
            
            is_complete = self.print_iteration_result(final_result)
            
            if return_code != 0:
                self.logger.warning(f"Process exited with code {return_code}")
            
            if usage_limit_epoch:
                self.usage_parser.sleep_until_reset(usage_limit_epoch, self.logger)
            
            if is_complete:
                break
            
            iteration += 1
        
        if iteration > self.config.max_iterations:
            self.logger.warning(f"🛑 Reached maximum iterations ({self.config.max_iterations}). Stopping.")


def main():
    """Entry point for the TDD DevOps Loop."""
    if len(sys.argv) != 3:
        print("Usage: python main_refactored.py <project_path> <ticket_number>")
        sys.exit(1)
    
    project_path = sys.argv[1]
    ticket_number = sys.argv[2]
    
    config = Configuration()
    loop = TDDDevOpsLoop(config)
    loop.run(project_path, ticket_number)


if __name__ == "__main__":
    main()