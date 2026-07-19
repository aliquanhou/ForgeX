# ForgeX Agent OS — 版本基线

## v0.5 LTS — 内核稳定版

**发布日期**: 2026-07-19  
**状态**: ✅ LTS（Long Term Stable）  
**冻结**: Kernel API 不再新增模块，后续扩展走 Plugin 体系

---

## 架构基线

```
15 个模块 · 82 个 Python 源文件 · 165 个测试 · 0 失败
```

| 层 | 模块 | 版本 | 状态 |
|---|------|------|------|
| **Kernel** | kernel/ (runtime, state, event_bus, budget, scheduler, intent) | 1.0 | ✅ 冻结 |
| **Intelligence** | decision/ (Decision Engine v2, Uncertainty Entropy, LLM Judge) | 2.0 | ✅ 冻结 |
| **Planning** | planner/ (HighLevelPlanner, Plan) | 1.0 | ✅ 冻结 |
| **World Model** | knowledge/ (code_graph, dep_graph, symbol_index, impact_analysis, arch_map) | 1.0 | ✅ 冻结 |
| **Memory** | memory/ (short-term, episodic, semantic, procedural) | 1.0 | ✅ 冻结 |
| **Tool Graph** | graph/ (Adaptive DAG, Node, ToolGraph) | 2.0 | ✅ 冻结 |
| **Tools** | tools/ (14 tools: search, file, execute, git) | 1.0 | ✅ 冻结 |
| **Live** | live/ (trace, behavior_diff, coverage) | 1.0 | ✅ 冻结 |
| **Verification** | verifier/ (IndependentVerifier, EVI v2) | 2.0 | ✅ 冻结 |
| **Recovery** | recovery/ (FailureHandler, RetryPolicy, FailureMemory) | 1.0 | ✅ 冻结 |
| **Snapshot** | snapshot/ (SnapshotManager, rollback) | 1.0 | ✅ 冻结 |
| **Workspace** | workspace/ (WorkspaceManager, session isolation) | 1.0 | ✅ 冻结 |
| **Artifact** | api/artifact.py (Lifecycle, Versioning, RollbackChain) | 2.0 | ✅ 冻结 |
| **Human** | human/ (approval, explanation, impact_report, partial_merge) | 1.0 | ✅ 冻结 |
| **API** | api/ (FastAPI Gateway, SSE, REST) | 1.0 | ✅ 冻结 |

---

## 认知闭环

```
Task
  ↓
Understand (knowledge/)
  ↓
Plan (planner/)
  ↓
Decide (decision/)
  ↓
Execute (tools/ + graph/)
  ↓
Observe (live/)
  ↓
Verify (verifier/)
  ↓
Explain (human/)
  ↓
Approve (human/)
  ↓
Deliver (api/artifact/)
  ↓
Remember (memory/)
  ↓
[knowledge/ updates] → future tasks benefit
```

---

## 后续路线

- **Plugin SDK** — 扩展不走 kernel，走插件
- **Stability Testing** — 10 项压力测试验证
- **Enterprise** — Team / Permission / Audit / Cloud Runtime
