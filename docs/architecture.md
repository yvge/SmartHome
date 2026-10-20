# 架构设计说明

本文档补充 README 中的实现细节，便于答辩讲解与二次开发。

## 1. 分层结构

```text
┌──────────────────────────── 浏览器（Vue 3 + Pinia） ────────────────────────────┐
│  总览 / AI 管家 / 设备 / 场景编排 / 知识库 / 运行轨迹                            │
│  HTTP + fetch SSE 解析（POST /chat/stream、/scenes/{id}/run）                    │
└──────────────────────────────────────┬──────────────────────────────────────────┘
                                       │
┌──────────────────────────────────────▼──────────────────────────────────────────┐
│ FastAPI（app/api）                                                               │
│  chat / devices / scenes / rag / system                                          │
│  StreamingResponse(text/event-stream) · CORS · 统一异常                          │
└──────────────────────────────────────┬──────────────────────────────────────────┘
                                       │
┌──────────────────────────────────────▼──────────────────────────────────────────┐
│ 服务层（app/services）                                                           │
│  ChatService        SceneService        SceneManager（校验/CRUD）                │
└──────────────────────────────────────┬──────────────────────────────────────────┘
                                       │
┌──────────────────────────────────────▼──────────────────────────────────────────┐
│ Agent 层（app/agent）                                                            │
│  LangGraph 主图 + 场景子图 · OfflineNLU · Function Calling · Prompt              │
│  RunContext（run_id / seq / 事件队列）                                           │
└───────────────┬──────────────────────────────┬──────────────────────────────────┘
                │                              │
┌───────────────▼──────────────┐  ┌────────────▼─────────────────────────────────┐
│ RAG（app/rag）               │  │ 设备层（app/devices + core/simulator）       │
│ Embedding + 向量库           │  │ DeviceRegistry · 能力 Schema · 模拟器        │
│ Milvus / LocalVectorStore    │  │ EventBus → /system/events                    │
└───────────────┬──────────────┘  └────────────┬─────────────────────────────────┘
                │                              │
          ┌─────▼─────┐                  ┌─────▼─────┐
          │ SQLite    │                  │ 演示设备   │
          │ 会话/场景 │                  │ 20 台     │
          │ 语料/轨迹 │                  └───────────┘
          └───────────┘
```

## 2. 主图状态

`AgentState` 中关键字段：

| 字段 | 说明 |
| --- | --- |
| `user_input` | 当前用户输入 |
| `history` | 最近 8 条消息（来自 SQLite） |
| `last_devices` | 上一轮目标设备，用于「再亮一点」等指代 |
| `pending` | 待澄清问题（候选设备、动作与参数） |
| `retrieval` | RAG 召回的意图与知识片段 |
| `intent` | 结构化意图（类型、置信度、动作列表、目标设备） |
| `tool_calls` / `tool_results` | 规划出的工具调用与真实执行结果 |
| `verification` | 执行后的设备状态校验 |
| `scene_result` | 场景执行结果 |
| `response` / `status` / `error` | 最终回复与状态 |

### 路由

```text
understand ──control/query──▶ plan ──▶ guard ──通过──▶ execute ──▶ verify ──▶ respond
     │                                   └──无效──▶ fallback ─────────────────▶ respond
     ├──scene──▶ scene（子图）────────────────────────────────────────────────▶ respond
     └──chat/knowledge/clarify────────────────────────────────────────────────▶ respond
```

`guard` 返回空调用集合时走 `fallback`，保证错误指令也会得到可读回复。

## 3. 场景子图

```text
load ──▶ conditions ──不满足且非可选──▶ END(skipped)
              │
              ▼
            plan（按 when 条件过滤动作）
              │
              ▼
      ┌──▶ execute（每次执行一个动作）
      │        │
      │        ├── 还有动作 ──▶ execute
      │        └── 关键动作失败 ──▶ fallback ──▶ verify
      └────────┘
              verify（逐动作回读设备状态）
              ▼
             END
```

- `delay_ms` 控制动作节奏，SSE 前端可以清晰看到逐步联动；
- `critical` 标记关键动作，失败时不再继续剩余动作，直接进入兜底；
- `when` 是单个动作的条件，例如「温度 ≥ 25.5°C 才开空调」；
- `verify` 会校验实际设备属性是否等于期望值，不一致时降级为 `partial`。

## 4. 意图解析策略

