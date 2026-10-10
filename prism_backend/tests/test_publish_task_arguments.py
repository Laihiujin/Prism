import ast
import inspect
import unittest
from pathlib import Path

class PublishTaskArgumentsTest(unittest.TestCase):
    def test_payload_envelope(self):
        root = Path(__file__).parents[1]
        worker = ast.parse((root / "fastapi_app/tasks/publish_tasks.py").read_text(encoding="utf-8"))
        task = next(n for n in worker.body if isinstance(n, ast.FunctionDef) and n.name == "publish_single_task")
        signature = inspect.Signature([inspect.Parameter(a.arg, inspect.Parameter.POSITIONAL_OR_KEYWORD) for a in task.args.args[1:]])
        service = ast.parse((root / "fastapi_app/api/v1/publish/services.py").read_text(encoding="utf-8"))
        checked = 0
        for node in ast.walk(service):
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if isinstance(key, ast.Constant) and key.value == "kwargs":
                        self.assertIsInstance(value, ast.Dict)
                        signature.bind(**{k.value: {"batch_id": "test"} for k in value.keys})
                        checked += 1
        self.assertEqual(checked, 2)

if __name__ == "__main__":
    unittest.main()
