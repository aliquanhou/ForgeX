# Forge Agent OS

**Runtime-Driven Autonomous Engineering System**

Forge 不是一个聊天机器人。它是**第一个以 Runtime 为产品核心、真正具备工程交付能力的国产 Agent OS**。

## Architecture

```
User → Runtime → LLM (Decision) → Runtime (Validate/Budget/Rollback) → Tools

LLM 负责：思考下一步
Runtime 负责：控制整个系统
```

### Core Modules

| Module | Responsibility |
|--------|---------------|
| **Runtime Kernel** | Main loop, state machine, event bus, budget, scheduler |
| **Planner** | High-level plan generation from user goals |
| **Tool Graph** | All tools (search, read, write, execute, git) |
| **Verifier** | Independent verification — prevents self-delusion |
| **EVI Engine** | Evidence Intelligence — measures tool call effectiveness |
| **Snapshot** | File-level state capture and rollback |
| **State Compressor** | Compact LLM context — prevents long task drift |
| **Artifact Committer** | Delivery guarantees — task not done until artifact exists |

## Quick Start

```bash
# Install
pip install forge/

# Config (optional)
cp .env .env.local
# Edit FORGE_LLM_API_KEY

# Start server
python -m forge.main

# Or run a task directly
python -m forge.main run --task "explore the codebase and summarize architecture"
```

## API

```bash
# Create task
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"goal": "explore this project"}'

# Stream events (SSE)
curl -N http://localhost:8000/api/tasks/<task_id>/events

# List tasks
curl http://localhost:8000/api/tasks

# Health check
curl http://localhost:8000/api/health

# List tools
curl http://localhost:8000/api/tools
```

## Design Principles

1. **LLM is not the brain — Runtime is the brain**
2. **State ≠ Chat History** — Never feed full conversation back to the model
3. **Every task produces an artifact** — Task ends with file/test/commit, not "model says done"
4. **EVI drives decisions** — If tool calls produce no evidence, force finalize

## Moat

The 4 modules that make Forge defensible:
- **State Compressor** — Long tasks never drift
- **Budget + EVI** — Agent knows when to stop
- **Independent Verifier** — Results are trustworthy, not self-congratulatory
- **Snapshot / Rollback** — AI can safely modify production code

## License

MIT
