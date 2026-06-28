import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from agent_graph.graph import GraphCore
from main import app
from tools import registry as tool_registry


def local_tmp_path():
    path = Path(__file__).resolve().parents[2] / ".pytest_tmp" / "task_runtime" / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def patch_task_store(monkeypatch, tmp_path):
    from agent_graph import task_runtime
    from agent_graph import task_scheduler

    monkeypatch.setattr(task_runtime, "TASK_STORE_PATH", tmp_path / "tasks.json")
    monkeypatch.setattr(task_scheduler, "TASK_STORE_PATH", tmp_path / "tasks.json")
    monkeypatch.setattr(task_scheduler, "SCHEDULER_STATE_PATH", tmp_path / "task_scheduler.json")
    return task_runtime


def test_task_runtime_creates_task_with_steps_and_logs(monkeypatch):
    tmp_path = local_tmp_path()
    task_runtime = patch_task_store(monkeypatch, tmp_path)
    runtime = task_runtime.TaskRuntime()

    task = runtime.create_task("Build a report", session_id="s1")
    runtime.set_plan(task["task_id"], [{"title": "Draft", "status": "pending"}], {"name": "none", "arguments": {}})
    runtime.append_step(task["task_id"], "planner", "completed", "structured plan ready")
    runtime.add_artifact(task["task_id"], "note", {"text": "done"})
    runtime.finish_task(task["task_id"], "completed")

    loaded = runtime.get_task(task["task_id"])
    assert loaded["status"] == "completed"
    assert loaded["steps"][0]["title"] == "Draft"
    assert loaded["logs"][-1]["event"] == "status"
    assert loaded["artifacts"][0]["type"] == "note"


def test_graphcore_returns_task_and_planner_fields(monkeypatch):
    tmp_path = local_tmp_path()
    patch_task_store(monkeypatch, tmp_path)

    result = GraphCore().chat("What is 2 + 3?", "task-graph")

    assert result["task"]["status"] in {"running", "completed"}
    assert result["task"]["steps"]
    assert result["planner_result"]["tool_intent"]["name"] == "calculator"
    assert any(step["agent_name"] == "Planner Agent" for step in result["agent_flow"])


def test_execution_node_uses_generic_tool_intent(monkeypatch):
    tmp_path = local_tmp_path()
    patch_task_store(monkeypatch, tmp_path)
    calls = []

    def fake_execute(tool_call):
        calls.append(tool_call)
        return {"ok": True, "tool": tool_call["name"], "result": {"value": 5}}

    monkeypatch.setattr(tool_registry, "execute_tool", fake_execute)

    result = GraphCore().chat("What is 2 + 3?", "generic-tool")

    assert calls == [{"name": "calculator", "arguments": {"expression": "2 + 3"}}]
    assert result["tool_trace"][0]["tool_call"]["name"] == "calculator"
    assert result["task"]["artifacts"][0]["type"] == "tool_result"


def test_tasks_api_lists_and_reads_tasks(monkeypatch):
    tmp_path = local_tmp_path()
    patch_task_store(monkeypatch, tmp_path)
    client = TestClient(app)

    chat_response = client.post("/chat", json={"message": "What is 2 + 3?", "session_id": "task-api"})
    assert chat_response.status_code == 200
    task_id = chat_response.json()["task"]["task_id"]

    list_response = client.get("/tasks")
    detail_response = client.get(f"/tasks/{task_id}")

    assert list_response.status_code == 200
    assert any(task["task_id"] == task_id for task in list_response.json()["tasks"])
    assert detail_response.status_code == 200
    assert detail_response.json()["task_id"] == task_id


def test_task_runtime_can_mark_next_pending_step(monkeypatch):
    tmp_path = local_tmp_path()
    task_runtime = patch_task_store(monkeypatch, tmp_path)
    runtime = task_runtime.TaskRuntime()
    task = runtime.create_task("Long task", session_id="s1")
    runtime.set_plan(
        task["task_id"],
        [{"title": "First"}, {"title": "Second"}],
        {"name": "none", "arguments": {}},
    )

    step = runtime.next_pending_step(task["task_id"])
    runtime.update_step_status(task["task_id"], step["step_id"], "completed", "first done")

    loaded = runtime.get_task(task["task_id"])
    assert loaded["steps"][0]["status"] == "completed"
    assert loaded["steps"][0]["detail"] == "first done"
    assert loaded["steps"][1]["status"] == "pending"
    assert loaded["logs"][-1]["event"] == "step_status"


