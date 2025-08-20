#!/usr/bin/env python3

"""
TDD DevOps Loop - Modular Implementation Entry Point

This is the main entry point for the refactored, modular TDD DevOps Loop.
Uses clean architecture with separated concerns and loose coupling.
"""

import sys
from tdd_devops_loop import TDDDevOpsLoop, Configuration


def main():
    """Entry point for the TDD DevOps Loop."""
    if len(sys.argv) != 3:
        print("Usage: python main_modular.py <project_path> <ticket_number>")
        sys.exit(1)
    
    project_path = sys.argv[1]
    ticket_number = sys.argv[2]
    
    config = Configuration()
    loop = TDDDevOpsLoop(config)
    loop.run(project_path, ticket_number)


if __name__ == "__main__":
    main()