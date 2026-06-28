# V-Agent

V-Agent is a general FastAPI + Vue agent system. The default `/chat` runtime is `GraphCore`, a LangGraph-based multi-agent flow that combines memory retrieval, Skill matching, Skill Pack resource reading, tool execution traces, image input, and final response generation.

The legacy `AgentCore` is still available with `AGENT_RUNTIME=legacy`.

## Features

- LangGraph `GraphCore` runtime with Agent Flow tracing.
- Memory RAG through `MemoryCore` and `/memory` APIs.
- Skill Pack installation, lifecycle management, and resource viewing.
- Skill Resource Reader for safe text resource search/read inside a Skill root.
- Tool Store and Permission Review for approved tool installation.
- Tool Trace, Sources, Active Skills, Skill Trace, and Agent Flow in chat output.
- Image upload with `file_id` attachments; server paths are stored only in `uploads_index.json`.
- Mock LLM mode when no `LLM_API_KEY` is configured.

## Run

```powershell
cd backend
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

```powershell
cd frontend
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

## Runtime

Default:

```powershell
$env:AGENT_RUNTIME="graph"
```

Legacy:

```powershell
$env:AGENT_RUNTIME="legacy"
```

LLM settings:

```powershell
$env:LLM_API_KEY="..."
$env:LLM_BASE_URL="https://api.openai.com/v1"
$env:LLM_MODEL="gpt-4o-mini"
```

## Demo Flow

1. Ask V-Agent to install a web reading tool.
2. Review permissions in Permission Review and approve.
3. Confirm `web_reader` appears in Tool Store.
4. Ask: `use web_reader to summarize this page: https://example.com`.
5. Inspect Tool Trace, Sources, and Agent Flow.
6. Install or view a Skill Pack, then ask a query matching its triggers.
7. Inspect Active Skills, Skill Trace, and Skill resource results.
8. Upload an image and ask V-Agent to analyze it.

## Safety Notes

- Unknown downloaded scripts are not executed.
- MCP is not connected in this phase.
- Tool execution is limited to approved demo tools.
- Skill resources are searched/read as text only and constrained to their Skill root.
- Runtime files are ignored: uploads, installed tool registry, approvals, installed packages, generated Skills, and logs.

## Test

```powershell
python -m pytest backend\tests -q
```

```powershell
cd frontend
npm run build
```

If Vite/esbuild fails in a sandbox with `spawn EPERM`, run the same build command outside the sandbox.
