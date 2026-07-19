# ForgeX Agent OS 鈥?宸ヤ綔杩涘害鎶ュ憡

**鏇存柊鏃ユ湡**: 2026-07-19  
**褰撳墠鐗堟湰**: v0.5 LTS锛堝唴鏍稿喕缁擄級  
**娴嬭瘯鎬绘暟**: 205 椤癸紝0 澶辫触

---

## 涓€銆佸凡瀹屾垚浠诲姟

### v0.1 鈥?Tool Calling Agent锛堝熀绾匡級
- [x] Runtime Kernel: 涓诲惊鐜€佺姸鎬佹満銆佷簨浠舵€荤嚎銆侀绠楃鐞嗐€佹剰鍥惧垎绫汇€佽皟搴﹀櫒
- [x] 14 涓熀纭€宸ュ叿: grep銆乬lob銆乺ead_file銆亀rite_file銆乪dit_file銆乧reate_file銆乴ist_dir銆乪xecute銆乬it_status/diff/commit/log/reset
- [x] FastAPI 缃戝叧: REST + SSE 绔偣
- [x] 娴嬭瘯: 40 椤癸紝鍏ㄩ儴閫氳繃

### v0.2 鈥?Runtime Controlled Agent
- [x] Decision Engine: 9 绉嶅喅绛栫被鍨嬶紝EVI + 棰勭畻 + 鐭ヨ瘑缂哄彛缁煎悎鍐崇瓥
- [x] Tool Graph DAG: 鎷撴墤鎺掑簭銆佸墠缃潯浠躲€佸悗缃壇浣滅敤銆佷緷璧栬В鏋?- [x] EVI v2 鍏紡: EVI = 螖Info + 螖Progress + 螖RiskReduction - 伪路Cost
- [x] Artifact Lifecycle: DRAFT鈫扜ENERATED鈫扸ALIDATED鈫扐PPROVED鈫扖OMMITTED鈫扐RCHIVED
- [x] Recovery: FailureHandler锛堜弗閲嶅害鍒嗙骇锛夈€丷etryPolicy锛堟寚鏁伴€€閬匡級
- [x] Workspace: 浼氳瘽闅旂銆佽矾寰勯亶鍘嗛槻鎶?
### v0.3 鈥?Cognitive Agent OS
- [x] 鍥涘眰璁板繂鏋舵瀯:
  - Short-term: 浼樺厛鎰熺煡鍘嬬缉锛?00 token 闄愬埗
  - Context Window: 澶氳疆婊戝姩绐楀彛锛? 绾т紭鍏堢骇琛板噺
  - Episodic: 璺?session 缁忛獙瀛樺偍锛岀浉浼兼绱?  - Semantic: 椤圭洰鐭ヨ瘑鍥捐氨锛屽疄浣?鍏崇郴/鑷姩鎶藉彇
  - Procedural: 鎴愬姛妯″紡搴擄紝閿欒鈫掍慨澶嶆ā寮忓尮閰?- [x] Decision Engine v2: Uncertainty Entropy + Knowledge Coverage + LLM Judge 鍥為€€
- [x] Artifact Versioning: 鐗堟湰閾撅紙parent_id + diff + 鐗堟湰鑷姩閫掑锛?- [x] Adaptive Tool Graph: 澶辫触鑷姩鎻掑叆 debug_node

### v0.4 鈥?Engineering World Model Agent
- [x] Code Graph: AST 浠ｇ爜缁撴瀯鎻愬彇锛堢被/鍑芥暟/鏂规硶/瑁呴グ鍣級
- [x] Dependency Graph: 鏂囦欢绾?import 閾撅紙incoming/outgoing/transitive锛?- [x] Symbol Index: 璺ㄦ枃浠剁鍙峰畾涔夊拰寮曠敤绱㈠紩
- [x] Impact Analysis: 椋庨櫓璇勭骇锛圢ONE鈫扖RITICAL锛夈€佸奖鍝嶆枃浠?API/娴嬭瘯璁＄畻
- [x] Architecture Map: 灞傝瘑鍒紙6 绉嶅眰绫诲瀷锛夈€佽竟鐣屾娴嬨€佸眰闂翠緷璧栨帹鏂?
### v0.5 LTS 鈥?Collaborative Engineering Runtime锛堝唴鏍稿喕缁擄級
- [x] Live Execution: RuntimeSnapshot锛坰tdout/stderr/exit_code 鎹曡幏锛夈€乥efore/after 瀵规瘮
- [x] Behavior Diff: 鍥炲綊妫€娴嬨€佹敼杩涙娴嬨€乿erify_change 瀹夊叏楠岃瘉
- [x] Execution Coverage: 瑕嗙洊鐜囨姤鍛婅В鏋愩€乼raceback 璺緞鎺ㄦ柇
- [x] Human Collaboration:
  - ApprovalManager: 鍒嗙骇瀹℃壒锛坙ow auto-approve / high requires review锛?  - Explainer: 缁撴瀯鍖栧彉鏇磋В閲婏紙what/why/how/impact/alternatives锛?  - Impact Report: 浜虹被鍙 markdown 鎶ュ憡
  - Partial Merge: diff 鍧楃骇鍒€夋嫨鎬у悎骞?- [x] Plugin SDK: ForgePlugin 鎶借薄鍩虹被銆丳luginRegistry銆丳luginSpec