def test_run_next_task_step_api_executes_tool_intent_once(monkeypatch):
    tmp_path = local_tmp_path()
    task_runtime = patch_task_store(monkeypatch, tmp_path)
    calls = []

    def fake_execute(tool_call):
        calls.append(tool_call)
        return {"ok": True, "tool": tool_call["name"], "result": {"value": 5}}

    monkeypatch.setattr(tool_registry, "execute_tool", fake_execute)
    runtime = task_runtime.TaskRuntime()
    task = runtime.create_task("Calculate", session_id="task-run-next")
    runtime.set_plan(
        task["task_id"],
        [{"title": "Run calculator"}],
        {"name": "calculator", "arguments": {"expression": "2 + 3"}},
    )
    client = TestClient(app)
    run_response = client.post(f"/tasks/{task['task_id']}/run-next")

    assert run_response.status_code == 200
    task = run_response.json()["task"]
    assert calls == [{"name": "calculator", "arguments": {"expression": "2 + 3"}}]
    assert any(artifact["type"] == "tool_result" for artifact in task["artifacts"])
    assert any(step["status"] == "completed" for step in task["steps"])


def test_run_task_until_idle_api_advances_multiple_steps(monkeypatch):
    tmp_path = local_tmp_path()
    task_runtime = patch_task_store(monkeypatch, tmp_path)
    calls = []

    def fake_execute(tool_call):
        calls.append(tool_call)
        return {"ok": True, "tool": tool_call["name"], "result": {"attempt": len(calls)}}

    monkeypatch.setattr(tool_registry, "execute_tool", fake_execute)
    runtime = task_runtime.TaskRuntime()
    task = runtime.create_task("Loop task", session_id="task-run-loop")
    runtime.set_plan(
        task["task_id"],
        [{"title": "Step one"}, {"title": "Step two"}, {"title": "Step three"}],
        {"name": "calculator", "arguments": {"expression": "2 + 3"}},
    )
    client = TestClient(app)

    response = client.post(f"/tasks/{task['task_id']}/run-until-idle", json={"max_steps": 2})

    assert response.status_code == 200
    payload = response.json()
    assert payload["iterations"] == 2
    assert len(calls) == 2
    assert payload["task"]["steps"][0]["status"] == "completed"
    assert payload["task"]["steps"][1]["status"] == "completed"
    assert payload["task"]["steps"][2]["status"] == "pending"
    assert payload["task"]["status"] == "running"


def test_task_lifecycle_pause_resume_and_cancel_api(monkeypatch):
    tmp_path = local_tmp_path()
    task_runtime = patch_task_store(monkeypatch, tmp_path)
    calls = []

    def fake_execute(tool_call):
        calls.append(tool_call)
        return {"ok": True, "tool": tool_call["name"], "result": {"attempt": len(calls)}}

    monkeypatch.setattr(tool_registry, "execute_tool", fake_execute)
    runtime = task_runtime.TaskRuntime()
    task = runtime.create_task("Lifecycle task", session_id="task-lifecycle")
    runtime.set_plan(
        task["task_id"],
        [{"title": "Step one"}, {"title": "Step two"}],
        {"name": "calculator", "arguments": {"expression": "2 + 3"}},
    )
    client = TestClient(app)

    pause_response = client.post(f"/tasks/{task['task_id']}/pause")
    blocked_response = client.post(f"/tasks/{task['task_id']}/run-next")
    resume_response = client.post(f"/tasks/{task['task_id']}/resume")
    run_response = client.post(f"/tasks/{task['task_id']}/run-next")
    cancel_response = client.post(f"/tasks/{task['task_id']}/cancel")
    cancelled_run_response = client.post(f"/tasks/{task['task_id']}/run-until-idle", json={"max_steps": 2})

    assert pause_response.status_code == 200
    assert pause_response.json()["task"]["status"] == "paused"
    assert blocked_response.status_code == 409
    assert "paused" in blocked_response.json()["detail"]
    assert resume_response.status_code == 200
    assert resume_response.json()["task"]["status"] == "running"
    assert run_response.status_code == 200
    assert len(calls) == 1
    assert cancel_response.status_code == 200
    cancelled = cancel_response.json()["task"]
    assert cancelled["status"] == "cancelled"
    assert cancelled["logs"][-1]["event"] == "status"
    assert cancelled["logs"][-1]["message"] == "cancelled"
    assert cancelled_run_response.status_code == 409
    assert "cancelled" in cancelled_run_response.json()["detail"]


