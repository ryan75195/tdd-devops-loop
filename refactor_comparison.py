#!/usr/bin/env python3

"""
Comparison script showing the benefits of the refactored TDD DevOps Loop.
"""

import os


def analyze_code_metrics():
    """Analyze and compare code metrics between original and refactored versions."""
    
    def count_lines(filepath):
        """Count lines in a file."""
        try:
            with open(filepath, 'r') as f:
                return len(f.readlines())
        except FileNotFoundError:
            return 0
    
    def count_functions(filepath):
        """Count functions in a Python file."""
        try:
            with open(filepath, 'r') as f:
                content = f.read()
                return content.count('def ')
        except FileNotFoundError:
            return 0
    
    def count_classes(filepath):
        """Count classes in a Python file."""
        try:
            with open(filepath, 'r') as f:
                content = f.read()
                return content.count('class ')
        except FileNotFoundError:
            return 0
    
    original = "main.py"
    refactored = "main_refactored.py"
    
    print("=== Code Metrics Comparison ===\n")
    
    print(f"{'Metric':<20} {'Original':<12} {'Refactored':<12} {'Improvement':<12}")
    print("-" * 60)
    
    # Lines of code
    orig_lines = count_lines(original)
    refact_lines = count_lines(refactored)
    line_diff = refact_lines - orig_lines
    print(f"{'Lines of code':<20} {orig_lines:<12} {refact_lines:<12} {line_diff:+}<12")
    
    # Functions
    orig_funcs = count_functions(original)
    refact_funcs = count_functions(refactored)
    func_diff = refact_funcs - orig_funcs
    print(f"{'Functions':<20} {orig_funcs:<12} {refact_funcs:<12} {func_diff:+}<12")
    
    # Classes
    orig_classes = count_classes(original)
    refact_classes = count_classes(refactored)
    class_diff = refact_classes - orig_classes
    print(f"{'Classes':<20} {orig_classes:<12} {refact_classes:<12} {class_diff:+}<12")
    
    print("\n=== Architectural Improvements ===\n")
    
    improvements = [
        "✅ Separation of concerns with dedicated classes",
        "✅ Type hints for better code documentation",
        "✅ Comprehensive docstrings and comments",
        "✅ Configuration management with dataclasses",
        "✅ Dependency injection for testability",
        "✅ Single responsibility principle",
        "✅ Enhanced error handling",
        "✅ Modular design for easier maintenance",
        "✅ Better encapsulation and data hiding",
        "✅ Improved testability with isolated components"
    ]
    
    for improvement in improvements:
        print(improvement)
    
    print("\n=== Class Structure ===\n")
    
    classes = {
        "Configuration": "Manages settings and constants",
        "Logger": "Handles timestamped console output",
        "UsageLimitParser": "Parses Claude usage limits and handles sleep",
        "ClaudeExecutor": "Manages Claude command execution and parsing",
        "TDDDevOpsLoop": "Main orchestrator class"
    }
    
    for class_name, description in classes.items():
        print(f"📦 {class_name:<18} - {description}")
    
    print("\n=== Benefits ===\n")
    
    benefits = [
        "🔧 Maintainability: Each class has a single responsibility",
        "🧪 Testability: Components can be tested in isolation",
        "🔄 Reusability: Classes can be reused in other projects",
        "📖 Readability: Clear structure and comprehensive documentation",
        "🛡️  Reliability: Better error handling and type safety",
        "⚡ Extensibility: Easy to add new features or modify existing ones"
    ]
    
    for benefit in benefits:
        print(benefit)


def demonstrate_usage():
    """Show how to use the refactored code."""
    
    print("\n=== Usage Examples ===\n")
    
    print("1. Basic usage (same as original):")
    print("   python3 main_refactored.py /path/to/project TICKET-123")
    
    print("\n2. Programmatic usage with custom configuration:")
    print("""
   from main_refactored import Configuration, TDDDevOpsLoop
   
   # Custom configuration
   config = Configuration(max_iterations=25)
   
   # Create and run loop
   loop = TDDDevOpsLoop(config)
   loop.run('/path/to/project', 'TICKET-123')
   """)
    
    print("3. Individual component usage:")
    print("""
   from main_refactored import Logger, UsageLimitParser
   
   # Use logger independently
   logger = Logger()
   logger.info("Custom message")
   
   # Use parser independently
   parser = UsageLimitParser()
   epoch = parser.parse_usage_limit_epoch("5-hour limit reached ∙ resets 11am")
   """)


if __name__ == "__main__":
    print("🔄 TDD DevOps Loop - Refactoring Analysis\n")
    analyze_code_metrics()
    demonstrate_usage()
    print("\n🎉 Analysis Complete!")