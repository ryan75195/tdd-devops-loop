#!/usr/bin/env python3

"""
Agentic Pipeline - Main Entry Point

This is the main entry point for the generic agentic pipeline system.
Supports multiple agent types and complex workflows.
"""

import sys
import argparse
from pathlib import Path

# Import the agentic pipeline framework
from agentic_pipeline import AgentPipeline, AgentRegistry, AgentConfig
from agentic_pipeline.core.registry import get_registry
from agentic_pipeline.composition.workflow import WorkflowBuilder, create_tdd_workflow, create_debug_workflow

# Import and register built-in agents
from agentic_pipeline.agents.tdd_agent import TDDAgent
from agentic_pipeline.agents.code_review_agent import CodeReviewAgent
from agentic_pipeline.agents.debug_agent import DebugAgent
from agentic_pipeline.agents.planning_agent import PlanningAgent

# Import utilities
from agentic_pipeline.utils.logger import Logger


def register_builtin_agents():
    """Register all built-in agents with the global registry."""
    registry = get_registry()
    
    # Register TDD Agent
    registry.register_agent(
        agent_type="tdd",
        agent_class=TDDAgent,
        description="Performs iterative Test-Driven Development workflows",
        version="2.0.0",
        tags=["development", "testing", "tdd"]
    )
    
    # Register Code Review Agent
    registry.register_agent(
        agent_type="code_review",
        agent_class=CodeReviewAgent,
        description="Performs iterative code reviews with improvement suggestions",
        version="1.0.0",
        tags=["review", "quality", "analysis"]
    )
    
    # Register Debug Agent
    registry.register_agent(
        agent_type="debug",
        agent_class=DebugAgent,
        description="Performs iterative debugging with systematic error analysis",
        version="1.0.0",
        tags=["debug", "troubleshooting", "error-analysis"]
    )
    
    # Register Planning Agent
    registry.register_agent(
        agent_type="planning",
        agent_class=PlanningAgent,
        description="Converts natural language specs to Azure DevOps work items with BDD test cases",
        version="1.0.0",
        tags=["planning", "bdd", "azure-devops", "project-management"]
    )


def cmd_list_agents(args):
    """List all available agents."""
    registry = get_registry()
    agents = registry.list_agents()
    
    print("Available Agents:")
    print("=" * 50)
    for agent in agents:
        print(f"Type: {agent.agent_type}")
        print(f"Description: {agent.description}")
        print(f"Version: {agent.version}")
        print(f"Tags: {', '.join(agent.tags)}")
        print("-" * 30)


def cmd_run_agent(args):
    """Run a single agent."""
    registry = get_registry()
    logger = Logger()
    
    # Create agent configuration
    config = AgentConfig.create_simple(
        name=f"{args.agent_type}_agent",
        agent_type=args.agent_type,
        max_iterations=args.max_iterations
    )
    
    # Add agent-specific parameters
    if args.agent_type == "tdd":
        if not args.project_path or not getattr(args, 'work_item', None):
            print("Error: TDD agent requires --project-path and --work-item")
            sys.exit(1)
        config.set_parameter("project_path", args.project_path)
        config.set_parameter("work_item_id", getattr(args, 'work_item', None))
    
    elif args.agent_type == "debug":
        if not args.error_description:
            print("Error: Debug agent requires --error-description")
            sys.exit(1)
        config.set_parameter("error_description", args.error_description)
        if args.test_command:
            config.set_parameter("test_command", args.test_command)
    
    elif args.agent_type == "code_review":
        if args.target_files:
            config.set_parameter("target_files", args.target_files.split(","))
        config.set_parameter("fix_issues", args.fix_issues)
    
    elif args.agent_type == "planning":
        if not args.spec_file or not args.project_name or not args.organization:
            print("Error: Planning agent requires --spec-file, --project-name, and --organization")
            sys.exit(1)
        config.set_parameter("spec_file", args.spec_file)
        config.set_parameter("project_name", args.project_name)
        config.set_parameter("organization", args.organization)
        if args.parent_id:
            config.set_parameter("parent_id", args.parent_id)
        if args.area_path:
            config.set_parameter("area_path", args.area_path)
        if args.iteration_path:
            config.set_parameter("iteration_path", args.iteration_path)
    
    # Create and run agent
    try:
        agent = registry.create_agent(args.agent_type, config)
        pipeline = AgentPipeline(agent, logger)
        
        print(f"Starting {args.agent_type} agent...")
        results = pipeline.run()
        
        print("\nAgent execution completed!")
        print(f"Status: {results['pipeline_status']['final_status']}")
        print(f"Iterations: {results['pipeline_status']['total_iterations']}")
        print(f"Duration: {results['pipeline_status']['duration_seconds']:.2f} seconds")
        
        if results['pipeline_status']['errors']:
            print("Errors:")
            for error in results['pipeline_status']['errors']:
                print(f"  - {error}")
    
    except Exception as e:
        print(f"Error running agent: {e}")
        sys.exit(1)


