"""Background task helpers (FastAPI BackgroundTasks + in-process queue)."""
from __future__ import annotations

import threading
from collections.abc import Callable

_tasks: list[dict] = []
_lock = threading.Lock()


def enqueue(name: str, fn: Callable, *args, **kwargs) -> dict:
    """Run fn in background thread; track status for ops."""
    task = {"name": name, "status": "pending", "result": None, "error": None}

    def runner():
        task["status"] = "running"
        try:
            task["result"] = fn(*args, **kwargs)
            task["status"] = "done"
        except Exception as exc:  # noqa: BLE001
            task["error"] = str(exc)
            task["status"] = "failed"

    with _lock:
        _tasks.append(task)
        if len(_tasks) > 100:
            _tasks.pop(0)
    threading.Thread(target=runner, daemon=True).start()
    return task


def recent_tasks(limit: int = 20) -> list[dict]:
    with _lock:
        return list(_tasks[-limit:])
