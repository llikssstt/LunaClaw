import json
from pathlib import Path

from agent_graph.task_runner import run_task_step
from agent_graph.task_runtime import RUNNABLE_STATUSES, TASK_STORE_PATH, TaskRuntime, now_iso


SCHEDULER_STATE_PATH = Path(__file__).resolve().parents[1] / "storage" / "task_scheduler.json"


class TaskScheduler:
    def __init__(self, state_path=None):
        self.state_path = Path(state_path or SCHEDULER_STATE_PATH)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.state_path.exists():
            self._write({"running": False, "max_steps_per_tick": 1, "updated_at": now_iso(), "last_tick": None})

    def status(self):
        return self._read()

    def start(self, max_steps_per_tick=1):
        state = self._read()
        state.update(
            {
                "running": True,
                "max_steps_per_tick": _normalize_max_steps(max_steps_per_tick),
                "updated_at": now_iso(),
            }
        )
        self._write(state)
        return state

    def stop(self):
        state = self._read()
        state.update({"running": False, "updated_at": now_iso()})
        self._write(state)
        return state

    def tick(self):
        state = self._read()
        if not state.get("running"):
            return {"ok": False, "scheduler": state, "processed": 0, "results": [], "reason": "scheduler_stopped"}

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
        return {"ok": True, "scheduler": state, "processed": len(results), "results": results}

    def _read(self):
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {"running": False, "max_steps_per_tick": 1, "updated_at": now_iso(), "last_tick": None}

    def _write(self, state):
        self.state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _normalize_max_steps(value):
    try:
        return max(1, min(int(value or 1), 20))
    except (TypeError, ValueError):
        return 1
