"""Settings Manager for agentic pipeline framework."""

import json
import os
from typing import Dict, Any, Optional
from pathlib import Path


class SettingsManager:
    """Manages configuration settings from JSON file and environment variables."""
    
    def __init__(self, settings_file: Optional[str] = None):
        """Initialize settings manager with optional custom settings file."""
        if settings_file:
            self.settings_file = Path(settings_file)
        else:
            # Default to settings.json in same directory as this file
            config_dir = Path(__file__).parent
            self.settings_file = config_dir / "settings.json"
        
        self.settings = self._load_settings()
    
    def _load_settings(self) -> Dict[str, Any]:
        """Load settings from JSON file with fallback defaults."""
        default_settings = {
            "api_keys": {
                "openai_api_key": "",
                "claude_code_api_key": "",
                "azure_devops_pat": ""
            },
            "tdd_agent": {
                "max_reflection_retries": 3,
                "enable_reflection": True,
                "git_diff_min_size": 50
            },
            "planning_agent": {
                "max_iterations": 1,
                "include_integration_tests": True,
                "test_categories": ["service", "integration", "end-to-end"]
            },
            "azure_devops": {
                "default_organization": "",
                "default_project": "",
                "default_area_path": "",
                "default_iteration_path": ""
            },
            "logging": {
                "level": "info",
                "enable_file_logging": False,
                "log_file_path": "./logs/agentic_pipeline.log"
            }
        }
        
        if not self.settings_file.exists():
            # Create default settings file
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.settings_file, 'w') as f:
                json.dump(default_settings, f, indent=2)
            return default_settings
        
        try:
            with open(self.settings_file, 'r') as f:
                loaded_settings = json.load(f)
            
            # Merge with defaults to ensure all keys exist
            return self._merge_settings(default_settings, loaded_settings)
            
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load settings from {self.settings_file}: {e}")
            print("Using default settings")
            return default_settings
    
    def _merge_settings(self, defaults: Dict[str, Any], loaded: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge loaded settings with defaults."""
        result = defaults.copy()
        
        for key, value in loaded.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_settings(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get a setting value by dot-notation key path.
        
        Args:
            key_path: Dot-separated path like 'api_keys.openai_api_key'
            default: Default value if key not found
            
        Returns:
            Setting value or default
        """
        keys = key_path.split('.')
        current = self.settings
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        
        return current
    
    def get_api_key(self, service: str) -> Optional[str]:
        """
        Get API key for a service with environment variable fallback.
        
        Args:
            service: Service name ('openai', 'claude_code', 'azure_devops')
            
        Returns:
            API key or None if not found
        """
        # Map service names to setting keys and environment variables
        service_map = {
            'openai': ('api_keys.openai_api_key', 'OPENAI_API_KEY'),
            'claude_code': ('api_keys.claude_code_api_key', 'CLAUDE_CODE_API_KEY'),
            'azure_devops': ('api_keys.azure_devops_pat', 'AZURE_DEVOPS_PAT')
        }
        
        if service not in service_map:
            return None
        
        setting_key, env_var = service_map[service]
        
        # First try settings file
        api_key = self.get(setting_key)
        if api_key and api_key.strip():
            return api_key.strip()
        
        # Fallback to environment variable
        env_key = os.getenv(env_var)
        if env_key and env_key.strip():
            return env_key.strip()
        
        return None
    
    def set(self, key_path: str, value: Any) -> None:
        """
        Set a setting value by dot-notation key path.
        
        Args:
            key_path: Dot-separated path like 'api_keys.openai_api_key'
            value: Value to set
        """
        keys = key_path.split('.')
        current = self.settings
        
        # Navigate to parent of target key
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        # Set the final key
        current[keys[-1]] = value
    
    def save(self) -> bool:
        """
        Save current settings to file.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
            return True
        except IOError as e:
            print(f"Error saving settings to {self.settings_file}: {e}")
            return False
    
    def get_tdd_config(self) -> Dict[str, Any]:
        """Get TDD agent configuration."""
        return self.get('tdd_agent', {})
    
    def get_planning_config(self) -> Dict[str, Any]:
        """Get Planning agent configuration."""
        return self.get('planning_agent', {})
    
    def get_azure_config(self) -> Dict[str, Any]:
        """Get Azure DevOps configuration."""
        return self.get('azure_devops', {})


# Global settings instance
_global_settings = None

def get_settings(settings_file: Optional[str] = None) -> SettingsManager:
    """Get global settings instance."""
    global _global_settings
    if _global_settings is None or settings_file:
        _global_settings = SettingsManager(settings_file)
    return _global_settings