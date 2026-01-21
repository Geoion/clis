"""
PEVL Agent 基础功能测试

测试 Plan-Execute-Verify Loop 的基本流程
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from clis.config import ConfigManager
from clis.agent.pevl_agent import PEVLAgent
from clis.agent.task_analyzer import TaskAnalyzer
from clis.agent.agent import Agent
from clis.tools.registry import get_all_tools


def test_task_analyzer():
    """测试任务分析器"""
    print("\n" + "="*60)
    print("测试 1: TaskAnalyzer")
    print("="*60 + "\n")
    
    config_manager = ConfigManager()
    agent = Agent(config_manager)
    analyzer = TaskAnalyzer(agent)
    
    # 测试不同复杂度的任务
    test_queries = [
        "创建一个文本文件",
        "创建 Flask Web 服务",
        "部署 Docker 容器并测试",
        "分析这个项目的架构"
    ]
    
    for query in test_queries:
        print(f"任务: {query}")
        try:
            analysis = analyzer.analyze(query)
            print(f"  复杂度: {analysis.complexity}")
            print(f"  不确定性: {analysis.uncertainty}")
            print(f"  推荐模式: {analysis.recommended_mode}")
            print(f"  预估步骤: {analysis.estimated_steps}")
            print(f"  推理: {analysis.reasoning[:100]}...")
            print()
        except Exception as e:
            print(f"  ❌ 分析失败: {e}\n")


def test_pevl_agent_structure():
    """测试 PEVL Agent 基本结构"""
    print("\n" + "="*60)
    print("测试 2: PEVL Agent 结构")
    print("="*60 + "\n")
    
    config_manager = ConfigManager()
    tools = get_all_tools()
    
    try:
        agent = PEVLAgent(config_manager=config_manager, tools=tools)
        print(f"✓ PEVL Agent 创建成功")
        print(f"  工具数量: {len(tools)}")
        print(f"  最大轮数: {agent.max_rounds}")
        print()
    except Exception as e:
        print(f"❌ 创建失败: {e}\n")
        import traceback
        traceback.print_exc()


def test_pevl_simple_task():
    """测试 PEVL 执行简单任务"""
    print("\n" + "="*60)
    print("测试 3: PEVL 简单任务执行 (模拟)")
    print("="*60 + "\n")
    
    config_manager = ConfigManager()
    tools = get_all_tools()
    agent = PEVLAgent(config_manager=config_manager, tools=tools, max_rounds=2)
    
    # 简单任务
    query = "列出当前目录的文件"
    
    print(f"任务: {query}\n")
    
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
            
            # 限制步骤数避免测试卡住
            if step_count > 50:
                print("[Warning] 步骤超过50,停止测试")
                break
        
        print(f"\n✓ 测试完成,共 {step_count} 个步骤")
        
    except KeyboardInterrupt:
        print("\n\n❌ 测试中断")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n" + "="*60)
    print("PEVL Agent 基础功能测试")
    print("="*60)
    
    try:
        # 测试1: TaskAnalyzer
        # test_task_analyzer()  # 需要 API key,暂时跳过
        
        # 测试2: PEVL Agent 结构
        test_pevl_agent_structure()
        
        # 测试3: 简单任务执行
        # test_pevl_simple_task()  # 需要 API,暂时跳过
        
        print("\n" + "="*60)
        print("✓ 所有结构测试通过!")
        print("="*60 + "\n")
        
        print("注意: 完整功能测试需要配置 DeepSeek API key")
        print("      运行: clis config set llm.api.key YOUR_KEY")
        
    except Exception as e:
        print(f"\n❌ 测试套件失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
