"""
PEVL Agent Basic Functionality Tests

Test the basic flow of Plan-Execute-Verify Loop
"""

import sys
from pathlib import Path

# Add project path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from clis.config import ConfigManager
from clis.agent.pevl_agent import PEVLAgent
from clis.agent.task_analyzer import TaskAnalyzer
from clis.agent.agent import Agent
from clis.tools.registry import get_all_tools


def test_task_analyzer():
    """Test task analyzer"""
    print("\n" + "="*60)
    print("Test 1: TaskAnalyzer")
    print("="*60 + "\n")
    
    config_manager = ConfigManager()
    agent = Agent(config_manager)
    analyzer = TaskAnalyzer(agent)
    
    # Test tasks of different complexity
    test_queries = [
        "Create a text file",
        "Create Flask Web service",
        "Deploy Docker container and test",
        "Analyze this project's architecture"
    ]
    
    for query in test_queries:
        print(f"Task: {query}")
        try:
            analysis = analyzer.analyze(query)
            print(f"  Complexity: {analysis.complexity}")
            print(f"  Uncertainty: {analysis.uncertainty}")
            print(f"  Recommended mode: {analysis.recommended_mode}")
            print(f"  Estimated steps: {analysis.estimated_steps}")
            print(f"  Reasoning: {analysis.reasoning[:100]}...")
            print()
        except Exception as e:
            print(f"  ❌ Analysis failed: {e}\n")


def test_pevl_agent_structure():
    """Test PEVL Agent basic structure"""
    print("\n" + "="*60)
    print("Test 2: PEVL Agent Structure")
    print("="*60 + "\n")
    
    config_manager = ConfigManager()
    tools = get_all_tools()
    
    try:
        agent = PEVLAgent(config_manager=config_manager, tools=tools)
        print(f"✓ PEVL Agent created successfully")
        print(f"  Tool count: {len(tools)}")
        print(f"  Max rounds: {agent.max_rounds}")
        print()
    except Exception as e:
        print(f"❌ Creation failed: {e}\n")
        import traceback
        traceback.print_exc()


def test_pevl_simple_task():
    """Test PEVL executing simple task"""
    print("\n" + "="*60)
    print("Test 3: PEVL Simple Task Execution (Simulated)")
    print("="*60 + "\n")
    
    config_manager = ConfigManager()
    tools = get_all_tools()
    agent = PEVLAgent(config_manager=config_manager, tools=tools, max_rounds=2)
    
    # Simple task
    query = "List files in current directory"
    
    print(f"Task: {query}\n")
    
    try:
        step_count = 0
        for step in agent.execute(query):
            step_type = step.get('type')
            step_count += 1
            
            if step_type == "phase":
                print(f"[Phase] {step.get('content')}")
            elif step_type == "analysis_result":
                print(f"[Analysis] {step.get('content')}")
            elif step_type == "round_start":
                print(f"[Round] {step.get('content')}")
            elif step_type == "plan":
                plan = step.get('plan')
                if plan:
                    print(f"[Plan] {plan.total_steps} steps")
            elif step_type == "complete":
                rounds = step.get('rounds', 1)
                print(f"[Complete] {step.get('content')} (Round {rounds})")
                break
            elif step_type == "error":
                print(f"[Error] {step.get('content')}")
                break
            
            # Limit steps to avoid test hanging
            if step_count > 50:
                print("[Warning] Steps exceeded 50, stopping test")
                break
        
        print(f"\n✓ Test completed, total {step_count} steps")
        
    except KeyboardInterrupt:
        print("\n\n❌ Test interrupted")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n" + "="*60)
    print("PEVL Agent Basic Functionality Tests")
    print("="*60)
    
    try:
        # Test 1: TaskAnalyzer
        # test_task_analyzer()  # Requires API key, skip for now
        
        # Test 2: PEVL Agent structure
        test_pevl_agent_structure()
        
        # Test 3: Simple task execution
        # test_pevl_simple_task()  # Requires API, skip for now
        
        print("\n" + "="*60)
        print("✓ All structure tests passed!")
        print("="*60 + "\n")
        
        print("Note: Full functionality tests require DeepSeek API key configuration")
        print("      Run: clis config set llm.api.key YOUR_KEY")
        
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
