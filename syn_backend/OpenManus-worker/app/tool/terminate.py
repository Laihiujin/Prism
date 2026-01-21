from app.tool.base import BaseTool


_TERMINATE_DESCRIPTION = """当请求已满足或者助手无法继续执行任务时,终止交互。

**何时调用此工具:**
1. ✅ 成功完成所有任务 → 调用 terminate(status='success')
2. ❌ 任务执行失败且无法恢复 → 立即调用 terminate(status='failure')
3. ❌ 工具返回错误状态且无法修复 → 立即调用 terminate(status='failure')
4. ❌ 遇到无法解决的问题 → 立即调用 terminate(status='failure')

**重要提示:**
- 如果任务失败,请不要无休止地重试相同的操作
- 如果工具调用返回失败状态,请立即终止并说明原因
- 不要等待达到最大步数限制才终止
"""


class Terminate(BaseTool):
    name: str = "terminate"
    description: str = _TERMINATE_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "description": "The finish status of the interaction.",
                "enum": ["success", "failure"],
            }
        },
        "required": ["status"],
    }

    async def execute(self, status: str) -> str:
        """Finish the current execution"""
        return f"The interaction has been completed with status: {status}"