def cmd_run_workflow(args):
    """Run a predefined workflow."""
    logger = Logger()
    
    if args.workflow_type == "tdd":
        if not args.project_path or not args.ticket:
            print("Error: TDD workflow requires --project-path and --ticket")
            sys.exit(1)
        
        workflow_agent = create_tdd_workflow(args.project_path, args.ticket)
        
    elif args.workflow_type == "debug":
        if not args.error_description:
            print("Error: Debug workflow requires --error-description")
            sys.exit(1)
        
        workflow_agent = create_debug_workflow(args.error_description, args.test_command)
    
    else:
        print(f"Error: Unknown workflow type: {args.workflow_type}")
        sys.exit(1)
    
    # Run the workflow
    try:
        pipeline = AgentPipeline(workflow_agent, logger)
        
        print(f"Starting {args.workflow_type} workflow...")
        results = pipeline.run()
        
        print("\nWorkflow execution completed!")
        print(f"Status: {results['pipeline_status']['final_status']}")
        print(f"Iterations: {results['pipeline_status']['total_iterations']}")
        print(f"Duration: {results['pipeline_status']['duration_seconds']:.2f} seconds")
        
        # Show workflow-specific results
        agent_results = results.get('agent_results', {})
        if 'step_results' in agent_results:
            print(f"Completed steps: {agent_results['completed_steps']}")
            if agent_results['failed_steps']:
                print(f"Failed steps: {agent_results['failed_steps']}")
    
    except Exception as e:
        print(f"Error running workflow: {e}")
        sys.exit(1)


def cmd_run_config(args):
    """Run workflow from configuration file."""
    logger = Logger()
    
    config_path = Path(args.config_file)
    if not config_path.exists():
        print(f"Error: Configuration file not found: {config_path}")
        sys.exit(1)
    
    try:
        # Load workflow from configuration
        if config_path.suffix.lower() == '.yaml' or config_path.suffix.lower() == '.yml':
            builder = WorkflowBuilder.from_yaml(config_path)
        elif config_path.suffix.lower() == '.json':
            builder = WorkflowBuilder.from_json(config_path)
        else:
            print("Error: Configuration file must be YAML or JSON")
            sys.exit(1)
        
        # Build and run workflow
        workflow_agent = builder.build()
        pipeline = AgentPipeline(workflow_agent, logger)
        
        print(f"Starting workflow from {config_path}...")
        results = pipeline.run()
        
        print("\nWorkflow execution completed!")
        print(f"Status: {results['pipeline_status']['final_status']}")
        print(f"Iterations: {results['pipeline_status']['total_iterations']}")
        print(f"Duration: {results['pipeline_status']['duration_seconds']:.2f} seconds")
    
    except Exception as e:
        print(f"Error running configuration: {e}")
        sys.exit(1)


