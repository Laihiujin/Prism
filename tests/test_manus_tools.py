"""
测试 OpenManus Agent 工具
"""
import asyncio
import sys
from pathlib import Path

# 添加路径
sys.path.insert(0, str(Path(__file__).parent / "syn_backend"))
sys.path.insert(0, str(Path(__file__).parent / "syn_backend" / "OpenManus-worker"))

async def test_tools():
    """测试自定义工具"""
    from fastapi_app.agent.manus_tools import (
        ListAccountsTool,
        ListAssetsTool,
        CallAPITool
    )
    
    print("=" * 60)
    print("测试 OpenManus 自定义工具")
    print("=" * 60)
    
    # 测试 1: ListAccountsTool
    print("\n[测试 1] ListAccountsTool")
    print("-" * 60)
    accounts_tool = ListAccountsTool()
    result = await accounts_tool.execute()
    print(f"结果: {result.output if hasattr(result, 'output') else result.error}")
    
    # 测试 2: ListAssetsTool
    print("\n[测试 2] ListAssetsTool")
    print("-" * 60)
    assets_tool = ListAssetsTool()
    result = await assets_tool.execute(limit=5)
    print(f"结果: {result.output if hasattr(result, 'output') else result.error}")
    
    # 测试 3: CallAPITool
    print("\n[测试 3] CallAPITool - 获取账号")
    print("-" * 60)
    api_tool = CallAPITool()
    result = await api_tool.execute(endpoint="/accounts", method="GET")
    print(f"结果: {result.output[:500] if hasattr(result, 'output') else result.error}")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_tools())
