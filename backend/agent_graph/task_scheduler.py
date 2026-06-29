import json
import threading
import time
from pathlib import Path

from agent_graph.task_runner import run_task_step
from agent_graph.task_runtime import RUNNABLE_STATUSES, TASK_STORE_PATH, TaskRuntime, now_iso


SCHEDULER_STATE_PATH = Path(__file__).resolve().parents[1] / "storage" / "task_scheduler.json"
_worker_lock = threading.Lock()
_worker_thread = None
_worker_state_path = None
_worker_stop_event = threading.Event()


class TaskScheduler:
    def __init__(self, state_path=None):
        self.state_path = Path(state_path or SCHEDULER_STATE_PATH)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.state_path.exists():
            self._write(_default_state())

    def status(self):
        return self._with_worker_state(self._read())

    def start(self, max_steps_per_tick=1, tick_interval_seconds=2.0):
        state = self._read()
        state.update(
            {
                "running": True,
                "max_steps_per_tick": _normalize_max_steps(max_steps_per_tick),
                "tick_interval_seconds": _normalize_interval(tick_interval_seconds),
                "updated_at": now_iso(),
            }
        )
        self._write(state)
        self.start_worker()
        return self._with_worker_state(state)

    def stop(self):
        state = self._read()
        state.update({"running": False, "updated_at": now_iso()})
        self._write(state)
        self.stop_worker()
        return self._with_worker_state(state)

    def start_worker(self):
        global _worker_thread, _worker_state_path
        with _worker_lock:
            if _worker_thread and _worker_thread.is_alive() and _worker_state_path == self.state_path:
                return
            if _worker_thread and _worker_thread.is_alive():
                _worker_stop_event.set()
                _worker_thread.join(timeout=1.0)
            _worker_stop_event.clear()
            _worker_state_path = self.state_path
            _worker_thread = threading.Thread(target=_worker_loop, name="lunaclaw-task-scheduler", daemon=True)
            _worker_thread.start()

    def stop_worker(self, timeout=1.0):
        global _worker_thread, _worker_state_path
        with _worker_lock:
            thread = _worker_thread
            _worker_stop_event.set()
        if thread and thread.is_alive():
            thread.join(timeout=timeout)
        if not thread or not thread.is_alive():
            _worker_state_path = None

    def tick(self):
        state = self._read()
        if not state.get("running"):
            return {
                "ok": False,
                "scheduler": self._with_worker_state(state),
                "processed": 0,
                "results": [],
                "reason": "scheduler_stopped",
            }

        results = []
        max_steps = _normalize_max_steps(state.get("max_steps_per_tick", 1))
        for task in TaskRuntime().list_tasks():
            if len(results) >= max_steps:
                break
            if task.get("status") not in RUNNABLE_STATUSES:
                continue
            if not any(step.get("status") == "pending" for step in task.get("steps", [])):
                continue
            results.append(run_task_step(task["task_id"]))

        state["last_tick"] = now_iso()
        state["updated_at"] = now_iso()
        self._write(state)
        return {"ok": True, "scheduler": self._with_worker_state(state), "processed": len(results), "results": results}

    def _read(self):
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return _default_state()

    def _write(self, state):
        self.state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _with_worker_state(self, state):
        state = dict(state or {})
        state["worker_running"] = bool(_worker_thread and _worker_thread.is_alive())
        return state


def _worker_loop():
    while not _worker_stop_event.is_set():
        scheduler = TaskScheduler()
        state = scheduler._read()
        if not state.get("running"):
            break
        interval = _normalize_interval(state.get("tick_interval_seconds", 2.0))
        if _worker_stop_event.wait(interval):
            break
        scheduler.tick()


def _normalize_max_steps(value):
    try:
        return max(1, min(int(value or 1), 20))
    except (TypeError, ValueError):
        return 1


def _normalize_interval(value):
    try:
        return max(0.01, min(float(value or 2.0), 60.0))
    except (TypeError, ValueError):
        return 2.0


def _default_state():
    return {
        "running": False,
        "max_steps_per_tick": 1,
        "tick_interval_seconds": 2.0,
        "updated_at": now_iso(),
        "last_tick": None,
    }
