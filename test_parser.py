#!/usr/bin/env python3

"""Test script to verify the usage limit parsing logic works correctly."""

import sys
import os
from datetime import datetime, timezone

# Add the main script to path so we can import functions
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import parse_usage_limit_epoch, parse_time_to_next_occurrence

def test_parse_time_to_next_occurrence():
    """Test the time parsing helper function."""
    print("Testing parse_time_to_next_occurrence:")
    
    test_cases = ["11am", "2pm", "12pm", "12am", "6am", "9pm"]
    
    for time_str in test_cases:
        epoch = parse_time_to_next_occurrence(time_str)
        if epoch:
            dt = datetime.fromtimestamp(epoch)
            print(f"  {time_str:6} -> {dt.strftime('%Y-%m-%d %H:%M:%S')} (epoch: {epoch})")
        else:
            print(f"  {time_str:6} -> FAILED TO PARSE")
    print()

def test_parse_usage_limit_epoch():
    """Test the main usage limit parsing function."""
    print("Testing parse_usage_limit_epoch:")
    
    test_messages = [
        "5-hour limit reached ∙ resets 11am",
        "usage limit reached|1672531200",
        "5-hour limit reached • resets 2pm",
        "Usage limit reached, resets 6am",
        "limit reached at 9pm",
        "random message with no limit info",
        "💭 5-hour limit reached ∙ resets 11am",
    ]
    
    for msg in test_messages:
        epoch = parse_usage_limit_epoch(msg)
        if epoch:
            dt = datetime.fromtimestamp(epoch)
            print(f"  ✅ '{msg}' -> {dt.strftime('%Y-%m-%d %H:%M:%S')} (epoch: {epoch})")
        else:
            print(f"  ❌ '{msg}' -> NO MATCH")
    print()

if __name__ == "__main__":
    print("=== Testing TDD DevOps Loop Usage Limit Parser ===\n")
    test_parse_time_to_next_occurrence()
    test_parse_usage_limit_epoch()
    print("=== Test Complete ===")