def cmd_tdd_convenience(args):
    """Run TDD agent with familiar command-line interface."""
    registry = get_registry()
    logger = Logger()
    
    # Create TDD agent configuration with new parameters
    config_params = {
        "project_path": args.project_path,
        "work_item_id": args.work_item_id
    }
    
    # Add organization if provided
    if hasattr(args, 'organization') and args.organization:
        config_params["organization"] = args.organization
    
    config = AgentConfig.create_simple(
        name="tdd_agent",
        agent_type="tdd",
        **config_params
    )
    
    try:
        agent = registry.create_agent("tdd", config)
        pipeline = AgentPipeline(agent, logger)
        
        print(f"Starting TDD workflow for work item {args.work_item_id}...")
        print(f"Project: {args.project_path}")
        print("No iteration limits - will continue until all tasks complete")
        print()
        
        results = pipeline.run()
        
        print("\nTDD workflow completed!")
        print(f"Status: {results['pipeline_status']['final_status']}")
        print(f"Iterations: {results['pipeline_status']['total_iterations']}")
        print(f"Duration: {results['pipeline_status']['duration_seconds']:.2f} seconds")
        
        if results['pipeline_status']['errors']:
            print("Errors:")
            for error in results['pipeline_status']['errors']:
                print(f"  - {error}")
    
    except Exception as e:
        print(f"Error running TDD workflow: {e}")
        sys.exit(1)


def main():
    """Main entry point."""
    # Register built-in agents
    register_builtin_agents()
    
    # Create argument parser
    parser = argparse.ArgumentParser(
        description="Agentic Pipeline - Generic framework for AI agent workflows"
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List agents command
    list_parser = subparsers.add_parser('list', help='List available agents')
    
    # Run single agent command
    run_parser = subparsers.add_parser('run', help='Run a single agent')
    run_parser.add_argument('agent_type', help='Type of agent to run')
    run_parser.add_argument('--max-iterations', type=int, default=50, help='Maximum iterations')
    run_parser.add_argument('--project-path', help='Project path (for TDD agent)')
    run_parser.add_argument('--work-item', help='Work item ID (for TDD agent)')
    run_parser.add_argument('--error-description', help='Error description (for Debug agent)')
    run_parser.add_argument('--test-command', help='Test command (for Debug agent)')
    run_parser.add_argument('--target-files', help='Target files (for Code Review agent)')
    run_parser.add_argument('--fix-issues', action='store_true', help='Automatically fix issues')
    # Planning agent arguments
    run_parser.add_argument('--spec-file', help='Path to specification file (for Planning agent)')
    run_parser.add_argument('--project-name', help='Azure DevOps project name (for Planning agent)')
    run_parser.add_argument('--organization', help='Azure DevOps organization URL (for Planning agent)')
    run_parser.add_argument('--parent-id', type=int, help='Parent work item ID to link to (for Planning agent)')
    run_parser.add_argument('--area-path', help='Area path for work items (for Planning agent)')
    run_parser.add_argument('--iteration-path', help='Iteration path for work items (for Planning agent)')
    
    # Run workflow command
    workflow_parser = subparsers.add_parser('workflow', help='Run a predefined workflow')
    workflow_parser.add_argument('workflow_type', choices=['tdd', 'debug'], help='Type of workflow')
    workflow_parser.add_argument('--project-path', help='Project path')
    workflow_parser.add_argument('--work-item', help='Work item ID')
    workflow_parser.add_argument('--error-description', help='Error description')
    workflow_parser.add_argument('--test-command', help='Test command')
    
    # Run from config file command
    config_parser = subparsers.add_parser('config', help='Run workflow from configuration file')
    config_parser.add_argument('config_file', help='Path to YAML or JSON configuration file')
    
    # TDD convenience command (maintains familiar interface)
    tdd_parser = subparsers.add_parser('tdd', help='Run TDD workflow (convenience command)')
    tdd_parser.add_argument('project_path', help='Path to the project directory')
    tdd_parser.add_argument('work_item_id', help='Azure DevOps PBI work item ID')
    tdd_parser.add_argument('--organization', help='Azure DevOps organization URL')
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Execute command
    if args.command == 'list':
        cmd_list_agents(args)
    elif args.command == 'run':
        cmd_run_agent(args)
    elif args.command == 'workflow':
        cmd_run_workflow(args)
    elif args.command == 'config':
        cmd_run_config(args)
    elif args.command == 'tdd':
        cmd_tdd_convenience(args)


if __name__ == "__main__":
    main()