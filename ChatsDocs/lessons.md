# lessons.md — 经验教训与防范规则

> 记录导致问题的模式和对应防范规则。每次会话开始时加载。
> 踩坑后立即追加条目，格式：日期 + 问题 + 根因 + 规则。

---

## 文档阶段踩过的坑

### 2026-03-19 | EventSource 不支持 POST + 自定义 Header

**问题**：初版 IMPLEMENTATION_PLAN 将前端 SSE 接收写为 "EventSource / fetch + ReadableStream" 二选一。  
**根因**：`EventSource` API 只支持 GET 请求，无法发送 POST body，也无法稳定携带 `Authorization` header。后端接口是 `POST /api/sessions/{id}/messages` + Bearer 鉴权，EventSource 根本不可用。  
**规则**：涉及需要鉴权的 SSE 端点时，**始终用 `fetch` + `ReadableStream` 手动解析**，不要将 `EventSource` 列为备选。

---

### 2026-03-19 | 流式输出与结构化 JSON 的矛盾

**问题**：要求模型输出完整 JSON（含 narrative + choices + state_update），同时又要逐 token 流式发送叙事文本。两者物理矛盾。  
**根因**：如果等 JSON 完整再发送，就没有流式体验；如果边生成边发 JSON token，前端无法解析不完整的 JSON。  
**规则**：采用**分隔符协议** `\n---META---\n`。模型先输出纯叙事文本（可逐 token 流式发送），分隔符后输出单行 JSON 元数据（服务端缓冲解析）。详见 `docs/BACKEND_STRUCTURE.md` §4.4。

---

### 2026-03-19 | 前端集中开发的集成爆炸风险

**问题**：初版计划将所有前端压缩到最后 3 天（Phase 7, Day 25-27），20 天纯后端期间无 UI 验证。  
**根因**：后端 API 的设计问题（字段名、分页格式、错误码）要到 Day 25 才暴露，但此时距截止仅剩 3 天。SSE 流式是最高风险的前端任务，被放在了最晚。  
**规则**：**前端跟随后端分阶段交付**。每个 Phase 后端完成后紧跟对应前端页面，发现集成问题当 Phase 内修复。公共组件按需创建，不集中构建。

---

### 2026-03-19 | 依赖关系图声称可并行但实际不行

**问题**：依赖图标注 P1（鉴权）和 P2（入库）可并行，但 P2 的所有端点都是 `/api/admin/*`，需要 P1 的 JWT + `require_admin`。  
**根因**：画依赖图时只看了数据依赖，忽略了基础设施依赖（鉴权中间件）。  
**规则**：画依赖图时，除了数据依赖，还要检查**鉴权依赖**和**基础设施依赖**（中间件、seed 脚本等）。

---

### 2026-03-19 | 缺失的 ORM 模型导致后续 Phase 卡住

**问题**：`user_profiles` 和 `story_profiles` 表在 Phase 4.8 和 Phase 5 都要用，但没有任何 Phase 包含创建这两个 ORM 模型的步骤。  
**根因**：这两个表的"使用方"和"创建方"分属不同 Phase，编写计划时各 Phase 只关注自己需要的模型。  
**规则**：为每个数据库表维护一个"创建于哪个 Phase"的清单。编写新 Phase 前，先检查所有引用的表是否已在更早的 Phase 中创建。

---

## 编码阶段

### 2026-03-19 | SQLite 相对路径基准是 cwd 而非项目根

**问题**：`.env` 中 `DATABASE_URL=sqlite+aiosqlite:///./data/app.db`，Alembic 报 "unable to open database file"。  
**根因**：SQLite URL 中的相对路径 `./data/app.db` 以当前工作目录为基准。uvicorn 和 alembic 都在 `RAG/backend/` 下运行，因此路径解析为 `RAG/backend/data/app.db`。但项目目录结构规定 `data/` 在 `RAG/data/`（TECH_STACK.md §8）。  
**规则**：`DATABASE_URL` / `CHROMA_PERSIST_DIR` / `UPLOAD_DIR` 等路径，如果 `data/` 在 `backend/` 的上级目录，必须使用 `../data/` 前缀。修改 `.env`、`.env.example` 和 `config.py` 默认值三处保持一致。

---

### 2026-03-20 | passlib 与 bcrypt 4.2+ 不兼容

