"""
Integration test: ReAct vs Plan-Execute mode comparison

Test scenarios:
1. Simple tasks (2)
2. Medium tasks (4)
3. Complex tasks (2)
4. Edge cases (2)

Evaluation metrics:
- Execution time
- Operation count
- Success rate
- Memory quality
"""

import pytest
import time
import json
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
import tempfile
import shutil

from clis.config import ConfigManager
from clis.agent.interactive_agent import InteractiveAgent
from clis.agent.two_phase_agent import TwoPhaseAgent
from clis.tools.registry import get_all_tools


class TestResult:
    """Single test result"""
    
    def __init__(self, mode: str, scenario: str):
        self.mode = mode  # "react" or "plan-execute"
        self.scenario = scenario
        self.success = False
        self.execution_time = 0.0
        self.operation_count = 0
        self.tool_calls = []
        self.memory_stats = {}
        self.task_file = None
        self.error = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "mode": self.mode,
            "scenario": self.scenario,
            "success": self.success,
            "execution_time": self.execution_time,
            "operation_count": self.operation_count,
            "tool_calls": self.tool_calls,
            "memory_stats": self.memory_stats,
            "task_file": str(self.task_file) if self.task_file else None,
            "error": self.error
        }


class AgentComparison:
    """Agent comparison test framework"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.tools = get_all_tools()
        self.results: List[TestResult] = []
        self.test_root = Path(tempfile.gettempdir()) / f"clis_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.test_root.mkdir(exist_ok=True)
    
    def run_react_mode(self, query: str, scenario: str) -> TestResult:
        """Run ReAct mode test"""
        result = TestResult("react", scenario)
        
        try:
            agent = InteractiveAgent(
                config_manager=self.config_manager,
                tools=self.tools,
                max_iterations=20
            )
            
            start_time = time.time()
            
            for step in agent.execute(query):
                step_type = step.get("type")
                
                if step_type == "tool_call":
                    result.operation_count += 1
                    result.tool_calls.append({
                        "tool": step.get("tool"),
                        "params": step.get("params")
                    })
                
                elif step_type == "complete":
                    result.success = True
                    result.memory_stats = step.get("stats", {})
                    result.task_file = step.get("task_file")
                    break
                
                elif step_type == "error":
                    result.error = step.get("content")
                    break
            
            result.execution_time = time.time() - start_time
            
        except Exception as e:
            result.error = str(e)
            result.execution_time = time.time() - start_time
        
        return result
    
    def run_plan_execute_mode(self, query: str, scenario: str) -> TestResult:
        """Run Plan-Execute mode test"""
        result = TestResult("plan-execute", scenario)
        
        try:
            agent = TwoPhaseAgent(
                config_manager=self.config_manager,
                tools=self.tools
            )
            
            start_time = time.time()
            
            for step in agent.execute(query, auto_approve_plan=True):
                step_type = step.get("type")
                
                if step_type == "tool_call":
                    result.operation_count += 1
                    result.tool_calls.append({
                        "tool": step.get("tool"),
                        "params": step.get("params")
                    })
                
                elif step_type == "complete":
                    result.success = True
                    result.memory_stats = step.get("stats", {})
                    result.task_file = step.get("task_file")
                    break
                
                elif step_type == "error":
                    result.error = step.get("content")
                    break
            
            result.execution_time = time.time() - start_time
            
        except Exception as e:
            result.error = str(e)
            result.execution_time = time.time() - start_time
        
        return result
    
    def compare_scenario(self, scenario: str, query: str) -> Dict[str, TestResult]:
        """Compare single scenario"""
        print(f"\n{'='*60}")
        print(f"Testing: {scenario}")
        print(f"Query: {query}")
        print(f"{'='*60}\n")
        
        # Clean test environment
        test_dir = self.test_root / scenario.replace(" ", "_")
        if test_dir.exists():
            shutil.rmtree(test_dir)
        test_dir.mkdir(parents=True)
        
        # ReAct mode
        print("Running ReAct mode...")
        react_result = self.run_react_mode(query, scenario)
        self.results.append(react_result)
        print(f"✓ Completed in {react_result.execution_time:.2f}s, {react_result.operation_count} operations")
        
        # Plan-Execute mode
        print("Running Plan-Execute mode...")
        plan_result = self.run_plan_execute_mode(query, scenario)
        self.results.append(plan_result)
        print(f"✓ Completed in {plan_result.execution_time:.2f}s, {plan_result.operation_count} operations")
        
        # Compare
        self._print_comparison(react_result, plan_result)
        
        return {
            "react": react_result,
            "plan-execute": plan_result
        }
    
    def _print_comparison(self, react: TestResult, plan: TestResult):
        """Print comparison results"""
        print(f"\n{'─'*60}")
        print("Comparison:")
        print(f"{'─'*60}")
        print(f"Success:       ReAct={react.success}, Plan-Execute={plan.success}")
        print(f"Time:          ReAct={react.execution_time:.2f}s, Plan-Execute={plan.execution_time:.2f}s")
        print(f"Operations:    ReAct={react.operation_count}, Plan-Execute={plan.operation_count}")
        
        if react.execution_time > 0 and plan.execution_time > 0:
            time_diff = ((plan.execution_time - react.execution_time) / react.execution_time) * 100
            ops_diff = ((plan.operation_count - react.operation_count) / react.operation_count) * 100 if react.operation_count > 0 else 0
            
            print(f"Time diff:     {time_diff:+.1f}%")
            print(f"Ops diff:      {ops_diff:+.1f}%")
    
    def save_results(self, output_path: str = "test_results.json"):
        """Save test results"""
        results_data = {
            "timestamp": datetime.now().isoformat(),
            "test_root": str(self.test_root),
            "total_scenarios": len(self.results) // 2,
            "results": [r.to_dict() for r in self.results]
        }
        
        with open(output_path, 'w') as f:
            json.dump(results_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Results saved to {output_path}")
    
    def generate_report(self) -> str:
        """Generate test report"""
        report = []
        report.append("# Agent Comparison Test Report")
        report.append(f"\n**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"**Total Scenarios**: {len(self.results) // 2}\n")
        
        # Group by scenario
        scenarios = {}
        for result in self.results:
            if result.scenario not in scenarios:
                scenarios[result.scenario] = {}
            scenarios[result.scenario][result.mode] = result
        
        # Summary statistics
        react_wins = 0
        plan_wins = 0
        
        for scenario, results in scenarios.items():
            react = results.get("react")
            plan = results.get("plan-execute")
            
            if react and plan:
                if react.execution_time < plan.execution_time and react.operation_count <= plan.operation_count:
                    react_wins += 1
                elif plan.execution_time < react.execution_time and plan.operation_count <= react.operation_count:
                    plan_wins += 1
        
        report.append(f"## Summary\n")
        report.append(f"- ReAct wins: {react_wins}")
        report.append(f"- Plan-Execute wins: {plan_wins}")
        report.append(f"- Ties: {len(scenarios) - react_wins - plan_wins}\n")
        
        # Detailed results
        report.append("## Detailed Results\n")
        
        for scenario, results in scenarios.items():
            report.append(f"### {scenario}\n")
            
            react = results.get("react")
            plan = results.get("plan-execute")
            
            if react and plan:
                report.append("| Metric | ReAct | Plan-Execute | Diff |")
                report.append("|--------|-------|--------------|------|")
                report.append(f"| Success | {react.success} | {plan.success} | - |")
                report.append(f"| Time (s) | {react.execution_time:.2f} | {plan.execution_time:.2f} | {plan.execution_time - react.execution_time:+.2f} |")
                report.append(f"| Operations | {react.operation_count} | {plan.operation_count} | {plan.operation_count - react.operation_count:+d} |")
                report.append("")
        
        return "\n".join(report)


# ============ Test Scenarios ============

def test_simple_file_creation():
    """Scenario 1: Create simple text file"""
    comparison = AgentComparison()
    comparison.compare_scenario(
        "Simple File Creation",
        f"Create a text file at {comparison.test_root}/test1/hello.txt with content 'Hello World'"
    )
    return comparison


def test_simple_file_read():
    """Scenario 2: Read and analyze file"""
    comparison = AgentComparison()
    test_file = comparison.test_root / "test2" / "data.txt"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("apple\nbanana\ncherry\n")
    
    comparison.compare_scenario(
        "Simple File Read",
        f"Read {test_file} and count how many lines it has"
    )
    return comparison


def test_flask_web_service():
    """Scenario 3: Flask Web Service"""
    comparison = AgentComparison()
    comparison.compare_scenario(
        "Flask Web Service",
        f"Create a Flask web service in {comparison.test_root}/test3 with a /hello endpoint that returns 'Hello World', use python3"
    )
    return comparison


def test_git_repository():
    """Scenario 4: Git repository creation"""
    comparison = AgentComparison()
    comparison.compare_scenario(
        "Git Repository Creation",
        f"Create a git repository in {comparison.test_root}/test4, add a README.md file with 'Test Project', and commit it"
    )
    return comparison


# ============ Main Test Suite ============

@pytest.mark.integration
def test_full_comparison():
    """Complete comparison test suite"""
    print("\n" + "="*60)
    print("AGENT COMPARISON TEST SUITE")
    print("="*60)
    
    all_results = []
    
    # Simple tasks
    print("\n[SIMPLE TASKS]")
    c1 = test_simple_file_creation()
    all_results.extend(c1.results)
    
    c2 = test_simple_file_read()
    all_results.extend(c2.results)
    
    # Medium tasks
    print("\n[MEDIUM TASKS]")
    c3 = test_flask_web_service()
    all_results.extend(c3.results)
    
    c4 = test_git_repository()
    all_results.extend(c4.results)
    
    # Save results
    comparison = AgentComparison()
    comparison.results = all_results
    comparison.save_results("tests/test_results.json")
    
    # Generate report
    report = comparison.generate_report()
    with open("tests/test_report.md", "w") as f:
        f.write(report)
    
    print(f"\n{'='*60}")
    print("✓ All tests completed")
    print(f"{'='*60}\n")
    print(report)


if __name__ == "__main__":
    # Can be run standalone
    test_full_comparison()
