from __future__ import annotations

import os
import sys
from pathlib import Path
from celery import Celery

# Add syn_backend to Python path for myUtils imports
# This ensures myUtils can be imported even when PYTHONPATH isn't set
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent  # Go up from fastapi_app/tasks/ to syn_backend/
BACKEND_DIR_STR = str(BACKEND_DIR).replace('\\', '\\\\')  # Normalize Windows path

# Print debug info
print(f"[Celery Init] Current file: {__file__}")
print(f"[Celery Init] BACKEND_DIR: {BACKEND_DIR}")
print(f"[Celery Init] BACKEND_DIR_STR: {BACKEND_DIR_STR}")
print(f"[Celery Init] sys.path before: {sys.path[:3]}")

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
    print(f"[Celery Init] Added {BACKEND_DIR} to sys.path")
else:
    print(f"[Celery Init] {BACKEND_DIR} already in sys.path")

print(f"[Celery Init] sys.path after: {sys.path[:3]}")

# Test import
try:
    import myUtils
    print(f"[Celery Init] SUCCESS: myUtils import successful")
except ImportError as e:
    print(f"[Celery Init] FAILED: myUtils import failed: {e}")

from fastapi_app.core.config import resolved_celery_broker_url, resolved_celery_result_backend

# Fix for Celery 5.5.x Windows thread-local storage bug
os.environ.setdefault('FORKED_BY_MULTIPROCESSING', '1')

celery_app = Celery(
    "synapse",
    broker=resolved_celery_broker_url(),
    backend=resolved_celery_result_backend(),
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=False,
    broker_connection_retry_on_startup=True,
    # Ensure non-default task modules are loaded by the worker.
    include=["fastapi_app.tasks.publish_tasks"],
    # Worker pool configuration for Windows
    # Use threads to enable concurrency on Windows (solo forces serial execution).
    worker_pool="threads",
    worker_pool_restarts=True,
    worker_prefetch_multiplier=1,  # Keep prefetch low to avoid task hoarding
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks to prevent memory leaks
)
