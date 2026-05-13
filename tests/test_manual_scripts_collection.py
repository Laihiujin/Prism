import pytest


def test_manual_scripts_are_excluded_from_pytest_collection():
    pytest.skip("Root tests/ contains manual live scripts; run them directly when needed.")
