import subprocess
import os
import json
import sys
import re
import time
import math
from datetime import datetime, timezone

def get_timestamp():
    """Get current timestamp for logging."""
    return datetime.now().strftime("%H:%M:%S")

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "user_message": {"type": "string", "description": "Status message about the current loop iteration"},
        "complete": {"type": "boolean", "description": "Whether the ticket is complete (true to stop loop, false to continue)"}
    },
    "required": ["user_message", "complete"]
}

def parse_time_to_next_occurrence(time_str):
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

def parse_usage_limit_epoch(text):
    """Parse usage limit messages and return epoch timestamp of reset time."""
    # Try original format first: "usage limit reached|1234567890"
    match = re.search(r'usage limit reached\|(\d+)', text, re.I)
    if match:
        return int(match.group(1))
    
    # Try new format: "5-hour limit reached ∙ resets 11am"
    match = re.search(r'(?:5-hour limit reached|usage limit reached).*?resets\s+(\d{1,2}(?:am|pm))', text, re.I)
    if match:
        time_str = match.group(1)
        return parse_time_to_next_occurrence(time_str)
    
    # Try other variants
    match = re.search(r'limit reached.*?(\d{1,2}(?:am|pm))', text, re.I)
    if match:
        time_str = match.group(1)
        return parse_time_to_next_occurrence(time_str)
    
    return None

def sleep_until_reset(epoch):
    if not epoch:
        return
    
    now = int(time.time())
    wait_seconds = max(0, int(epoch) - now)
    
    if wait_seconds > 0:
        reset_time = datetime.fromtimestamp(epoch, tz=timezone.utc).astimezone()
        reset_str = reset_time.strftime("%Y-%m-%d %H:%M:%S %Z")
        wait_minutes = math.ceil(wait_seconds / 60)
        
        timestamp = get_timestamp()
        print(f"\n[{timestamp}] ⏳ Claude limit hit. Sleeping {wait_minutes} min (until {reset_str}).")
        time.sleep(wait_seconds)
    
def build_claude_command(ticket_number, is_followup=False, schema=None):
    if is_followup:
        json_instructions = f'Provide a JSON status update in this exact format: {json.dumps(schema)}. Include user_message with current status and complete (boolean) indicating if the ticket is fully done.'
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
        
def handle_system_event(parsed):
    if parsed.get('subtype') == 'init':
        print("=" * 60)
        print(f"🚀 Session started (ID: {parsed.get('session_id', 'unknown')[:8]}...)")
        print(f"📁 Working directory: {parsed.get('cwd', 'unknown')}")
        print(f"🤖 Model: {parsed.get('model', 'unknown')}")
        print(f"🔧 Tools available: {len(parsed.get('tools', []))}")
        print("=" * 60)

def handle_tool_use(tool_name, tool_input):
    timestamp = get_timestamp()
    if tool_name == 'Read':
        print(f"\n[{timestamp}] 📖 Reading: {tool_input.get('file_path', '')}")
    elif tool_name == 'Edit':
        print(f"\n[{timestamp}] ✏️  Editing: {tool_input.get('file_path', '')}")
    elif tool_name == 'Write':
        print(f"\n[{timestamp}] 📝 Writing: {tool_input.get('file_path', '')}")
    elif tool_name == 'Bash':
        cmd_preview = tool_input.get('command', '')[:80]
        print(f"\n[{timestamp}] 🖥️  Running: {cmd_preview}")
    elif tool_name == 'Glob':
        print(f"\n[{timestamp}] 🔍 Searching: {tool_input.get('pattern', '')} in {tool_input.get('path', '.')}")
    elif tool_name == 'Grep':
        print(f"\n[{timestamp}] 🔎 Grepping: '{tool_input.get('pattern', '')}' in {tool_input.get('path', '.')}")
    elif tool_name == 'TodoWrite':
        todos = tool_input.get('todos', [])
        print(f"\n[{timestamp}] 📋 Todo List ({len(todos)} items):")
        for todo in todos:
            status_emoji = {'pending': '⏳', 'in_progress': '🔄', 'completed': '✅'}.get(todo.get('status', 'pending'), '❓')
            content = todo.get('content', 'No description')[:60] + ('...' if len(todo.get('content', '')) > 60 else '')
            print(f"     {status_emoji} {content}")
    else:
        print(f"\n[{timestamp}] 🔧 Tool: {tool_name}")

