#!/usr/bin/env python3
"""Test script for simplified reflection loop."""

import sys
from pathlib import Path
import subprocess
import tempfile
import os

# Add the agentic_pipeline to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from agentic_pipeline.agents.tdd_agent import TDDAgent
from agentic_pipeline.core.config import AgentConfig

def test_simplified_reflection():
    """Test the simplified reflection loop with a mock git repo."""
    
    print("🚀 Testing Simplified TDD Reflection Loop...")
    
    # Create a temporary git repository for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"📁 Created temp repo: {temp_dir}")
        
        # Initialize git repo
        subprocess.run(['git', 'init'], cwd=temp_dir, capture_output=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=temp_dir)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=temp_dir)
        
        # Create initial commit
        test_file = Path(temp_dir) / "test.txt"
        test_file.write_text("Initial content\n")
        subprocess.run(['git', 'add', '.'], cwd=temp_dir)
        subprocess.run(['git', 'commit', '-m', 'Initial commit'], cwd=temp_dir)
        
        # Create working changes (simulating Claude's TDD work)
        test_file.write_text("Initial content\nAdded by TDD iteration\n")
        new_file = Path(temp_dir) / "new_test.js"
        new_file.write_text("""
describe('Test Suite', () => {
  it('should test real implementation', () => {
    const service = new RealService();
    const result = service.doSomething();
    expect(result).toBe('expected');
  });
});
""")
        
        print("📝 Created simulated TDD changes:")
        
        # Show working changes
        result = subprocess.run(['git', 'diff', 'HEAD'], 
                              cwd=temp_dir, capture_output=True, text=True)
        print(f"Git diff size: {len(result.stdout)} characters")
        print("Sample diff:")
        print(result.stdout[:300] + "..." if len(result.stdout) > 300 else result.stdout)
        
        # Create mock task details
        mock_task = {
            "id": "test-123",
            "title": "Test: Real service integration should work correctly",
            "description": "Test that the service integrates properly with real implementation",
            "acceptance_criteria": """
Given: A service instance exists
When: doSomething() is called  
Then: The result should be 'expected'
And: No mocks should be used for the primary functionality
"""
        }
        
        print("\n🤖 Testing TDD Agent reflection methods...")
        
        # Create TDD Agent config
        config = AgentConfig.create_simple(
            name="test-tdd-agent",
            agent_type="tdd",
            project_path=temp_dir,
            work_item_id="123",
            organization="test-org"
        )
        
        # Initialize agent
        agent = TDDAgent(config)
        agent.project_path = temp_dir  # Override for test
        
        # Initialize the agent (this sets up reflection service)
        try:
            agent.initialize()
        except Exception as e:
            # Expected to fail on Azure DevOps calls, but should init reflection service
            print(f"⚠️ Full initialization failed (expected): {e}")
            
            # Manually initialize just the reflection service parts
            from agentic_pipeline.services.openai_reflection_service import OpenAIReflectionService
            config_dir = Path(__file__).parent / "config"
            sys.path.insert(0, str(config_dir))
            from settings_manager import get_settings
            
            settings = get_settings()
            tdd_config = settings.get_tdd_config()
            
            if tdd_config.get('enable_reflection', True):
                try:
                    agent.reflection_service = OpenAIReflectionService()
                    print("✅ Manually initialized reflection service")
                except Exception as refl_error:
                    print(f"❌ Failed to initialize reflection service: {refl_error}")
                    agent.reflection_service = None
        
        try:
            # Test git working changes method
            print("\n📊 Testing _get_git_working_changes()...")
            working_changes = agent._get_git_working_changes()
            print(f"Working changes detected: {len(working_changes)} characters")
            print("✅ Git working changes method works")
            
            # Test reflection service initialization  
            print("\n🔧 Testing reflection service...")
            if hasattr(agent, 'reflection_service') and agent.reflection_service:
                print("✅ Reflection service available")
                
                # Test reflection on working changes
                print("\n🤔 Testing reflection analysis...")
                result = agent.reflection_service.evaluate_tdd_implementation(
                    git_diff=working_changes,
                    task_details=mock_task,
                    bdd_scenarios=mock_task["acceptance_criteria"],
                    iteration_context="Test iteration 1/3"
                )
                
                print(f"📊 Reflection result:")
                print(f"Status: {result.status}")
                print(f"Feedback: {result.feedback[:200]}...")
                
                # Test commit method
                print(f"\n💾 Testing commit method...")
                if result.status == "continue":
                    success = agent._commit_changes("Test: TDD iteration approved by reflection")
                    if success:
                        print("✅ Changes committed successfully")
                    else:
                        print("❌ Commit failed")
                else:
                    print("🔄 Reflection suggested retry - not committing")
                    
            else:
                print("⚠️ No reflection service available (check OpenAI API key)")
                
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_simplified_reflection()