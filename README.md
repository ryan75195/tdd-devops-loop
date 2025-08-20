# Agentic Pipeline Framework

A generic framework for creating and orchestrating AI agents with iterative workflows. Originally evolved from the TDD DevOps Loop but now supports multiple agent types and complex workflow composition.

## 🚀 Quick Start

### List Available Agents
```bash
python main.py list
```

### Run TDD Workflow (Original Use Case)
```bash
# Simple TDD command
python main.py tdd /path/to/project TICKET-123

# With custom iterations
python main.py tdd /path/to/project TICKET-123 --max-iterations 30
```

### Run Other Agents
```bash
# Code review
python main.py run code_review --target-files "src/*.py" --fix-issues

# Debug workflow
python main.py run debug --error-description "App crashes on startup" --test-command "python test.py"
```

### Run Complex Workflows
```bash
# Predefined TDD workflow (TDD + Code Review)
python main.py workflow tdd --project-path /path --ticket TICKET-123

# Debug workflow (Debug + Review)
python main.py workflow debug --error-description "Memory leak" --test-command "pytest tests/"
```

### Configuration-Based Workflows
```bash
# Run from YAML configuration
python main.py config examples/tdd_workflow.yaml

# Run from JSON configuration  
python main.py config examples/simple_tdd.json

# Run code review workflow
python main.py config examples/code_review.json

# Run debug workflow
python main.py config examples/debug_workflow.yaml
```

## 🏗️ Architecture

The framework provides a plugin-based architecture for creating iterative AI agents:

```
agentic_pipeline/
├── core/                    # Core framework
│   ├── agent.py            # Abstract Agent base class
│   ├── pipeline.py         # AgentPipeline orchestrator
│   ├── state.py            # AgentState management
│   ├── config.py           # AgentConfig system
│   └── registry.py         # AgentRegistry for discovery
├── agents/                  # Built-in agents
│   ├── tdd_agent.py        # TDD workflows
│   ├── code_review_agent.py # Code review
│   └── debug_agent.py      # Debugging
├── composition/             # Workflow system
│   ├── composite.py        # CompositeAgent orchestrator
│   └── workflow.py         # WorkflowBuilder with DSL
├── utils/                   # Utilities
│   ├── logger.py           # Logging utilities
│   └── usage_parser.py     # Usage limit parsing
└── tdd_core/               # TDD-specific components
    └── ...                 # Original TDD infrastructure
```

## 🤖 Built-in Agents

### 1. TDD Agent
Performs iterative Test-Driven Development workflows.
```bash
python main.py run tdd --project-path /path --ticket TICKET-123
```

### 2. Code Review Agent
Performs systematic code reviews with improvement suggestions.
```bash
python main.py run code_review --target-files "src/*.py" --fix-issues
```

### 3. Debug Agent
Systematic debugging with hypothesis-driven investigation.
```bash
python main.py run debug --error-description "App crashes" --test-command "python test.py"
```

## 🔄 Workflow Composition

### Sequential Workflows
Execute agents one after another:
```yaml
name: "my_workflow"
mode: "sequential"
steps:
  - agent_type: "tdd"
    config:
      project_path: "/path"
      ticket_number: "TICKET-123"
  - agent_type: "code_review"
    config:
      fix_issues: true
```

### Conditional Workflows
Execute agents based on conditions:
```yaml
name: "conditional_workflow"
mode: "conditional"
steps:
  - agent_type: "debug"
    config:
      error_description: "Memory leak"
  - agent_type: "code_review"
    condition: "state.get('debugging_successful', False)"
    config:
      review_criteria: ["performance", "memory management"]
```

### Programmatic API
```python
from agentic_pipeline import AgentPipeline, AgentConfig
from agentic_pipeline.composition.workflow import WorkflowBuilder

# Create workflow programmatically
workflow = (WorkflowBuilder("my_workflow")
            .add_agent("tdd", config={"project_path": "/path", "ticket_number": "TICKET-123"})
            .then("code_review", config={"fix_issues": True})
            .build())

# Run workflow
pipeline = AgentPipeline(workflow)
results = pipeline.run()
```

## 🔌 Creating Custom Agents

Creating a new agent is simple:

```python
from agentic_pipeline.core.agent import Agent, AgentResult, AgentStatus

class MyCustomAgent(Agent):
    # Agent metadata for auto-discovery
    AGENT_TYPE = "my_custom"
    DESCRIPTION = "Does custom work iteratively"
    VERSION = "1.0.0"
    TAGS = ["custom", "example"]
    
    def initialize(self, context):
        """Setup the agent."""
        self.log("info", "Initializing custom agent")
        # Setup logic here
    
    def execute_iteration(self, state):
        """Execute one iteration."""
        # Do work for one iteration
        iteration_data = {"result": "some_work_done"}
        
        return AgentResult(
            status=AgentStatus.RUNNING,
            message="Iteration completed",
            data=iteration_data,
            terminal=False  # Continue or stop
        )
    
    def check_terminal_condition(self, state):
        """Decide when to stop."""
        return state.iteration >= 10  # Stop after 10 iterations
```

The framework automatically discovers and registers this agent, making it available via:
```bash
python main.py run my_custom --config-params here
```

## 📋 Command Reference

### Main Commands
- `python main.py list` - List all available agents
- `python main.py run <agent_type>` - Run a single agent
- `python main.py workflow <workflow_type>` - Run predefined workflows
- `python main.py config <config_file>` - Run from configuration file
- `python main.py tdd <project_path> <ticket>` - TDD convenience command

### TDD-Specific Usage
```bash
# Basic TDD (maintains original interface)
python main.py tdd /path/to/project TICKET-123

# TDD with custom iterations
python main.py tdd /path/to/project TICKET-123 --max-iterations 30

# Advanced TDD workflow with review
python main.py workflow tdd --project-path /path --ticket TICKET-123
```

### Agent-Specific Parameters

**TDD Agent:**
- `--project-path` - Path to project directory
- `--ticket` - Ticket/issue identifier
- `--max-iterations` - Maximum iterations (default: 50)

**Code Review Agent:**
- `--target-files` - Comma-separated list of files to review
- `--fix-issues` - Automatically fix found issues
- `--max-iterations` - Maximum iterations (default: 50)

**Debug Agent:**
- `--error-description` - Description of error to debug
- `--test-command` - Command to test if issue is fixed
- `--max-iterations` - Maximum iterations (default: 50)

## 📁 Configuration Files

### YAML Example
```yaml
name: "comprehensive_tdd"
mode: "sequential"
global_config:
  max_iterations: 30
steps:
  - agent_type: "tdd"
    name: "tdd_implementation"
    config:
      project_path: "/path/to/project"
      ticket_number: "TICKET-123"
  - agent_type: "code_review"
    name: "post_review"
    config:
      fix_issues: true
      review_criteria: ["quality", "performance"]
```

### JSON Example
```json
{
  "name": "debug_workflow",
  "mode": "conditional",
  "steps": [
    {
      "agent_type": "debug",
      "config": {
        "error_description": "Application crashes on large files",
        "test_command": "python test_large_files.py"
      }
    },
    {
      "agent_type": "code_review",
      "condition": "state.get('debugging_successful', False)",
      "config": {
        "review_criteria": ["bug fixes", "error handling"]
      }
    }
  ]
}
```

## 🎯 Key Features

### Plugin Architecture
- **Easy agent creation** - Inherit from `Agent` base class
- **Auto-discovery** - Agents automatically registered when found
- **Zero framework modification** - Add new agents without changing core code

### State Management
- **Historical tracking** - Complete history of all iterations
- **Rollback capabilities** - Revert to previous states
- **State passing** - Share data between agents in workflows
- **Serializable** - Save/restore agent state

### Workflow Composition
- **Sequential execution** - Agents run one after another
- **Conditional branching** - Execute based on state conditions
- **Loop workflows** - Repeat until conditions met
- **Error handling** - Graceful failure management

### Terminal Conditions
- **Max iterations** - Stop after N iterations
- **Success/failure status** - Stop on agent completion
- **Custom conditions** - User-defined termination logic
- **State-based conditions** - Stop when state matches criteria

## 🔧 Development

### Adding a New Agent
1. Create class inheriting from `Agent`
2. Implement required methods (`initialize`, `execute_iteration`, `check_terminal_condition`)
3. Add agent metadata (`AGENT_TYPE`, `DESCRIPTION`, etc.)
4. Place in `agentic_pipeline/agents/` directory
5. Framework automatically discovers and registers it

### Testing
```bash
# Test the framework
python main.py list  # Should show your new agent

# Test your agent
python main.py run your_agent_type --your-params
```

## 📦 Dependencies

This project uses only Python standard library components - no external dependencies required.

## 🔄 Migration from Original TDD System

The original TDD DevOps Loop functionality is fully preserved with a familiar interface:

**Old usage:**
```bash
python main.py /path/to/project TICKET-123  # No longer supported
```

**New usage (equivalent):**
```bash
python main.py tdd /path/to/project TICKET-123  # Primary interface
```

All original functionality is maintained while providing the flexibility of the new agent framework.