def handle_assistant_event(parsed):
    message = parsed.get('message', {})
    content = message.get('content', [])
    usage_limit_epoch = None
    
    for item in content:
        if item.get('type') == 'text':
            text = item.get('text', '').strip()
            if text:
                timestamp = get_timestamp()
                print(f"\n[{timestamp}] 💭 {text}")
                epoch = parse_usage_limit_epoch(text)
                if epoch:
                    usage_limit_epoch = epoch
        elif item.get('type') == 'tool_use':
            tool_name = item.get('name', 'unknown')
            tool_input = item.get('input', {})
            handle_tool_use(tool_name, tool_input)
    
    return usage_limit_epoch

def handle_user_event(parsed):
    message = parsed.get('message', {})
    content = message.get('content', [])
    
    for item in content:
        if item.get('type') == 'tool_result':
            result_content = item.get('content', '')
            if isinstance(result_content, str) and len(result_content) > 80:
                timestamp = get_timestamp()
                print(f"[{timestamp}] ✅ {result_content[:80]}...")
                print("-" * 40)
            else:
                timestamp = get_timestamp()
                print(f"[{timestamp}] ✅ Completed")
                print("-" * 40)

def handle_result_event(parsed):
    result_str = parsed.get('result', '') or ''
    epoch = parse_usage_limit_epoch(result_str)
    if epoch:
        reset_time = datetime.fromtimestamp(epoch, tz=timezone.utc).astimezone()
        reset_str = reset_time.strftime("%Y-%m-%d %H:%M:%S %Z")
        timestamp = get_timestamp()
        print(f"\n[{timestamp}] ⛔️ Claude usage limit detected! Reset time: {reset_str} (epoch: {epoch})")
        print(f"[{timestamp}] 💬 Original message: {result_str}")
        return epoch
    else:
        timestamp = get_timestamp()
        print(f"\n[{timestamp}] 🔍 Result event: {parsed}")
        return None

def process_stream_line(line, collected_text):
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
    
    if 'user_message' in parsed and 'complete' in parsed:
        return parsed, None, collected_text
    
    event_type = parsed.get('type')
    usage_limit_epoch = None
    
    if event_type == 'system':
        handle_system_event(parsed)
    elif event_type == 'assistant':
        usage_limit_epoch = handle_assistant_event(parsed)
    elif event_type == 'user':
        handle_user_event(parsed)
    elif event_type == 'result':
        usage_limit_epoch = handle_result_event(parsed)
    else:
        print(f"\n🔍 Unknown event: {event_type} - {parsed}")
    
    return None, usage_limit_epoch, collected_text

def extract_json_from_markdown(collected_text):
    json_blocks = re.findall(r'```json\s*\n(.*?)\n```', collected_text, re.DOTALL)
    for block in json_blocks:
        try:
            json_obj = json.loads(block.strip())
            if isinstance(json_obj, dict) and 'user_message' in json_obj and 'complete' in json_obj:
                return json_obj
        except json.JSONDecodeError:
            continue
    return None

