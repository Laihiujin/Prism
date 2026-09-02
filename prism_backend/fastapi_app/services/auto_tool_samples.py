"""自动遍历示例：这里的 `@prism_tool` 函数会被扫描器自动发现并暴露到 MCP/API/CLI/前端。

真实接入时，把任意能力函数加上 `@prism_tool` 装饰器即可，无需手写 ToolSpec。
"""
from fastapi_app.services.tool_catalog import prism_tool


@prism_tool(description="两个整数相加，演示自动遍历。", category="demo")
def add(a: int, b: int = 1) -> dict:
    """把两个整数相加。

    :param a: 第一个数
    :param b: 第二个数，默认 1
    """
    return {"sum": a + b}


@prism_tool(description="反转字符串，演示自动遍历。", category="demo")
def reverse(text: str = "") -> dict:
    """反转字符串。

    :param text: 要反转的字符串
    """
    return {"reversed": text[::-1]}
