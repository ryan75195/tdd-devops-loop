# TDD DevOps Loop - Modular Architecture

A clean, maintainable implementation of the TDD DevOps Loop using object-oriented design principles and separation of concerns.

## Architecture

The project follows clean architecture principles with the following structure:

```
tdd_devops_loop/
├── __init__.py                    # Package entry point
├── core/                          # Core business logic
│   ├── __init__.py
│   ├── config.py                  # Configuration and data classes
│   ├── interfaces.py              # Abstract base classes and protocols
│   ├── command_builder.py         # Claude command construction
│   ├── stream_processor.py        # Stream output processing
│   ├── response_processor.py      # Response parsing
│   ├── session_manager.py         # Main facade orchestrator
│   └── loop.py                    # Main TDD loop orchestrator
├── handlers/                      # Strategy pattern implementations
│   ├── __init__.py
│   └── tool_handlers.py           # Tool-specific handlers
├── parsers/                       # Chain of responsibility for JSON parsing
│   ├── __init__.py
│   └── json_parsers.py            # JSON parsing strategies
├── events/                        # Observer pattern for event handling
│   ├── __init__.py
│   └── event_handlers.py          # Event handling components
└── utils/                         # Utility components
    ├── __init__.py
    ├── logger.py                  # Logging utilities
    └── usage_parser.py            # Usage limit parsing
```

## Design Patterns Used

1. **Strategy Pattern**: Tool handlers for different Claude tools
2. **Chain of Responsibility**: JSON parsing with multiple fallback strategies
3. **Observer Pattern**: Event handling with pluggable observers
4. **Facade Pattern**: ClaudeSessionManager orchestrates all components
5. **Factory Pattern**: Event handler factory for different event types

## Usage

### Modular Version (Recommended)
```bash
python main_modular.py <project_path> <ticket_number>
```

### Legacy Monolithic Version
```bash
python main.py <project_path> <ticket_number>
```

## Benefits of Modular Architecture

- **Testability**: Each component can be unit tested in isolation
- **Extensibility**: Adding new tools/events requires minimal changes
- **Maintainability**: Clear separation of concerns
- **Flexibility**: Easy to swap implementations
- **Readability**: Well-organized and self-documenting code

## Configuration

The `Configuration` class in `core/config.py` contains all configurable parameters:
- `max_iterations`: Maximum number of TDD iterations (default: 50)
- `response_schema`: JSON schema for Claude responses

## Dependencies

This project uses only Python standard library components - no external dependencies required.