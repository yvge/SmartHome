# 智慧居 · 智能家居 AI Agent 使用手册

> 适用版本：v1.0.0（竞赛演示版）  
> 更新日期：2026-10-20  
> 项目根目录：`智能家居AI agent平台/`

这本手册面向第一次接触项目的人，重点说明四件事：

1. 项目有哪些运行模式，离线模式和在线模式有什么区别；
2. 如何配置大模型 API Key，以及配置后如何确认生效；
3. 如何用 Docker 启动整个项目（含可选的 Milvus）；
4. 有没有“居家/回家、离家”这类场景，怎么触发、怎么演示。

---

## 目录

- [一、先把“模式”说清楚](#一先把模式说清楚)
- [二、配置 API Key](#二配置-api-key)
- [三、用 Docker 启动](#三用-docker-启动)
- [四、回家 / 离家等场景模式](#四回家--离家等场景模式)
- [五、日常使用与演示速查](#五日常使用与演示速查)
- [六、常见问题排查](#六常见问题排查)
- [七、配置项速查](#七配置项速查)

---

## 一、先把“模式”说清楚

项目里“模式”有两个层面的含义，不要混淆：

### 1.1 运行模式：离线规则模式 / 在线大模型模式

这是整个后端服务的运行方式，由 `backend/.env` 中是否配置了可用的 `LLM_API_KEY` 决定。

| | 离线规则模式（默认） | 在线大模型模式（LLM 模式） |
| --- | --- | --- |
| 触发条件 | `LLM_API_KEY` 为空，或 `LLM_PROVIDER=offline` | `LLM_API_KEY` 非空，且 `LLM_PROVIDER=openai` |
| 意图理解 | 内置中文规则 + RAG 检索 | 大模型输出结构化 JSON，RAG 检索作为参考 |
| 工具规划 | 规则映射为 Function Calling 调用 | 大模型选择工具，后端过滤目标设备 |
| 回复生成 | 本地模板生成 | 大模型流式生成 |
| 是否需要联网 | 不需要 | 需要能访问所配置的 API |
| 界面显示 | 侧边栏「离线规则」、消息标记「规则引擎」 | 侧边栏「LLM 在线」、显示模型名称 |
| 适合场景 | 无 Key、无网络、比赛现场演示 | 希望对话更自然、更灵活 |

**在线模式不是“纯大模型”模式。** 它是「LLM 优先 + 规则兜底」：

- 模型返回不完整、超时、限流、Key 失效时，会自动回退到离线规则解析；
- 场景执行、设备控制、参数校验、异常兜底仍然由后端的 LangGraph 和工具层完成；
- 因此即使模型服务临时不可用，演示也不会中断，只会在轨迹里出现一条回退提示。

### 1.2 RAG 的两个独立选项

RAG 不改变“离线/在线”的划分，它有自己的两组配置：

| 选项 | 可取值 | 默认 | 说明 |
| --- | --- | --- | --- |
| Embedding | `local` / `openai` | `local` | `local` 是零依赖的字符 n-gram 特征哈希（512 维）；`openai` 调用 OpenAI 兼容的 embeddings 接口 |
| 向量库 | `auto` / `local` / `milvus` | `auto` | `auto` 先尝试 Milvus，连不上自动降级本地内存向量库；`milvus` 强制尝试 Milvus，失败仍会降级保证可用 |

所以常见的组合有：

- **完全离线**：离线规则 + 本地 Embedding + 本地向量库（默认，不需要任何外部服务）；
- **LLM + 本地 RAG**：配置大模型 Key，但向量检索仍在本机完成（推荐，启动最快）；
- **LLM + Milvus**：配置大模型 Key，并用 Docker 启动 Milvus（完整展示 RAG 技术栈）。

### 1.3 怎么确认当前处于什么模式

启动后有三种方式：

1. **看界面**：左侧边栏底部会显示「离线规则 / LLM 在线」以及模型名；顶部状态胶囊也会显示当前模型。
2. **看启动日志**：后端启动时会打印一行，例如：
   ```text
   SmartHome AI Agent ready | LLM=offline-rules | RAG=local
   ```
3. **看状态接口**：浏览器打开
   ```text
   http://127.0.0.1:8000/api/v1/system/status
   ```
   重点字段：
   - `app.demo_mode`：`true` 表示离线规则模式；
   - `llm.enabled`：是否启用了大模型；
   - `llm.model`：离线时显示 `offline-rules`；
   - `rag.backend`：当前实际使用的向量库（`local` / `milvus`）；
   - `rag.embedding.provider`：当前 Embedding 类型（`local` / `openai`）。

> `llm.enabled` 只表示“配置了 Key”，不代表 Key 一定有效。真正调用失败时，状态里的 `llm.last_error` 会记录原因，对话会自动回退规则引擎。

---

## 二、配置 API Key

### 2.1 配置文件位置

后端只读取 **`backend/.env`** 这一个配置文件。仓库里提供的是模板 `backend/.env.example`。

首次配置：

```bash
cd backend
# Windows CMD
copy .env.example .env
# PowerShell / macOS / Linux / Git Bash
cp .env.example .env
```

然后用编辑器打开 `backend/.env`。这个文件已被 `.gitignore` 忽略，不会被提交到仓库。

### 2.2 最小配置（以 DeepSeek 为例）

```env
LLM_PROVIDER=openai
LLM_API_KEY=sk-你的真实Key
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
LLM_TEMPERATURE=0.2
LLM_TIMEOUT=60
```

说明：

- `LLM_PROVIDER` 只有 `openai` 和 `offline` 两个值；任何 OpenAI 兼容服务都填 `openai`；
- `LLM_BASE_URL` 必须以服务商要求的版本路径结尾（通常是 `/v1`）；
- 只填 `LLM_API_KEY` 也能用，因为默认地址和模型就是 DeepSeek；但换服务商时三项要一起改；
- 修改 `.env` 后必须**重启后端**才会生效（配置在进程启动时加载）。

### 2.3 常见服务商示例

以下模型名仅作示例，实际以服务商控制台当前可用的模型为准。

**通义千问（DashScope 兼容模式）**

```env
LLM_PROVIDER=openai
LLM_API_KEY=sk-你的DashScopeKey
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-plus
```

**Moonshot**

```env
LLM_PROVIDER=openai
LLM_API_KEY=sk-你的Key
LLM_BASE_URL=https://api.moonshot.cn/v1
LLM_MODEL=moonshot-v1-8k
```

**SiliconFlow**

```env
LLM_PROVIDER=openai
LLM_API_KEY=sk-你的Key
LLM_BASE_URL=https://api.siliconflow.cn/v1
LLM_MODEL=Qwen/Qwen2.5-7B-Instruct
```

**OpenAI**

```env
LLM_PROVIDER=openai
LLM_API_KEY=sk-你的Key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

**本地 Ollama**

Ollama 也提供 OpenAI 兼容接口。先确保本机 Ollama 已启动并拉取了模型：

```bash
ollama pull qwen2.5:7b
ollama serve
```

```env
LLM_PROVIDER=openai
LLM_API_KEY=ollama
LLM_BASE_URL=http://127.0.0.1:11434/v1
LLM_MODEL=qwen2.5:7b
```

> `LLM_API_KEY` 不能为空，即使 Ollama 不校验 Key，也要随便填一个非空值（如 `ollama`）。
>
> 如果后端运行在 Docker 容器里、Ollama 在宿主机上，`LLM_BASE_URL` 要改成
> `http://host.docker.internal:11434/v1`。

### 2.4 配置后如何确认生效

1. 重启后端；
2. 打开 http://127.0.0.1:8000/ ，看左侧边栏是否显示「LLM 在线」及模型名；
3. 或者访问 http://127.0.0.1:8000/api/v1/system/status ，确认：
   ```json
   {
     "app": { "demo_mode": false },
     "llm": { "enabled": true, "model": "deepseek-chat" }
   }
   ```
4. 在「AI 管家」里发一句「你好」或「打开客厅主灯」，观察回复与右侧轨迹；在线模式下由模型生成自然语言，节点轨迹仍与离线模式一致。

### 2.5 可选：使用远程 Embedding

默认的 `local` Embedding 不消耗额度，演示足够。如果希望 RAG 也使用真实语义向量，可以配置 OpenAI 兼容的 embeddings 接口：

```env
EMBEDDING_PROVIDER=openai
EMBEDDING_API_KEY=sk-你的Key
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_MODEL=text-embedding-v3
EMBEDDING_DIM=1024
```

注意：

- `EMBEDDING_DIM` 必须与服务商模型实际输出维度一致（通义 `text-embedding-v3` 默认 1024），否则 Milvus 写入会因维度不一致失败；
- 更换 Embedding 模型或维度后需要重启，让后端重新建立向量；
- 接口不可用时会自动回退到本地哈希 Embedding，并在状态接口的 `rag.embedding.fallback` 中记录原因；
- 大多数演示场景保持 `EMBEDDING_PROVIDER=local` 即可。

### 2.6 Key 配置常见问题

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 侧边栏仍是「离线规则」 | Key 为空、仍是模板占位符，或 `LLM_PROVIDER=offline` | 检查 `backend/.env`，重启后端 |
| 回复出现「模型服务不可用，已切换本地意图解析」 | Key 错误、网络不通、限流或余额不足 | 查看状态接口的 `llm.last_error`，检查 Key/网络/额度 |
| 401 / Unauthorized | Key 无效或复制时带了空格 | 重新复制，确保没有引号外多余字符 |
| 404 / model not found | `LLM_BASE_URL` 或 `LLM_MODEL` 不对应 | 对照服务商文档同时修改地址与模型名 |
| 请求超时 | 网络慢、代理问题或模型响应过慢 | 增大 `LLM_TIMEOUT`，或先切回离线模式演示 |
| 场景/设备控制仍然正常，只是措辞变简单 | 触发了自动降级 | 这是预期行为：Agent 会优先保证执行成功 |

### 2.7 安全建议

- 不要把真实 Key 写进代码、截图、README 或提交记录；
- `backend/.env` 已在 `.gitignore` 中，Docker 构建时也通过 `.dockerignore` 排除，不会打进镜像；
- 如果 Key 曾经出现在公开仓库或聊天记录中，请在服务商控制台立即作废并重新生成。

---

## 三、用 Docker 启动

### 3.1 前置条件

- 已安装 Docker Desktop（Windows / macOS）或 Docker Engine（Linux）；
- **Docker 引擎已启动**（不是只打开 Docker Desktop 窗口，要等引擎状态变成 Running）；
- 首次构建需要联网下载 Node、Python、npm 与 pip 依赖。

检查命令：

```bash
docker --version
docker compose version
```

如果提示 `docker: unknown command: docker compose`，说明当前安装的是旧版 Compose 独立命令，把下文命令中的 `docker compose` 换成 `docker-compose` 即可。

如果 Compose 版本较旧、不支持 `docker-compose.yml` 中的可选 `env_file` 配置，先执行 `copy backend/.env.example backend/.env`（或 `cp`）生成配置文件，再启动即可。

### 3.2 一键启动应用

在项目根目录执行：

```bash
docker compose up -d --build
```

或：

```bash
docker-compose up -d --build
```

首次构建会依次完成：

1. `node:22-alpine` 中执行 `npm ci && npm run build`，构建前端；
2. `python:3.11-slim` 中安装后端依赖与 `pymilvus`；
3. 把前端构建产物复制到镜像内，由 FastAPI 直接托管。

启动后访问：

- 控制台：http://127.0.0.1:8000/
- 接口文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/api/health

容器名为 `smarthome-agent`，数据保存在名为 `smarthome-data` 的 Docker 数据卷中。

查看状态：

```bash
docker compose ps
docker compose logs -f app
```

### 3.3 在 Docker 中配置 API Key

Docker 启动与本地启动共用 **`backend/.env`**：`docker-compose.yml` 通过 `env_file` 把它注入容器。

步骤：

```bash
# 1. 准备配置文件（如果还没有）
cd backend
copy .env.example .env
# 编辑 .env，填入 LLM_API_KEY 等
```

```bash
# 2. 回到项目根目录，重建/启动
cd ..
docker compose up -d --build
```

如果只是改了 `.env` 内容，没有改代码，可以只重建容器：

```bash
docker compose up -d --force-recreate app
```

> 注意：`backend/.env` 不会被复制进镜像，而是在容器启动时注入，所以修改 Key 不需要重新构建镜像。

### 3.4 同时启用 Milvus

项目提供了独立的 Milvus 单机编排文件 `docker-compose.milvus.yml`（etcd + MinIO + Milvus）。

**第一步：先启动向量库**

```bash
docker compose -f docker-compose.milvus.yml up -d
# 旧版 Compose：
docker-compose -f docker-compose.milvus.yml up -d
```

首次拉取镜像并初始化需要 1–2 分钟，等待健康检查通过：

```bash
docker compose -f docker-compose.milvus.yml ps
```

**第二步：让应用使用 Milvus**

在 `backend/.env` 中设置：

```env
VECTOR_STORE=milvus
```

然后启动应用：

```bash
docker compose up -d --build
```

应用容器会自动通过 `host.docker.internal:19530` 访问宿主机上映射出来的 Milvus 端口；镜像中已经安装了 `pymilvus`，不需要额外装包。

**第三步：确认生效**

打开 http://127.0.0.1:8000/api/v1/rag/stats ，确认：

```json
{
  "backend": "milvus",
  "requested_backend": "milvus",
  "degraded": false,
  "count": 160
}
```

如果 `backend` 仍是 `local`，或 `degraded=true`：

- Milvus 可能还没启动完成，先等健康检查通过；
- 确认 `VECTOR_STORE=milvus` 已写入 `backend/.env`；
- 执行 `docker compose restart app`，让后端重新连接；
- 查看 `docker compose logs app` 中的降级原因。

> 也可以只用 Docker 启动 Milvus、后端仍用本地 Python 运行。此时在 `backend/.env` 中设置
> `MILVUS_URI=http://localhost:19530`，并在本地虚拟环境执行
> `pip install -r backend/requirements-milvus.txt`。

### 3.5 Docker 常用命令

| 目的 | 命令 |
| --- | --- |
| 构建并后台启动 | `docker compose up -d --build` |
| 查看日志 | `docker compose logs -f app` |
| 查看容器状态 | `docker compose ps` |
| 重启应用 | `docker compose restart app` |
| 修改代码后重建 | `docker compose up -d --build` |
| 停止并保留数据 | `docker compose down` |
| 停止并删除数据卷（清空数据库） | `docker compose down -v` |
| 强制重新创建容器 | `docker compose up -d --force-recreate app` |
| 进入容器排查 | `docker compose exec app bash` |

### 3.6 端口与数据

**改端口**：在项目根目录新建 `.env`（不是 `backend/.env`），写入：

```env
APP_PORT=8080
```

然后启动：

```bash
docker compose up -d
```

访问 http://127.0.0.1:8080/ 。

**数据位置**：

- 本地 Python 启动：`backend/data/smart_home.db`、`backend/data/vector_cache.json`；
- Docker 启动：数据卷 `smarthome-data`，挂载到容器 `/app/backend/data`；
- 清空演示数据：`docker compose down -v`（会删除数据库、会话和自定义场景，请谨慎）。

**时区**：容器默认 `TZ=Asia/Shanghai`，模拟器的「早晨/午后/傍晚」时间段会与北京时间一致。可在根目录 `.env` 中用 `TZ=Asia/Shanghai` 覆盖。

---

## 四、回家 / 离家等场景模式

### 4.1 有没有“居家模式”和“离家模式”？

有，但要区分两个概念：

- **运行模式**（离线 / 在线）是整个后端的运行方式；
- **场景模式**（回家 / 离家 / 观影等）是 LangGraph 场景子图，执行一次多设备联动，不是持续运行的后台安防模式。

项目内置了 6 个场景，其中：

- **回家模式**：也就是常说的“居家模式 / 到家模式”，自然语言里说「我到家了」「开启回家模式」「开启居家模式」都能触发；
- **离家模式**：说「出门了，进入离家模式」「执行离家模式」「我要去上班了」可以触发。

> 这些场景是“一次性设备联动”：执行完后设备保持在结果状态，不会持续监控门窗或自动布防。
> 项目没有接入摄像头/门磁等安防硬件，因此不是家庭安防系统意义上的“布防/撤防”。

### 4.2 六个内置场景

| 场景 | 可用触发说法 | 主要动作 | 条件 |
| --- | --- | --- | --- |
| **回家模式** | 我到家了 / 开启回家模式 / 开启居家模式 / 进入到家模式 | 客厅主灯 80%、灯带 45%、客厅空调 26°C（室温 ≥25.5°C 时）、客厅窗帘合到 30%、净化器自动、播放轻音乐 | 16:00–23:59 为可选条件，不满足也会继续执行 |
| **离家模式** | 出门了，进入离家模式 / 开启离家场景 / 执行离家模式 | 关闭 6 路灯、2 台空调、净化器、加湿器、音箱、电视插座，合上两幅窗帘 | 无条件，直接执行 |
| **观影模式** | 打开观影模式 / 我要看电影 / 开启观影场景 | 主灯降到 12% 暖光、灯带微亮、合拢窗帘、空调 24°C 低风速、电视插座通电、音箱待机 | 无条件 |
| **睡眠模式** | 我要睡觉了 / 开启睡眠模式 / 晚安 | 关闭主要灯光、床头灯留 8%、合帘、主卧空调 27°C、加湿器 55%、净化器睡眠模式、电视断电 | 21:00–23:59 为可选条件 |
| **清晨模式** | 早安，打开清晨模式 / 开启起床场景 / 该起床了 | 拉开主卧与客厅窗帘、床头灯柔和亮起、关闭空调与加湿器、播放晨间新闻 | 05:30–09:30 为可选条件 |
| **全屋节能** | 开启全屋节能模式 / 执行节能场景 | 主灯降至 30%、关闭灯带与书房灯、客厅空调 27°C、关闭主卧空调、净化器自动、电视断电 | 无条件 |

说明：

- 内置时间条件都是 `optional`，所以比赛现场不在对应时段也能完整演示；
- 场景浮层会显示条件判断结果，例如「当前 14:20 不在 16:00–23:59 时段内（可选条件，继续执行）」；
- 回家模式的空调步骤还带有室温条件：只有客厅温度 ≥25.5°C 时才开启，否则该步骤会被跳过。

### 4.3 怎么运行场景

有三种方式：

1. **自然语言**：在「AI 管家」输入「我到家了」「开启离家模式」等；
2. **场景编排页**：进入「场景编排」，在场景卡片上点击运行；
3. **API**：`POST /api/v1/scenes/{scene_id}/run`，返回 SSE 事件流。

执行时右侧/浮层会逐步展示：

```text
加载场景 → 条件判断 → 动作编排 → 逐个设备执行 → 状态校验 → 完成
```

每个动作都会推送执行结果；如果关键动作失败（例如设备被手动设为离线），会进入兜底分支，尽最大可能恢复状态，最终结果标记为「部分完成」。

### 4.4 演示兜底：把设备设为离线

推荐演示步骤：

1. 进入「设备」页，打开「客厅主灯」的控制抽屉；
2. 点击模拟离线；
3. 回到「AI 管家」说「我到家了」；
4. 观察：客厅主灯关键动作失败 → 进入 `fallback` 兜底分支 → 场景继续执行其他设备 → 最终标记为部分完成；
5. 重新上线设备，再执行一次场景，恢复完整成功。

### 4.5 自定义场景

在「场景编排」页可以新建、编辑、复制、删除自定义场景：

- 每个场景可以包含多个设备动作，并设置顺序、延时、关键动作标记；
- 支持时间、温度、湿度、设备属性等条件；
- 支持配置兜底动作；
- 场景名称会进入意图匹配，之后可以直接说「开启 XXX 模式」触发（自定义场景建议以「模式/场景」结尾）。

---

## 五、日常使用与演示速查

### 5.1 页面入口

| 页面 | 用途 |
| --- | --- |
| 总览 | 全屋环境、空间拓扑、功率/温度趋势、快捷场景 |
| AI 管家 | 自然语言对话、语音输入、意图与工具调用轨迹 |
| 设备 | 查看 20 台设备、控制属性、模拟上线/离线 |
| 场景编排 | 运行内置场景、创建自定义场景、查看 LangGraph 子图 |
| 知识库 | 语义检索、查看/新增 RAG 语料 |
| 运行轨迹 | 回放每次对话/场景的节点耗时、工具调用与结果 |

### 5.2 推荐演示话术

| 输入 | 展示点 |
| --- | --- |
| `打开客厅主灯，亮度调到 80%` | 多步合并为一次 `control_light` 工具调用 |
| `空调调到 26 度` | 两台空调产生歧义，先澄清 |
| `客厅` | 恢复澄清，继续执行 |
| `再亮一点` | 基于上一轮设备的上下文指代 |
| `关闭客厅灯，然后打开主卧空调` | 多指令拆分与顺序执行 |
| `打开主卧窗帘，开一半` | 参数抽取（开合度 50%） |
| `把客厅灯调暖一点，亮度 50%` | 同一次调用合并色温与亮度 |
| `我到家了` / `开启居家模式` | 回家模式，含条件步骤与多设备联动 |
| `出门了，进入离家模式` | 离家模式，批量关闭设备 |
| `空调多少度最省电？` | RAG 知识问答 |
| `现在室内温湿度怎么样` | 环境查询与工具调用 |

### 5.3 语音输入

「AI 管家」支持浏览器语音输入（Web Speech API）：

- 推荐 Chrome / Edge；
- 需要允许麦克风权限；
- 在 `localhost` 或 HTTPS 下可用；部分浏览器在非安全上下文会禁用麦克风。

### 5.4 重置演示数据

**本地运行**：

1. 停止后端；
2. 删除 `backend/data/smart_home.db`、`smart_home.db-wal`、`smart_home.db-shm`（如果存在）以及 `backend/data/vector_cache.json`；
3. 重新启动后端，会自动重建数据库、设备、语料与 6 个内置场景。

**Docker 运行**：

```bash
docker compose down -v
docker compose up -d --build
```

> `down -v` 会删除 `smarthome-data` 数据卷，包括会话、运行记录和自定义场景。

### 5.5 运行测试

```bash
cd backend
# Windows
.venv\Scripts\python.exe -m pytest -q
# macOS / Linux
.venv/bin/python -m pytest -q
```

当前测试覆盖 NLU、设备控制、参数裁剪、离线设备、场景 CRUD、对话 SSE、场景 SSE、异常兜底、RAG 检索与运行记录，使用独立临时数据库，不依赖外网、LLM 或 Milvus。

---

## 六、常见问题排查

### 6.1 页面打不开 / 8000 端口被占用

- 本地启动时 `run.py` 固定监听 `8000`；先确认没有其他进程占用：
  ```bash
  # Windows
  netstat -ano | findstr :8000
  # macOS / Linux
  lsof -i :8000
  ```
  结束占用进程，或修改 `backend/run.py` 中的 `port`；
- Docker 启动时直接换映射端口（根目录 `.env`）：
  ```env
  APP_PORT=8080
  ```
  然后 `docker compose up -d`。

### 6.2 打开首页不是控制台页面 / 静态资源 404

- 确认 `frontend/dist` 存在（本地启动时 FastAPI 从这里托管页面）；没有构建产物时，根路径会返回一段 JSON 信息而不是页面；
- 如果没有构建产物，执行：
  ```bash
  cd frontend
  npm install
  npm run build
  ```
- 开发模式可改用 `npm run dev`，访问 http://127.0.0.1:5173 （Vite 会把 `/api` 代理到 8000）；
- Docker 镜像会在构建阶段自动生成前端产物，不需要本地 Node。

### 6.3 一直显示「离线规则」，配置了 Key 也不生效

按顺序检查：

1. 文件是不是 `backend/.env`，而不是根目录 `.env`；
2. `LLM_API_KEY` 是否为空或仍是示例占位符；
3. `LLM_PROVIDER` 是否为 `offline`；
4. 修改后是否重启了后端；
5. Docker 中是否执行了 `docker compose up -d --force-recreate app`；
6. 查看 `/api/v1/system/status` 中的 `llm.enabled` 与 `llm.last_error`。

### 6.4 对话出现「LLM 回退」提示

说明模型调用失败，但规则引擎已经接管，功能不受影响。常见原因：

- Key 无效、余额不足、限流；
- `LLM_BASE_URL` 写错或网络无法访问；
- 模型名不存在；
- 请求超时（可在 `.env` 中增大 `LLM_TIMEOUT`）。

### 6.5 RAG 一直是本地向量库，没有用上 Milvus

1. 确认 Milvus 容器健康：
   ```bash
   docker compose -f docker-compose.milvus.yml ps
   ```
2. 确认 `backend/.env` 中 `VECTOR_STORE=milvus`；
3. 本地 Python 运行还需要 `pip install -r backend/requirements-milvus.txt`；
4. Docker 应用容器内默认使用 `host.docker.internal:19530` 访问宿主机 Milvus；
5. 查看 `docker compose logs app` 或 `/api/v1/rag/stats` 中的 `error` / `degraded` 字段；
6. 若应用比 Milvus 先启动，执行 `docker compose restart app` 重新连接。

> 即使 Milvus 不可用也不影响演示：`auto` 模式会自动降级到本地向量库，状态接口会标明实际后端。

### 6.6 Docker 命令报错

| 报错 | 处理 |
| --- | --- |
| `failed to connect to the docker API` | Docker 引擎没启动，打开 Docker Desktop 并等待 Running |
| `unknown command: docker compose` | 使用 `docker-compose`（旧版独立命令） |
| 构建很慢或卡在 npm/pip | 首次构建需要下载依赖，检查网络/代理；后续会命中缓存 |
| `port is already allocated` | 8000 被占用，用根目录 `.env` 设置 `APP_PORT=8080` |
| 容器启动后 unhealthy | `docker compose logs app` 查看启动日志，通常是依赖安装或端口问题 |

### 6.7 设备控制失败

- 设备是否被手动设为离线（「设备」页会显示离线状态）；
- 参数是否超出范围（例如亮度 1–100、空调 16–30°C），后端会自动裁剪并提示；
- 设备类型是否支持该能力（例如传感器只读）；
- 查看「运行轨迹」中的 `guard` / `tool_result` 事件，定位是拦截还是执行失败。

---

## 七、配置项速查

以下变量写入 `backend/.env`（本地与 Docker 共用）：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `LLM_PROVIDER` | `openai` | `openai` = 任意 OpenAI 兼容服务；`offline` = 强制离线规则 |
| `LLM_API_KEY` | 空 | 为空即离线规则模式 |
| `LLM_BASE_URL` | `https://api.deepseek.com/v1` | 模型接口地址 |
| `LLM_MODEL` | `deepseek-chat` | 模型名称 |
| `LLM_TEMPERATURE` | `0.2` | 生成温度 |
| `LLM_TIMEOUT` | `60` | 请求超时（秒） |
| `EMBEDDING_PROVIDER` | `local` | `local` / `openai` |
| `EMBEDDING_API_KEY` | 空 | 使用远程 Embedding 时填写 |
| `EMBEDDING_BASE_URL` | 空 | 为空时复用 `LLM_BASE_URL` |
| `EMBEDDING_MODEL` | `text-embedding-v3` | Embedding 模型 |
| `EMBEDDING_DIM` | `512` | 向量维度，必须与模型输出一致 |
| `VECTOR_STORE` | `auto` | `auto` / `local` / `milvus` |
| `MILVUS_URI` | `http://localhost:19530` | 本地 Python 运行时的 Milvus 地址 |
| `MILVUS_COLLECTION` | `smart_home_kb` | Milvus collection 名称 |
| `SIMULATOR_INTERVAL` | `4.0` | 设备/环境模拟推送间隔（秒） |
| `CORS_ORIGINS` | `*` | 允许的跨域来源，生产环境建议收紧 |
| `DEBUG` | `false` | 开启后 uvicorn 使用 reload |
| `LOG_LEVEL` | `INFO` | 日志级别 |

以下变量用于 `docker-compose.yml`，写在项目根目录 `.env`（可选）：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `APP_PORT` | `8000` | 宿主机映射端口 |
| `MILVUS_URI` | `http://host.docker.internal:19530` | 应用容器访问 Milvus 的地址 |
| `TZ` | `Asia/Shanghai` | 容器时区 |

---

## 附：最短上手路径

**只想看演示（不配置任何 Key）**

```bash
docker compose up -d --build
# 或本地双击 start.bat
```

打开 http://127.0.0.1:8000/ ，直接说「打开客厅主灯」「我到家了」。

**想接入大模型**

1. 复制 `backend/.env.example` 为 `backend/.env`；
2. 填入 `LLM_API_KEY`（以及对应服务商的 `LLM_BASE_URL`、`LLM_MODEL`）；
3. 重启服务；
4. 侧边栏显示「LLM 在线」即生效。

**想启用 Milvus**

```bash
docker compose -f docker-compose.milvus.yml up -d
# backend/.env: VECTOR_STORE=milvus
docker compose up -d --build
```

访问 `/api/v1/rag/stats` 确认 `backend` 为 `milvus`。
