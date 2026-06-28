from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from agent.agent_core import AgentCore
from agent.memory_core import MemoryCore
from agent.memory import MemoryStore
from agent.self_evolution import SelfEvolutionCore
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


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat(request: ChatRequest):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="message is required")
    return AgentCore().chat(request.message, request.session_id)


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