**问题**：`passlib[bcrypt]` 调用 `CryptContext(schemes=["bcrypt"]).hash()` 报 `AttributeError: module 'bcrypt' has no attribute '__about__'`，随后触发 `ValueError: password cannot be longer than 72 bytes`。  
**根因**：`passlib` 最后更新于 2020 年，其 bcrypt 后端依赖 `bcrypt.__about__.__version__` 检测版本，但 `bcrypt>=4.1` 移除了 `__about__` 模块。  
**规则**：不使用 `passlib`，直接用 `bcrypt.hashpw()` / `bcrypt.checkpw()` 进行密码哈希与校验。`requirements.txt` 中 `passlib[bcrypt]` 可保留但实际不导入。

---

### 2026-03-20 | 管理后台与顶层导航主题冲突

**问题**：管理页使用 `.admin` 浅色 CSS 变量，但与游玩态共用的 TopNav（深色条）叠在一起，视觉与令牌不一致。  
**根因**：同一 `App` 根节点默认仍是 Dark 的 `--bg-primary`，TopNav 按游玩规范实现，未为 `/admin` 单独分支。  
**规则**：`/admin/*` 下隐藏 TopNav，管理区仅用 `AdminSidebar` + 内容区（浅色 `.admin` 容器），侧栏提供返回前台入口。参见 `FRONTEND_GUIDELINES.md` §2.2。

---

### 2026-03-20 | FormData 上传手动写 Content-Type 导致失败

**问题**：管理端上传作品报「Not Found」或校验失败。  
**根因**：`axios` 对 `FormData` 若手动设置 `Content-Type: multipart/form-data`，浏览器不会自动附加 `boundary`，服务端无法解析 `file` 字段，行为表现为路由未命中或 422。  
**规则**：`FormData` 请求**不要**设置 `Content-Type`，交给运行时自动带 boundary。

---

### 2026-03-20 | Tailwind @theme 静态色与管理端 .admin 不同步

**问题**：管理后台侧栏浅色，表格/弹层仍像深色。  
**根因**：Tailwind v4 `@theme` 里写死 hex 时，`bg-bg-secondary` 等工具类不读 `.admin` 下的 `--bg-secondary`。Radix Portal 挂在 `body` 下，也不在 `.admin` 子树内。  
**规则**：`@theme` 中颜色用 `var(--语义变量)`，在 `:root` 与 `body.admin-route`（或 `.admin`）上切换同一套语义变量；`/admin` 时用 `useEffect` 给 `body` 挂 `admin-route`。

---

### 2026-03-20 | DeepSeek 有余额仍 401

**问题**：入库任务 `error_message` 为 DeepSeek `401 Authorization Required`，但控制台网页有余额。  
**根因常见**：① Windows / CI **用户或系统环境变量**里的 `DEEPSEEK_API_KEY`（**含已废弃但仍非空的旧 Key**）会覆盖 `RAG/.env`，pydantic-settings **环境变量优先于 `.env`**；② 环境变量里存在 **空的** `DEEPSEEK_API_KEY=`（代码侧已设 `env_ignore_empty=True` 减轻此情况）；③ `.env` 里 Key 带 **BOM、首尾空格、误加引号**；④ 改 `.env` 后 **未重启 uvicorn**（无 `--reload` 时）。  
**规则**：在 `RAG/backend` 执行 `python -c "from app.core.config import settings; print(len(settings.DEEPSEEK_API_KEY))"` 核对长度；清理冲突的环境变量；代码侧对 Key 做 `strip()` 与 BOM 处理（见 `deepseek.py`）。

**补充**：若「另一项目」用同一 Key 正常，多为 **两项目读到的字符串不一致**（`RAG/.env` 未保存全量、路径不同、或系统环境变量在本机只影响其中一个进程）。用 `scripts/deepseek_key_fingerprint.py`（`PYTHONPATH=. python scripts/deepseek_key_fingerprint.py`）在两处各跑一次，比对 `normalized_len` 与 `sha256_prefix` 应完全相同。

**再补充（2026-03-20）**：若另一项目用 **`OpenAI(api_key, base_url=...)`** 而 RAG 曾用 **裸 `httpx`**，可能出现 **与官方 SDK 不同的 URL 组合** 或 **`httpx` 默认 `trust_env=True` 走系统代理** 导致网关返回 401。RAG 已改为 **`AsyncOpenAI` + `httpx.AsyncClient(trust_env=False)` + 超时/重试**，与 OpenAI 兼容调用对齐。

