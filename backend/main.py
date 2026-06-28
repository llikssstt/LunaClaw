import os
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from agent.agent_core import AgentCore
from agent_graph.graph import GraphCore
from agent.memory_core import MemoryCore
from agent.memory import MemoryStore
from agent.self_evolution import SelfEvolutionCore
from tool_system.installer import approve_install, install_tool
from tool_system.manager import ToolManager
from tool_system.sandbox_runner import run_installed_tool
from tools.skill_installer_tool import (
    delete_skill,
    disable_skill,
    enable_skill,
    install_skill,
    list_skill_resources,
    list_skills as list_installed_skills,
    read_skill,
    read_skill_resource,
)
from tools.todo_tool import TodoStore


app = FastAPI(title="LunaClaw Companion Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    attachments: List[Dict[str, Any]] = []


class MemoryCreateRequest(BaseModel):
    content: str
    category: str = "user_profile"
    importance: float = 0.7
    source: str = "manual"


class MemoryUpdateRequest(BaseModel):
    content: Optional[str] = None
    category: Optional[str] = None
    importance: Optional[float] = None
    status: Optional[str] = None


class SkillInstallRequest(BaseModel):
    url: str
    skill_id: Optional[str] = None


class ToolSearchRequest(BaseModel):
    query: str = ""


class ToolInstallRequest(BaseModel):
    tool_id: str
    source: str = "market"


class ToolApprovalRequest(BaseModel):
    approved: bool


class ToolRunRequest(BaseModel):
    tool_name: str = "fetch_page"
    arguments: Dict[str, Any] = {}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat(request: ChatRequest):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="message is required")
    if os.getenv("AGENT_RUNTIME", "graph").strip().lower() == "legacy":
        return AgentCore().chat(request.message, request.session_id)
    return GraphCore().chat(request.message, request.session_id, attachments=request.attachments)


@app.get("/tools")
def tools():
    return ToolManager().list_available_tools()


@app.get("/tools/market")
def tool_market():
    return {"tools": ToolManager().list_market_tools()}


@app.get("/tools/installed")
def installed_tools():
    return {"tools": ToolManager().list_installed_tools()}


@app.post("/tools/search")
def search_tools(request: ToolSearchRequest):
    return {"tools": ToolManager().search_tools(request.query)}


@app.post("/tools/install")
def install_tool_endpoint(request: ToolInstallRequest):
    try:
        return install_tool(request.tool_id, request.source)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/tools/approve/{approval_id}")
def approve_tool_endpoint(approval_id: str, request: ToolApprovalRequest):
    result = approve_install(approval_id, request.approved)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.post("/tools/{tool_id}/enable")
def enable_tool_endpoint(tool_id: str):
    try:
        return ToolManager().enable_tool(tool_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="tool not found")


@app.post("/tools/{tool_id}/disable")
def disable_tool_endpoint(tool_id: str):
    try:
        return ToolManager().disable_tool(tool_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="tool not found")


@app.post("/tools/{tool_id}/run")
def run_tool_endpoint(tool_id: str, request: ToolRunRequest):
    return run_installed_tool(tool_id, request.tool_name, request.arguments)


@app.post("/uploads/image")
def upload_image(file: UploadFile = File(...)):
    content_type = file.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="only image uploads are supported")
    upload_dir = Path(__file__).resolve().parent / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "").suffix.lower()[:12]
    file_id = f"img_{uuid.uuid4().hex[:16]}"
    path = upload_dir / f"{file_id}{suffix}"
    data = file.file.read()
    max_bytes = 8 * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(status_code=400, detail="image too large")
    path.write_bytes(data)
    return {
        "ok": True,
        "file_id": file_id,
        "filename": file.filename,
        "content_type": content_type,
        "size": len(data),
        "path": str(path),
        "type": "image",
    }


@app.get("/memory")
def list_memory():
    return MemoryCore().list_memories()


@app.post("/memory")
def create_memory(request: MemoryCreateRequest):
    if not request.content.strip():
        raise HTTPException(status_code=400, detail="content is required")
    try:
        return MemoryCore().write_memory(request.content, request.category, request.importance, request.source)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.put("/memory/{memory_id}")
def update_memory(memory_id: str, request: MemoryUpdateRequest):
    try:
        return MemoryCore().update_memory(
            memory_id,
            content=request.content,
            category=request.category,
            importance=request.importance,
            status=request.status,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="memory not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.delete("/memory/{memory_id}")
def delete_memory(memory_id: str):
    try:
        return MemoryCore().delete_memory(memory_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="memory not found")


@app.get("/memory/search")
def search_memory(query: str, top_k: int = 5):
    return MemoryCore().retriever.retrieve(query, top_k=top_k)


@app.get("/memory/logs")
def memory_logs(limit: int = 100):
    return MemoryCore().list_logs(limit=limit)


@app.get("/evolution/logs")
def evolution_logs(limit: int = 100):
    return SelfEvolutionCore().list_logs(limit=limit)


@app.get("/evolution/skills")
def evolution_skills():
    return SelfEvolutionCore().list_skills()


@app.post("/evolution/rollback/{operation_id}")
def rollback_evolution(operation_id: str):
    try:
        return SelfEvolutionCore().rollback(operation_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="evolution operation not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/skills")
def skills():
    return list_installed_skills()


@app.post("/skills/install")
def install_skill_endpoint(request: SkillInstallRequest):
    result = install_skill(request.url, request.skill_id)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get("/skills/{skill_id}/resources")
def skill_resources(skill_id: str):
    result = list_skill_resources(skill_id)
    if not result.get("ok"):
        raise HTTPException(status_code=_skill_error_status(result), detail=result["error"])
    return result


@app.get("/skills/{skill_id}/resources/{resource_path:path}")
def skill_resource(skill_id: str, resource_path: str, max_chars: int = 8000):
    result = read_skill_resource(skill_id, resource_path, max_chars=max_chars)
    if not result.get("ok") and (result.get("error") or {}).get("code") not in {"unsupported_binary"}:
        raise HTTPException(status_code=_skill_error_status(result), detail=result["error"])
    return result


@app.get("/skills/{skill_id}")
def skill_detail(skill_id: str):
    result = read_skill(skill_id)
    if not result.get("ok"):
        raise HTTPException(status_code=_skill_error_status(result), detail=result["error"])
    return result


@app.post("/skills/{skill_id}/enable")
def enable_skill_endpoint(skill_id: str):
    result = enable_skill(skill_id)
    if not result.get("ok"):
        raise HTTPException(status_code=_skill_error_status(result), detail=result["error"])
    return result


@app.post("/skills/{skill_id}/disable")
def disable_skill_endpoint(skill_id: str):
    result = disable_skill(skill_id)
    if not result.get("ok"):
        raise HTTPException(status_code=_skill_error_status(result), detail=result["error"])
    return result


@app.delete("/skills/{skill_id}")
def delete_skill_endpoint(skill_id: str):
    result = delete_skill(skill_id)
    if not result.get("ok"):
        raise HTTPException(status_code=_skill_error_status(result), detail=result["error"])
    return result


def _skill_error_status(result):
    code = (result.get("error") or {}).get("code")
    if code == "skill_not_found":
        return 404
    return 400


@app.get("/todos")
def list_todos():
    return TodoStore().list()
