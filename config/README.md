# Configuration Settings

This directory contains configuration files for the Agentic Pipeline Framework.

## Setup

1. **Copy the example settings file:**
   ```bash
   cp config/settings.example.json config/settings.json
   ```

2. **Edit `settings.json` with your API keys and preferences:**
   ```json
   {
     "api_keys": {
       "openai_api_key": "sk-your-openai-api-key-here",
       "azure_devops_pat": "your-personal-access-token"
     }
   }
   ```

## Configuration Options

### API Keys
- **`openai_api_key`**: OpenAI API key for GPT-5 reflection service
- **`claude_code_api_key`**: Claude Code SDK API key (if needed)  
- **`azure_devops_pat`**: Azure DevOps Personal Access Token

### TDD Agent Settings
- **`max_reflection_retries`**: Maximum retry attempts for reflection feedback (default: 3)
- **`enable_reflection`**: Enable/disable OpenAI reflection quality gate (default: true)
- **`git_diff_min_size`**: Minimum git diff size to trigger reflection (default: 50)

### Planning Agent Settings
- **`max_iterations`**: Maximum planning iterations (default: 1)
- **`include_integration_tests`**: Force integration test creation (default: true)
- **`test_categories`**: Required test categories to include

### Azure DevOps Defaults
- **`default_organization`**: Default Azure DevOps organization URL
- **`default_project`**: Default project name
- **`default_area_path`**: Default area path for work items
- **`default_iteration_path`**: Default iteration path

### Logging
- **`level`**: Log level (debug, info, warning, error)
- **`enable_file_logging`**: Write logs to file (default: false)
- **`log_file_path`**: Path for log file

## Environment Variable Fallbacks

If settings are not provided in the JSON file, the system will check these environment variables:

- `OPENAI_API_KEY`
- `CLAUDE_CODE_API_KEY` 
- `AZURE_DEVOPS_PAT`

## Usage in Code

```python
from config.settings_manager import get_settings

# Get settings instance
settings = get_settings()

# Get API key with fallback
api_key = settings.get_api_key('openai')

# Get specific setting
max_retries = settings.get('tdd_agent.max_reflection_retries', 3)

# Get agent configuration
tdd_config = settings.get_tdd_config()
```

## Security Note

⚠️ **Never commit `settings.json` with real API keys to version control!**

Add `settings.json` to your `.gitignore` file to keep your API keys secure.