- [x] 10 椤瑰帇鍔涙祴璇? 闀夸换鍔?鎭㈠/骞昏/澶т粨搴?澶氫换鍔?鍐呭瓨/涓栫晫妯″瀷/瀹℃壒/鎴愭湰/绋冲畾

### v0.5 LTS 琛ュ厖
- [x] Apache 2.0 寮€婧愬崗璁?- [x] 鎺ㄩ€佸埌 GitHub: `aliquanhou/ForgeX`
- [x] ForgeX-Studio 鐙珛浠撳簱: `aliquanhou/ForgeX-Studio`锛坴0.1锛? 闈㈡澘锛?- [x] Event Protocol v1: 18 涓ǔ瀹氫簨浠剁被鍨嬶紝Runtime 鈫?Studio SSE 閫氫俊濂戠害
- [x] 闆嗘垚娴嬭瘯: 5 椤?Runtime 鈫?SSE 鍚堢害娴嬭瘯
- [x] 浜嬩欢鍥炴斁 Demo: `forge/demo/event_demo.py`

---

## 浜屻€丟it 浠撳簱

### ForgeX锛圧untime Core锛?```
10 commits 路 18 妯″潡鐩綍 路 205 娴嬭瘯 路 0 澶辫触
master 鈫?https://github.com/aliquanhou/ForgeX
```

### ForgeX-Studio锛堝墠绔?IDE锛?```
1 commit 路 React 19 + Vite + Tailwind
7 闈㈡澘: Timeline/Decision/World/Memory/Tools/Artifact/Plugins
master 鈫?https://github.com/aliquanhou/ForgeX-Studio
```

---

## 涓夈€佸綋鍓嶆ā鍧楀叏鏅紙18 涓ā鍧楋級

| 妯″潡 | 鐩綍 | 鐘舵€?|
|------|------|------|
| Runtime 鏍稿績 | `kernel/` | 鉁?鍐荤粨 v1.0 |
| 鍐崇瓥寮曟搸 | `decision/` | 鉁?鍐荤粨 v2.0 |
| 瑙勫垝鍣?| `planner/` | 鉁?鍐荤粨 v1.0 |
| 涓栫晫妯″瀷 | `knowledge/` | 鉁?鍐荤粨 v1.0 |
| 鍥涘眰璁板繂 | `memory/` | 鉁?鍐荤粨 v1.0 |
| 宸ュ叿鍥?| `graph/` | 鉁?鍐荤粨 v2.0 |
| 14 宸ュ叿 | `tools/` | 鉁?鍐荤粨 v1.0 |
| 杩愯鏃惰拷韪?| `live/` | 鉁?鍐荤粨 v1.0 |
| 楠岃瘉 + EVI | `verifier/` | 鉁?鍐荤粨 v2.0 |
| 鎭㈠ | `recovery/` | 鉁?鍐荤粨 v1.0 |
| 蹇収 | `snapshot/` | 鉁?鍐荤粨 v1.0 |
| 宸ヤ綔鍖?| `workspace/` | 鉁?鍐荤粨 v1.0 |
| 鍒跺搧锛堢敓鍛藉懆鏈?+ 鐗堟湰锛?| `api/artifact.py` | 鉁?鍐荤粨 v2.0 |
| 浜烘満鍗忎綔 | `human/` | 鉁?鍐荤粨 v1.0 |
| API 缃戝叧 | `api/` | 鉁?鍐荤粨 v1.0 |
| Plugin SDK | `plugin/` | 鉁?鍐荤粨 v1.0 |
| **浜嬩欢鍗忚** | **`events/`** | **馃啎 v1.0 鈥?鏂板** |
| **浜嬩欢鍥炴斁 Demo** | **`demo/`** | **馃啎 v0.1 鈥?鏂板** |

---

## 鍥涖€佸緟瑙ｅ喅闂

### 浼樺厛绾?P0 鈥?鑱旇皟闃诲 鉁?宸蹭慨澶?
| 闂 | 瑙ｅ喅 |
|------|------|
| `forge/demo/__init__.py` GBK 缂栫爜鎹熷潖 | 閲嶅啓涓?UTF-8锛宍import forge.demo` 姝ｅ父 鉁?|
| SSE 绔偣 404锛堣矾鐢遍『搴忓啿绐侊級 | `/tasks/events` 绉诲埌 `/{task_id}` 鍓嶏紱绉婚櫎 `event:` 鍓嶇紑锛圫SE 鍛藉悕浜嬩欢涓嶈Е鍙?`onmessage`锛夆渽 |
| Demo 璺ㄨ繘绋?EventBus 闅旂 | 鏂板 `POST /api/demo` 鍚岃繘绋嬭Е鍙戜簨浠跺洖鏀撅紝18 绉嶄簨浠剁粡 SSE 閫佽揪璁㈤槄鑰?鉁?|
| 绔彛涓嶄竴鑷达紙Runtime 8000 / Studio 5173锛?| 缁熶竴 Runtime 鈫?5173锛孲tudio 鈫?5174锛圴ite proxy `/api` 鈫?`localhost:5173`锛夆渽 |
| API 浠诲姟涓嶄骇鐢熶簨浠讹紙鏃?handler锛?| `POST /api/tasks` 鑷姩鍚庡彴鎵ц `Runtime.run()` 鉁?|
| `_execute_action` 缂轰簨浠跺彂甯?| 鏂板 `PHASE_CHANGED`/`TOOL_STARTED`/`TOOL_COMPLETED` 浜嬩欢鍙戝皠 鉁?|
| task_id 涓嶄竴鑷达紙API vs SSE锛?| `run()` 澶嶇敤宸叉湁鐘舵€侊紝涓嶉噸寤?RuntimeState 鉁?|

