#!/usr/bin/env python3

"""Test script for the refactored TDD DevOps Loop."""

import sys
import os
from datetime import datetime

# Add the refactored script to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main_refactored import (
    Configuration, Logger, UsageLimitParser, ClaudeExecutor, TDDDevOpsLoop
)


def test_logger():
    """Test the Logger class."""
    print("=== Testing Logger ===")
    logger = Logger()
    
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    logger.success("This is a success message")
    logger.assistant_message("This is an assistant message")
    logger.iteration_header(1)
    
    # Test tool actions
    logger.tool_action('Read', '/path/to/file.py')
    logger.tool_action('Bash', 'ls -la')
    logger.tool_action('Unknown', 'some action')
    
    print("✅ Logger tests completed\n")


def test_usage_limit_parser():
    """Test the UsageLimitParser class."""
    print("=== Testing UsageLimitParser ===")
    parser = UsageLimitParser()
    
    test_messages = [
        "5-hour limit reached ∙ resets 11am",
        "usage limit reached|1672531200",
        "5-hour limit reached • resets 2pm",
        "Usage limit reached, resets 6am",
        "random message with no limit info",
        "💭 5-hour limit reached ∙ resets 11am",
    ]
    
    for msg in test_messages:
        epoch = parser.parse_usage_limit_epoch(msg)
        if epoch:
            dt = datetime.fromtimestamp(epoch)
            print(f"  ✅ '{msg[:30]}...' -> {dt.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print(f"  ❌ '{msg[:30]}...' -> NO MATCH")
    
    # Test time parsing
    print("\nTesting time parsing:")
    for time_str in ["11am", "2pm", "12am", "9pm"]:
        epoch = parser.parse_time_to_next_occurrence(time_str)
        if epoch:
            dt = datetime.fromtimestamp(epoch)
            print(f"  {time_str} -> {dt.strftime('%Y-%m-%d %H:%M:%S')}")
    
    print("✅ UsageLimitParser tests completed\n")


def test_configuration():
    """Test the Configuration class."""
    print("=== Testing Configuration ===")
    
    # Test default configuration
    config = Configuration()
    print(f"Max iterations: {config.max_iterations}")
    print(f"Response schema keys: {list(config.response_schema['properties'].keys())}")
    
    # Test custom configuration
    custom_config = Configuration(max_iterations=25)
    print(f"Custom max iterations: {custom_config.max_iterations}")
    
    print("✅ Configuration tests completed\n")


def test_claude_executor():
    """Test the ClaudeExecutor class (without actually running Claude)."""
    print("=== Testing ClaudeExecutor ===")
    
    config = Configuration()
    logger = Logger()
    parser = UsageLimitParser()
    executor = ClaudeExecutor(config, logger, parser)
    
    # Test command building
    main_cmd = executor.build_claude_command("TICKET-123")
    followup_cmd = executor.build_claude_command("TICKET-123", is_followup=True)
    
    print(f"Main command length: {len(main_cmd)} args")
    print(f"Followup command length: {len(followup_cmd)} args")
    print(f"Main command contains 'stream-json': {'stream-json' in main_cmd}")
    print(f"Followup command contains 'json': {'json' in followup_cmd}")
    
    # Test JSON extraction
    markdown_with_json = '''
    Here is some text.
    
    ```json
    {
        "user_message": "Test message",
        "complete": false
    }
    ```
    
    More text here.
    '''
    
    extracted = executor.extract_json_from_markdown(markdown_with_json)
    if extracted:
        print(f"✅ Extracted JSON: {extracted}")
    else:
        print("❌ Failed to extract JSON")
    
    print("✅ ClaudeExecutor tests completed\n")


def test_tdd_devops_loop():
    """Test the TDDDevOpsLoop class (initialization only)."""
    print("=== Testing TDDDevOpsLoop ===")
    
    # Test with default config
    loop = TDDDevOpsLoop()
    print(f"Default max iterations: {loop.config.max_iterations}")
    
    # Test with custom config
    custom_config = Configuration(max_iterations=10)
    custom_loop = TDDDevOpsLoop(custom_config)
    print(f"Custom max iterations: {custom_loop.config.max_iterations}")
    
    print("✅ TDDDevOpsLoop tests completed\n")


def main():
    """Run all tests."""
    print("=== Testing Refactored TDD DevOps Loop ===\n")
    
    test_configuration()
    test_logger()
    test_usage_limit_parser()
    test_claude_executor()
    test_tdd_devops_loop()
    
    print("=== All Tests Completed ===")


if __name__ == "__main__":
    main()