def run_followup_status_check(ticket_number):
    """Run a follow-up call to get JSON status from the previous TDD work."""
    timestamp = get_timestamp()
    print(f"\n[{timestamp}] 🔄 Getting status update...")
    
    cmd = build_claude_command(ticket_number, is_followup=True, schema=RESPONSE_SCHEMA)
    
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
        
        try:
            # First try to parse the outer JSON structure
            outer_result = json.loads(stdout.strip())
            
            # Check if it's our target schema directly
            if isinstance(outer_result, dict) and 'user_message' in outer_result and 'complete' in outer_result:
                return outer_result
            
            # Check if it's a Claude Code result wrapper with nested content
            if isinstance(outer_result, dict) and 'result' in outer_result:
                nested_result = outer_result['result']
                # Try to extract JSON from the nested result (which might be markdown)
                extracted = extract_json_from_markdown(nested_result)
                if extracted:
                    return extracted
                
                # Try to parse the nested result directly as JSON
                try:
                    parsed_nested = json.loads(nested_result)
                    if isinstance(parsed_nested, dict) and 'user_message' in parsed_nested and 'complete' in parsed_nested:
                        return parsed_nested
                except json.JSONDecodeError:
                    pass
            
        except json.JSONDecodeError:
            pass
        
        # Final fallback: try to extract from the entire output
        result = extract_json_from_markdown(stdout)
        if result:
            return result
        
        timestamp = get_timestamp()
        print(f"[{timestamp}] ⚠️  Failed to parse JSON from follow-up. Raw output: {stdout[:200]}...")
        return None
        
    except Exception as e:
        timestamp = get_timestamp()
        print(f"[{timestamp}] ❌ Error in follow-up call: {e}")
        return None

def run_single_iteration(ticket_number):
    # First: Run the main TDD work
    cmd = build_claude_command(ticket_number)
    
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
            _, epoch, collected_text = process_stream_line(line, collected_text)
            
            if epoch:
                usage_limit_reset_epoch = max(usage_limit_reset_epoch or 0, epoch)
        
        process.wait()
        stderr_output = process.stderr.read()
        if stderr_output:
            print(f"STDERR: {stderr_output}", file=sys.stderr)
        
        # Second: Get status via follow-up call
        final_result = run_followup_status_check(ticket_number)
        
        return final_result, usage_limit_reset_epoch, process.returncode
    
    except Exception as e:
        timestamp = get_timestamp()
        print(f"[{timestamp}] ❌ Error running command: {e}")
        return None, None, 1

def print_iteration_result(final_result):
    print("\n" + "=" * 60)
    
    timestamp = get_timestamp()
    if final_result:
        print(f"[{timestamp}] 📊 Status: {final_result.get('user_message', 'No message')}")
        is_complete = final_result.get('complete', False)
        
        if is_complete:
            print(f"[{timestamp}] ✅ Ticket marked as complete. Exiting loop.")
        else:
            print(f"[{timestamp}] 🔄 Continuing to next iteration...")
        
        print("=" * 60)
        return is_complete
    else:
        print(f"[{timestamp}] ⚠️  Warning: No final JSON response found. Continuing...")
        print("=" * 60)
        return False

def run_tdd_devops_loop(project_path, ticket_number):
    os.chdir(project_path)
    
    iteration = 1
    max_iterations = 50
    
    while iteration <= max_iterations:
        timestamp = get_timestamp()
        print(f"\n=== TDD DevOps Loop - Iteration {iteration} === [{timestamp}]")
        
        final_result, usage_limit_epoch, return_code = run_single_iteration(ticket_number)
        
        is_complete = print_iteration_result(final_result)
        
        if return_code != 0:
            timestamp = get_timestamp()
            print(f"[{timestamp}] ⚠️  Warning: Process exited with code {return_code}")
        
        if usage_limit_epoch:
            sleep_until_reset(usage_limit_epoch)
        
        if is_complete:
            break
        
        iteration += 1
    
    if iteration > max_iterations:
        timestamp = get_timestamp()
        print(f"[{timestamp}] 🛑 Reached maximum iterations ({max_iterations}). Stopping.")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python main.py <project_path> <ticket_number>")
        sys.exit(1)
    project_path = sys.argv[1]
    ticket_number = sys.argv[2]
    run_tdd_devops_loop(project_path, ticket_number)
