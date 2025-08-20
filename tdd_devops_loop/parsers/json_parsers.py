"""JSON parsing components implementing Chain of Responsibility pattern."""

import json
import re
from typing import Optional, Dict, Any

from ..core.interfaces import JsonParser


class DirectJsonParser(JsonParser):
    """Attempts to parse text directly as JSON."""
    
    def try_parse(self, text: str) -> Optional[Dict[str, Any]]:
        try:
            result = json.loads(text.strip())
            if (isinstance(result, dict) and 
                'user_message' in result and 
                'complete' in result):
                return result
        except json.JSONDecodeError:
            pass
        return None


class MarkdownJsonParser(JsonParser):
    """Extracts JSON from markdown code blocks."""
    
    def try_parse(self, text: str) -> Optional[Dict[str, Any]]:
        patterns = [
            r'```json\s*\n(.*?)\n```',  # Standard ```json block
            r'```json(.*?)```',          # Without newlines
            r'```\s*\n(\{.*?\})\s*\n```', # Generic code block with JSON
        ]
        
        for pattern in patterns:
            json_blocks = re.findall(pattern, text, re.DOTALL)
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


class WrappedResultParser(JsonParser):
    """Handles Claude Code result wrapper with nested content."""
    
    def try_parse(self, text: str) -> Optional[Dict[str, Any]]:
        try:
            outer_result = json.loads(text.strip())
            
            if isinstance(outer_result, dict) and 'result' in outer_result:
                nested_result = outer_result['result']
                
                # Try markdown extraction first
                markdown_parser = MarkdownJsonParser()
                extracted = markdown_parser.try_parse(nested_result)
                if extracted:
                    return extracted
                
                # Try direct parsing of nested result
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
        return None


class JsonParsingChain:
    """Chain of responsibility for JSON parsing strategies."""
    
    def __init__(self):
        self.parsers = [
            DirectJsonParser(),
            WrappedResultParser(),
            MarkdownJsonParser()
        ]
    
    def parse(self, text: str) -> Optional[Dict[str, Any]]:
        """Try each parser in sequence until one succeeds."""
        for parser in self.parsers:
            result = parser.try_parse(text)
            if result:
                return result
        return None