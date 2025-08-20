"""Usage limit parsing utility for TDD DevOps Loop."""

import re
import time
import math
from datetime import datetime, timezone
from typing import Optional


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
    
    def sleep_until_reset(self, epoch: Optional[int], logger) -> None:
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