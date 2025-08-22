"""Response processing for Claude outputs."""

from typing import Optional, Dict, Any

from ..parsers.json_parsers import JsonParsingChain


class ResponseProcessor:
    """Handles processing and parsing of Claude responses."""
    
    def __init__(self, parsing_chain: JsonParsingChain, logger):
        self.parsing_chain = parsing_chain
        self.logger = logger
    
    def process_followup_response(self, stdout: str) -> Optional[Dict[str, Any]]:
        """Process the follow-up response using the parsing chain."""
        result = self.parsing_chain.parse(stdout)
        if not result:
            self.logger.warning(f"Failed to parse JSON from follow-up. Raw output: {stdout}")
        return result