1. 先做两路 RAG 检索（意图 Top-5、知识 Top-3），合并后按分数排序；
2. LLM 可用时：把设备目录、最近对话、pending 澄清、环境、场景与召回示例一起放入 Prompt，要求输出固定 JSON；
3. 对 LLM JSON 做设备 ID、场景 ID、动作合法性校验；任何字段不合法则弃用；
4. LLM 不可用/超时/返回非法时：使用 `OfflineNLU`，覆盖房间、设备别名、代词、方向增量、多指令拆分、歧义澄清、场景与知识问答；
5. 最终统一转换成 `ParsedIntent`，后续节点不关心来源。

### 规则解析的关键处理

- 房间/设备别名：客厅、主卧、书房、阳台……「主灯」「床头灯」「灯带」；
- 多指令：按逗号/分号/「然后/接着/同时」拆分，短参数片段会回并到前一句；
- 参数合并：同一设备上的「开灯 + 亮度 80%」合并为一次 `light_brightness_set`；
- 方向增量：「亮一点」「调低两度」基于当前设备状态计算目标值；
- 歧义：多台同类型设备且无房间/上下文时返回 `clarify`，并在 `pending` 中保存动作与候选；
- 代词：「它 / 那个 / 再……」优先使用 `last_devices` 中的设备；
- 上下文：`last_devices` 通过 LangGraph checkpointer 与每轮 state 传递，实现多轮控制。

## 5. 事件协议

所有 Agent 事件都包含：`type`、`run_id`、`seq`、`ts`。

| 事件 | 负载要点 |
| --- | --- |
| `run_start` | session_id、kind、mode、assistant |
| `node_start` | node、label |
| `node_end` | node、duration_ms、summary |
| `retrieval` | intents、knowledge、latency_ms、backend |
| `intent` | intent 对象、label、notes |
| `plan` | tool_calls、source（llm/rule） |
| `guard` | passed、blocked、warnings |
| `tool_call` / `tool_result` | call_id、name、args、ok、message、device |
| `verification` | items、mismatches |
| `scene_start` / `scene_step` / `scene_step_result` / `scene_condition` / `scene_fallback` / `scene_done` | 场景执行过程 |
| `token` / `response` | 流式文本与最终完整回复 |
| `notice` / `error` | 降级提示与可恢复错误 |
| `done` | status、execution_id、message_id、duration_ms、usage |

前端 `streamPost` 逐帧解析，`ChatStore.handleEvent` 将事件映射到消息对象；`RunContext` 同时保留内存 trace，用于写库。

## 6. 数据表

| 表 | 用途 |
| --- | --- |
| `devices` | 设备实例、属性、能力缓存 |
| `scenes` | 内置/自定义场景、条件、步骤、兜底 |
| `sessions` / `messages` | 会话与消息 |
| `executions` | 每次运行的意图、工具调用、trace、结果、状态与耗时 |
| `kb_entries` | 意图示例与知识问答语料 |
| `app_meta` | 种子版本等元数据 |

SQLite 使用 WAL 模式，读写由 `Database` 的 `RLock` 串行化，保证 FastAPI 异步环境下的安全。

## 7. 关键取舍

| 问题 | 选择 | 原因 |
| --- | --- | --- |
| 没有真实硬件 | 设备注册表 + 物理模拟 | 演示可重复、可注入离线/故障，面试时也能讲清接入边界 |
| 没有 API Key | 规则 NLU + 本地哈希向量 | 任何机器可运行，离线也能展示完整链路 |
| 向量库 | Milvus 优先，本地降级 | 兼顾简历技术点与演示可靠性 |
| 场景执行 | LangGraph 子图 | 条件、循环、兜底、校验都是真实图节点，而非硬编码函数 |
| 状态推送 | 单一 EventBus | 对话 trace 与全屋状态互不耦合，前端可分别订阅 |
| 持久化 | SQLite | 零部署；生产可平滑替换 PostgreSQL |

## 8. 可扩展点

1. 新增设备：在 `devices/specs.py` 增加类型与种子，工具 Schema、控制面板与场景编辑器自动生效；
2. 接入真实协议：实现 `DeviceAdapter`（MQTT/HTTP），替换 `DeviceRegistry.apply`；
3. 换向量库：实现 `BaseVectorStore` 并调整工厂函数；
4. 定时场景：复用场景子图，由 APScheduler 触发；
5. 多用户：会话与设备按 user_id 隔离，补 JWT 与 RBAC。
