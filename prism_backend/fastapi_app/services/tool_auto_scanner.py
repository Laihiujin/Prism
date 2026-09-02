"""自动遍历扫描器：AST 扫描代码库，发现所有 ``@prism_tool`` 标记的函数并注册为工具。

设计要点
--------
- 纯 AST 静态分析：不 import 任何被扫描模块，因此不会触发重依赖/副作用，启动安全。
- 识别方式：function 节点的 ``decorator_list`` 里有名字为 ``prism_tool`` 的装饰器调用。
- 元信息优先取装饰器实参（description / category / parameters / name / output_summary），
  缺省时从 docstring（``:param name:``）与函数签名自动推导。
- handler 为「延迟 import 模块 + 调用函数」的包装，真正调用时才加载模块。
- 只暴露被标记的函数，不会误伤内部 helper。
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import tool_catalog as _tc

BACKEND_ROOT = Path(__file__).resolve().parents[2]  # fastapi_app/services → prism_backend

# 默认扫描根（可被环境变量覆盖以缩小范围）
SCAN_ROOTS = [
    BACKEND_ROOT / "uploader",
    BACKEND_ROOT / "utils",
    BACKEND_ROOT / "automation",
    BACKEND_ROOT / "services",
    BACKEND_ROOT / "fastapi_app" / "services",
]

# 跳过不生成工具的文件
_SKIP_PARTS = {"__pycache__", "node_modules", "vendor", "signing", ".baseline-run"}
_SKIP_PREFIX = ("test_", "conftest", "verify_", "tool_auto_scanner", "_")


def _scan_root_dirs() -> List[Path]:
    return [p for p in SCAN_ROOTS if p.is_dir()]


def _iter_py_files(root: Path):
    for path in root.rglob("*.py"):
        rel = path.relative_to(root)
        if any(part.startswith(".") for part in rel.parts):
            continue
        if path.name.startswith(_SKIP_PREFIX):
            continue
        if any(part in _SKIP_PARTS for part in rel.parts):
            continue
        yield path


def _decorator_keywords(deco: ast.expr) -> Dict[str, Any]:
    """从 @prism_tool(...) 调用里读取字面量实参。"""
    if not isinstance(deco, ast.Call):
        return {}
    kw: Dict[str, Any] = {}
    for node in deco.keywords:
        try:
            kw[node.arg] = ast.literal_eval(node.value)
        except Exception:
            kw[node.arg] = None  # 非字面量，留给推导
    return kw


def _is_prism_tool(deco: ast.expr) -> bool:
    """装饰器是 @prism_tool(...)（或别名 attr.prism_tool(...)）。"""
    if isinstance(deco, ast.Name):
        return deco.id == "prism_tool"
    if isinstance(deco, ast.Attribute):
        return deco.attr == "prism_tool"
    if isinstance(deco, ast.Call):
        f = deco.func
        if isinstance(f, ast.Name):
            return f.id == "prism_tool"
        if isinstance(f, ast.Attribute):
            return f.attr == "prism_tool"
    return False


def _literal(node: Optional[ast.expr]):
    if node is None:
        return None
    if isinstance(node, ast.Constant):
        return node.value
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def _infer_json_type(annotation: Optional[ast.expr], default_node: Optional[ast.expr]) -> str:
    t = None
    if isinstance(annotation, ast.Name):
        t = annotation.id
    elif isinstance(annotation, ast.Constant):
        t = annotation.value
    name = str(t or "").lower()
    if name in ("str", "string"):
        return "string"
    if name in ("int", "integer"):
        return "integer"
    if name in ("float", "number"):
        return "number"
    if name in ("bool", "boolean"):
        return "boolean"
    if name in ("list", "array"):
        return "array"
    if name in ("dict", "object"):
        return "object"
    default = _literal(default_node)
    if isinstance(default, bool):
        return "boolean"
    if isinstance(default, int):
        return "integer"
    if isinstance(default, float):
        return "number"
    if isinstance(default, (list, tuple)):
        return "array"
    if isinstance(default, dict):
        return "object"
    return "string"


def _param_descriptions(docstring: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for line in textwrap.dedent(docstring or "").splitlines():
        s = line.strip().lstrip("*").strip()
        if s.lower().startswith(":param "):
            name = s.split(":", 2)[1].strip().split(" ")[0].strip()
            desc = s.split(":", 2)[2].strip() if s.count(":") >= 2 else ""
            if name:
                out[name] = desc
    return out


def _schema_from_fn(fn: ast.FunctionDef, docstruct: ast.Expr) -> Dict[str, Any]:
    args = fn.args
    positional = list(args.posonlyargs) + list(args.args)
    n_pos = len(positional)
    n_defaults = len(args.defaults)
    properties: Dict[str, Any] = {}
    required: List[str] = []

    def _add(name: str, default_node: Optional[ast.expr], ann: Optional[ast.expr]):
        ptype = _infer_json_type(ann, default_node)
        prop: Dict[str, Any] = {"type": ptype}
        desc = _param_descriptions(ast.get_docstring(docstruct) or "").get(name)
        if desc:
            prop["description"] = desc
        default = _literal(default_node)
        if default is not None:
            prop["default"] = default
        else:
            required.append(name)
        properties[name] = prop

    for i, arg in enumerate(positional):
        is_required_default = i < n_pos - n_defaults
        default_node = args.defaults[i - (n_pos - n_defaults)] if not is_required_default else None
        _add(arg.arg, default_node, arg.annotation)

    for i, arg in enumerate(args.kwonlyargs):
        default_node = args.kw_defaults[i] if i < len(args.kw_defaults) else None
        _add(arg.arg, default_node, arg.annotation)

    schema: Dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _make_handler(module_dotted: str, func_name: str):
    async def handler(**kwargs: Any) -> Any:
        import importlib

        mod = importlib.import_module(module_dotted)
        fn = getattr(mod, func_name)
        res = fn(**kwargs)
        if inspect.isawaitable(res):
            res = await res
        return res if isinstance(res, dict) else {"output": res}

    handler.__name__ = func_name
    return handler


def _detect_funcs_in_file(path: Path) -> List[_tc.ToolSpec]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return []

    module_dotted = path.relative_to(BACKEND_ROOT).with_suffix("").as_posix().replace("/", ".")
    specs: List[_tc.ToolSpec] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        decos = [d for d in node.decorator_list if _is_prism_tool(d)]
        if not decos:
            continue
        meta = {}
        for d in decos:
            meta.update(_decorator_keywords(d))
        docstring = ast.get_docstring(node) or ""
        name = meta.get("name") or node.name
        description = meta.get("description") or docstring.split("\n\n")[0].strip() or node.name
        parameters = meta.get("parameters")
        if parameters is None:
            parameters = _schema_from_fn(node, node)
        specs.append(_tc.ToolSpec(
            name=name,
            description=" ".join(str(description).split()),
            parameters=parameters,
            handler=_make_handler(module_dotted, node.name),
            category=meta.get("category") or "",
            output_summary=meta.get("output_summary") or "",
        ))
    return specs


def scan() -> List[_tc.ToolSpec]:
    specs: List[_tc.ToolSpec] = []
    for root in _scan_root_dirs():
        for path in _iter_py_files(root):
            specs.extend(_detect_funcs_in_file(path))
    return specs


def register_auto_tools() -> int:
    """扫描并注册所有 @prism_tool 工具；返回新注册数量（仅一次生效，重复调用跳过同名）。"""
    count = 0
    for spec in scan():
        if _tc.register_auto(spec) is not None:
            count += 1
    return count


if __name__ == "__main__":
    found = scan()
    print(f"[scanner] found {len(found)} @prism_tool functions:")
    for s in found:
        print(f"  - {s.name}  [{s.category}]  {s.description}")
