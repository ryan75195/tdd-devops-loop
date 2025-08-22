#!/usr/bin/env python3
"""Debug script to investigate GPT-5 API issues."""

import sys
from pathlib import Path
from openai import OpenAI

# Add config directory to path for imports
config_dir = Path(__file__).parent / "config"
sys.path.insert(0, str(config_dir))
from settings_manager import get_settings

def debug_gpt5_access():
    """Debug GPT-5 API access issues."""
    
    print("🔍 Debugging GPT-5 API Access...")
    
    # Get API key from settings
    settings = get_settings()
    api_key = settings.get_api_key('openai')
    
    if not api_key:
        print("❌ No OpenAI API key found in settings")
        return
    
    print(f"✅ API key found: {api_key[:10]}...")
    
    # Initialize OpenAI client
    client = OpenAI(api_key=api_key)
    
    # Test different API calls to understand the issue
    
    print("\n📡 Testing GPT-5 with chat.completions.create (corrected parameters):")
    try:
        response = client.chat.completions.create(
            model="gpt-5",
            messages=[{"role": "user", "content": "Hello"}],
            max_completion_tokens=10  # Fixed parameter
        )
        print("✅ chat.completions.create with GPT-5 succeeded")
        print(f"Response: {response.choices[0].message.content}")
    except Exception as e:
        print(f"❌ chat.completions.create with GPT-5 failed: {e}")
        print(f"Error type: {type(e).__name__}")
    
    print("\n📡 Testing GPT-5 with structured outputs:")
    try:
        response = client.chat.completions.create(
            model="gpt-5",
            messages=[
                {"role": "system", "content": "You must respond with valid JSON only."},
                {"role": "user", "content": "Respond with JSON: {\"message\": \"hello\", \"status\": \"success\"}"}
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "test_response",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "message": {"type": "string"},
                            "status": {"type": "string"}
                        },
                        "required": ["message", "status"],
                        "additionalProperties": False
                    }
                }
            },
            max_completion_tokens=50
        )
        print("✅ GPT-5 structured outputs succeeded")
        print(f"Raw response: '{response.choices[0].message.content}'")
        
        import json
        parsed = json.loads(response.choices[0].message.content)
        print(f"Parsed JSON: {parsed}")
        
    except Exception as e:
        print(f"❌ GPT-5 structured outputs failed: {e}")
        print(f"Error type: {type(e).__name__}")
    
    print("\n📡 Testing GPT-5 with responses.parse:")
    try:
        from pydantic import BaseModel
        
        class TestModel(BaseModel):
            message: str
        
        response = client.responses.parse(
            model="gpt-5",
            input=[{"role": "user", "content": "Say hello"}],
            text_format=TestModel,
            max_tokens=10
        )
        print("✅ responses.parse with GPT-5 succeeded")
        print(f"Response: {response.output_parsed}")
    except AttributeError as e:
        print(f"❌ responses.parse method not available: {e}")
        print("This suggests the OpenAI client version doesn't support this API yet")
    except Exception as e:
        print(f"❌ responses.parse with GPT-5 failed: {e}")
        print(f"Error type: {type(e).__name__}")
    
    print("\n📡 Testing GPT-4o for comparison:")
    try:
        response = client.chat.completions.create(
            model="gpt-4o-2024-08-06",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=10
        )
        print("✅ chat.completions.create with GPT-4o succeeded")
        print(f"Response: {response.choices[0].message.content}")
    except Exception as e:
        print(f"❌ chat.completions.create with GPT-4o failed: {e}")
    
    print(f"\n📊 OpenAI client version: {OpenAI.__version__ if hasattr(OpenAI, '__version__') else 'unknown'}")

if __name__ == "__main__":
    debug_gpt5_access()