def test_failed_step_can_be_retried_with_attempt_history(monkeypatch):
    tmp_path = local_tmp_path()
    task_runtime = patch_task_store(monkeypatch, tmp_path)
    calls = []

    def fake_execute(tool_call):
        calls.append(tool_call)
        if len(calls) == 1:
            return {"ok": False, "tool": tool_call["name"], "error": {"message": "temporary failure"}}
        return {"ok": True, "tool": tool_call["name"], "result": {"value": 5}}

    monkeypatch.setattr(tool_registry, "execute_tool", fake_execute)
    runtime = task_runtime.TaskRuntime()
    task = runtime.create_task("Retry task", session_id="task-retry")
    runtime.set_plan(
        task["task_id"],
        [{"title": "Run flaky calculator"}],
        {"name": "calculator", "arguments": {"expression": "2 + 3"}},
    )
    client = TestClient(app)

    first_run = client.post(f"/tasks/{task['task_id']}/run-next")
    retry_response = client.post(f"/tasks/{task['task_id']}/steps/step_1/retry")
    second_run = client.post(f"/tasks/{task['task_id']}/run-next")

    assert first_run.status_code == 200
    assert first_run.json()["ok"] is False
    failed_task = first_run.json()["task"]
    assert failed_task["status"] == "failed"
    assert failed_task["steps"][0]["attempts"] == 1
    assert failed_task["steps"][0]["last_error"] == "temporary failure"
    assert retry_response.status_code == 200
    queued_task = retry_response.json()["task"]
    assert queued_task["status"] == "running"
    assert queued_task["steps"][0]["status"] == "pending"
    assert queued_task["steps"][0]["attempts"] == 1
    assert queued_task["logs"][-1]["event"] == "step_retry"
    assert second_run.status_code == 200
    completed_task = second_run.json()["task"]
    assert completed_task["status"] == "completed"
    assert completed_task["steps"][0]["status"] == "completed"
    assert completed_task["steps"][0]["attempts"] == 2
    assert len(calls) == 2


def test_task_scheduler_tick_advances_runnable_tasks_only(monkeypatch):
    tmp_path = local_tmp_path()
    task_runtime = patch_task_store(monkeypatch, tmp_path)
    calls = []

    def fake_execute(tool_call):
        calls.append(tool_call)
        return {"ok": True, "tool": tool_call["name"], "result": {"attempt": len(calls)}}

    monkeypatch.setattr(tool_registry, "execute_tool", fake_execute)
    runtime = task_runtime.TaskRuntime()
    active = runtime.create_task("Active scheduled task", session_id="scheduler")
    runtime.set_plan(
        active["task_id"],
        [{"title": "First active"}, {"title": "Second active"}],
        {"name": "calculator", "arguments": {"expression": "2 + 3"}},
    )
    paused = runtime.create_task("Paused scheduled task", session_id="scheduler")
    runtime.set_plan(
        paused["task_id"],
        [{"title": "Paused step"}],
        {"name": "calculator", "arguments": {"expression": "4 + 4"}},
    )
    runtime.pause_task(paused["task_id"])
    client = TestClient(app)

    start_response = client.post("/tasks/scheduler/start", json={"max_steps_per_tick": 1})
    tick_response = client.post("/tasks/scheduler/tick")
    status_response = client.get("/tasks/scheduler")

    assert start_response.status_code == 200
    assert start_response.json()["scheduler"]["running"] is True
    assert tick_response.status_code == 200
    payload = tick_response.json()
    assert payload["ok"] is True
    assert payload["processed"] == 1
    assert payload["results"][0]["task"]["task_id"] == active["task_id"]
    assert len(calls) == 1
    active_after = client.get(f"/tasks/{active['task_id']}").json()
    paused_after = client.get(f"/tasks/{paused['task_id']}").json()
    assert active_after["steps"][0]["status"] == "completed"
    assert active_after["steps"][1]["status"] == "pending"
    assert paused_after["status"] == "paused"
    assert paused_after["steps"][0]["status"] == "pending"
    assert status_response.status_code == 200
    assert status_response.json()["scheduler"]["running"] is True