**入库 completed 但摘要/实体全空（2026-03-20）**：`IngestionJob.status=completed` 只表示管线未整体崩溃；**抽取/敏感**失败会记 `ingestion_warnings`（401 时可见）；**章节/场景摘要**若曾用 `except RuntimeError: pass` 则库内无摘要且无告警。已改为摘要失败也写入 **`llm_error`** 类 warning。验收时请查 **同一 job 的 warnings**，并确认 Key 正确后 **重新 ingest** 才会回填摘要与图谱。

### 2026-03-21 | 抽取窗口、场景切分与摘要套话

**抽取字数上限**：`extractor`/`summarizer`/`safety` 中按章截断（如 10k–16k 字）主要是 **费用、超时、JSON 稳定性** 的工程折中，**不是**「模型上下文硬上限」；长章后半段可能未被抽进图谱。

**场景切分**：`detect_scenes` 原按多空行切分，易把 **短前言** 单独成场景；已合并 **过短块**（常量 `MIN_SCENE_BODY_CHARS`）到相邻段。

**摘要套话**：模型偶发「请提供场景描述」等拒答句写入 `summary`；`summarizer` 用 **`is_junk_summary`** 丢弃，管线记 **`llm_error`**；**过短场景**（&lt; `MIN_SCENE_TEXT_CHARS_FOR_LLM`）跳过摘要调用。

**管理端场景**：`GET/PUT/DELETE .../metadata/scenes/{id}`；改 **`raw_text`** 会删该场景旧 **TextChunk**、**Chroma** `tc_*` 向量，再 **切块 + 嵌入**；删场景会 **重排 `scene_number`**。入库中 **`ingesting`** 仍 **409**（`_get_story_and_active_version`）。

### 2026-03-23 | 流式叙事与 `get_db` 事务

**问题**：`POST /messages` 若沿用依赖注入的 `get_db`，流式响应耗时期间会话可能长期不提交或与普通请求事务语义冲突。  
**规则**：**长连接 SSE** 使用 **`async with async_session_factory() as db`** 在路由/generator 内自管会话与 `commit`/`rollback`；引擎内完成写库后再 `yield` 尾部事件。

### 2026-03-23 | 叙事 `soften_content` 与 SSE 已发 token 不可混用

**问题**：流式回合若先把未软化的叙事 `token` 推给前端，再在落库前调用 `soften_content` 改写正文，会导致 **界面展示与数据库/历史不一致**。  
**规则**：**首版**仅对 **非流式开场**（`generate_opening`）在落库前可选软化（`NARRATIVE_SAFETY_SOFTEN`）。流式 `process_turn_sse` 不事后软化；完整「缓冲叙事段再 emit」留后续迭代。内容策略 **拦截** 时流式路径 **rollback** 本轮（含 user 消息）+ SSE `error`，与开场 **落库降级文案** 策略区分清楚。

### 2026-03-22 | Alembic 版本链与本地 `app.db` 不一致

**问题**：`alembic upgrade head` 报 `Can't locate revision identified by '…'`。  
**根因**：本机 SQLite 中 `alembic_version` 指向的 revision 在仓库 `alembic/versions/` 中不存在（或从其它分支/拷贝来的库）。  
**规则**：以仓库迁移链为准；新环境用空库 `upgrade head`，或 `alembic stamp <已知 head>` 再逐步升级；勿手工改表结构却不生成 revision。Phase 4 会话表迁移：`d4e5f6a7b8c9` 接在 `b7c4e2d1a9f0` 之后。

### 2026-03-21 | RAG 检索：Chroma `n_results`、BM25 缓存、加权 RRF

**Chroma**：`collection.query` 的 `n_results` 须 **≥1**；传 0 会报错或行为异常；与 `top_k` 组合时用 `max(1, top_k)`。

**BM25**：按 `story_version_id` 进程内缓存；**入库嵌入完成后**应调用 `invalidate_bm25_cache(story_version_id)`，否则新切块不参与检索。

**方案 A 融合**：双路为 **BM25 排名** 与 **向量距离排序后的 chunk id 列表**；合并使用 **加权 RRF**：`score[id] += w_bm25/(K+rank_bm25) + (1-w_bm25)/(K+rank_vec)`，默认 `K=60`（见 `variant_a.RRF_K`）。
