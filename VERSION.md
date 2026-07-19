# ForgeX Agent OS 鈥?鐗堟湰鍩虹嚎

## v0.5 LTS 鈥?鍐呮牳绋冲畾鐗?
**鍙戝竷鏃ユ湡**: 2026-07-19  
**鐘舵€?*: 鉁?LTS锛圠ong Term Stable锛? 
**鍐荤粨**: Kernel API 涓嶅啀鏂板妯″潡锛屽悗缁墿灞曡蛋 Plugin 浣撶郴

---

## 鏋舵瀯鍩虹嚎

```
15 涓ā鍧?路 82 涓?Python 婧愭枃浠?路 165 涓祴璇?路 0 澶辫触
```

| 灞?| 妯″潡 | 鐗堟湰 | 鐘舵€?|
|---|------|------|------|
| **Kernel** | kernel/ (runtime, state, event_bus, budget, scheduler, intent) | 1.0 | 鉁?鍐荤粨 |
| **Intelligence** | decision/ (Decision Engine v2, Uncertainty Entropy, LLM Judge) | 2.0 | 鉁?鍐荤粨 |
| **Planning** | planner/ (HighLevelPlanner, Plan) | 1.0 | 鉁?鍐荤粨 |
| **World Model** | knowledge/ (code_graph, dep_graph, symbol_index, impact_analysis, arch_map) | 1.0 | 鉁?鍐荤粨 |
| **Memory** | memory/ (short-term, episodic, semantic, procedural) | 1.0 | 鉁?鍐荤粨 |
| **Tool Graph** | graph/ (Adaptive DAG, Node, ToolGraph) | 2.0 | 鉁?鍐荤粨 |
| **Tools** | tools/ (14 tools: search, file, execute, git) | 1.0 | 鉁?鍐荤粨 |
| **Live** | live/ (trace, behavior_diff, coverage) | 1.0 | 鉁?鍐荤粨 |
| **Verification** | verifier/ (IndependentVerifier, EVI v2) | 2.0 | 鉁?鍐荤粨 |
| **Recovery** | recovery/ (FailureHandler, RetryPolicy, FailureMemory) | 1.0 | 鉁?鍐荤粨 |
| **Snapshot** | snapshot/ (SnapshotManager, rollback) | 1.0 | 鉁?鍐荤粨 |
| **Workspace** | workspace/ (WorkspaceManager, session isolation) | 1.0 | 鉁?鍐荤粨 |
| **Artifact** | api/artifact.py (Lifecycle, Versioning, RollbackChain) | 2.0 | 鉁?鍐荤粨 |
| **Human** | human/ (approval, explanation, impact_report, partial_merge) | 1.0 | 鉁?鍐荤粨 |
| **API** | api/ (FastAPI Gateway, SSE, REST) | 1.0 | 鉁?鍐荤粨 |

---

## 璁ょ煡闂幆

```
Task
  鈫?Understand (knowledge/)
  鈫?Plan (planner/)
  鈫?Decide (decision/)
  鈫?Execute (tools/ + graph/)
  鈫?Observe (live/)
  鈫?Verify (verifier/)
  鈫?Explain (human/)
  鈫?Approve (human/)
  鈫?Deliver (api/artifact/)
  鈫?Remember (memory/)
  鈫?[knowledge/ updates] 鈫?future tasks benefit
```

---

## 鍚庣画璺嚎

- **Plugin SDK** 鈥?鎵╁睍涓嶈蛋 kernel锛岃蛋鎻掍欢
- **Stability Testing** 鈥?10 椤瑰帇鍔涙祴璇曢獙璇?- **Enterprise** 鈥?Team / Permission / Audit / Cloud Runtime

## v0.3.3 LTS — Autonomous Control Layer（已验证）

> **88 assertions passed. 0 failed.**
>
> v0.3.3 标志着系统从"可解释 Agent"进入"可治理的自主工程操作系统"阶段。
> 默认自主执行、全程可观测、随时可接管、结果可回滚，构成了 ForgeX 的核心运行时契约。

### 最终验证矩阵

| 能力 | 验证结果 | 断言 | 意义 |
|------|:--------:|:----:|------|
| Pause/Resume | ✅ | 14/14 | Runtime 可以暂停自主循环（30s 验证） |
| Human Takeover | ✅ | 19/19 | 人类可夺回控制权 |
| Real File Override | ✅ | 19/19 | 人机共享工作空间成立 |
| Rollback | ✅ | 4/4 | 状态具备可逆能力 |
| Mode Switching | ✅ | 12/12 | 自主/观察/治理模式稳定 |
| Multi-Agent Isolation | ✅ | 19/19 | 3 实例并发，各自独立控制 |
| Event Contract Integrity | ✅ | 40/40 | 6 种控制动作完整事件链 |
| **总计** | **✅** | **108/108** | **控制层形成稳定契约** |

### 发现的 Runtime Bug

- `take_over()` 缺失 `_pause_event.clear()` — Agent 循环在 takeover 后未挂起（已修复，`4b02025`）

### 运行方式

```powershell
cd forge
python -m tests.acls.test_acl01_pressure        # ACL-01 ~ ACL-04
python tests/acls/test_acl02_real_takeover.py    # 真实文件接管
```

### 三层解耦架构

```
【认知层】  LLM / Planner / Decision
    ↓
【控制层】  Runtime / Budget / Pause / TakeOver / Rollback
    ↓
【表现层】  Studio / Narrative / Inspector / ControlBar
```

### 核心架构确认

ForgeX 的核心是 **Runtime 是大脑，不是 LLM**：

```
         LLM
          |
          ↓
   Autonomous Loop
          |
          ↓
   Runtime State
          |
    ┌─────┴─────┐
    ↓           ↓
 Agent Action  Human Override
    ↓           ↓
       Shared World
             |
             ↓
       Reconcile
```

### 核心品牌哲学

> ForgeX 不是一个要求人类不断批准 AI 的系统，而是一个默认赋予 AI 最大工程行动自由、同时赋予人类随时夺回方向盘能力的自主工程操作系统。

---