### 绔埌绔獙璇佺粨鏋?
| 娴嬭瘯 | 缁撴灉 |
|------|:----:|
| 鈶?Demo 浜嬩欢娴侊紙10 绉嶄簨浠讹級 | 鉁?48 鏉′簨浠讹紝鍏ㄩ儴绫诲瀷榻愬叏 |
| 鈶?鐪熷疄浠诲姟鐢熷懡鍛ㄦ湡锛? 绉嶄簨浠讹級 | 鉁?21 鏉′簨浠讹紝`task_started` 鈫?`task_completed` 瀹屾暣闂幆 |
| 鈶?task_id 涓€鑷存€?| 鉁?API 杩斿洖 `dfe57f0e`锛孲SE 浜嬩欢涓€鑷?|
| 鈶?Studio 浠ｇ悊 `/api` 鈫?`:5173` | 鉁?鍋ュ悍妫€鏌ラ€氳繃 |

**鏈嶅姟杩愯**: Runtime(`:5173`) 鈫?SSE 鈫?Studio(`:5174`, proxy 鈫?`:5173`)

### 浼樺厛绾?P1 鈥?Studio v0.2

| 鍔熻兘 | 鎻忚堪 | 鐘舵€?|
|------|------|------|
| Control Bar | Start / Pause / Resume / Stop 浠诲姟鎺у埗 | 馃摑 寰呭疄鐜?|
| Decision Override | 浜虹被瀹℃壒/鍚﹀喅/鏇挎崲鍐崇瓥 | 馃摑 寰呭疄鐜?|
| World Model 浜や簰 | 鐐瑰嚮瀹炰綋鏌ョ湅褰卞搷鍒嗘瀽 | 馃摑 寰呭疄鐜?|

### 浼樺厛绾?P2 鈥?骞冲彴鍖?
| 鍔熻兘 | 鎻忚堪 | 鐘舵€?|
|------|------|------|
| Plugin Marketplace | `forge install <plugin>` CLI | 馃摑 寰呰鍒?|
| Runtime Replay | events.jsonl 鍥炴斁 | 馃摑 寰呰鍒?|
| Multi-Agent | Agent 鍥㈤槦鍗忎綔 | 馃摑 寰呰鍒掞紙v1.0+锛?|

---

## 浜斻€佺増鏈矾绾?
| 鐗堟湰 | 瀹氫綅 | 鐘舵€?|
|------|------|:----:|
| v0.1 | Tool Calling Agent | 鉁?瀹屾垚 |
| v0.2 | Runtime Controlled Agent | 鉁?瀹屾垚 |
| v0.3 | Cognitive Agent OS | 鉁?瀹屾垚 |
| v0.4 | Engineering World Model Agent | 鉁?瀹屾垚 |
| **v0.5 LTS** | **Collaborative Engineering Runtime** | **鉁?褰撳墠 鈥?鍐呮牳鍐荤粨** |
| v0.2 (Studio) | Human Control Plane | 馃摑 涓嬩竴闃舵 |

---

## 鍏€佹灦鏋勮竟鐣?
```
ForgeX Ecosystem

ForgeX-Studio (Human Interface Layer)
    鈫?SSE (Event Protocol v1)
ForgeX Runtime (Cognitive Execution Plane)
    鈫?Plugin SDK
Plugins (Capability Expansion Layer)
```

**鏍稿績鍘熷垯**: Studio 涓嶇洿鎺ヨ鍙?RuntimeState锛屽彧娑堣垂 `events/` 鍗忚灞傚畾涔夌殑浜嬩欢銆?
