from pathlib import Path


_TESTS_DIR = Path(__file__).parent

# These are manual/live integration scripts. Keeping them out of pytest
# collection avoids network/browser side effects during local quality checks.
collect_ignore = [
    str(path)
    for path in _TESTS_DIR.glob("test_*.py")
    if path.name != "test_manual_scripts_collection.py"
]
collect_ignore.extend(str(path) for path in (_TESTS_DIR / "config").glob("test_*.py"))
collect_ignore.extend(str(path) for path in (_TESTS_DIR / "integration").glob("test_*.py"))
