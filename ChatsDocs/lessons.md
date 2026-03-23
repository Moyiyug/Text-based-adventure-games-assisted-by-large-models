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

### 2026-03-23 | 游玩页选项须与 `GET …/messages` 的 metadata 对齐

**问题**：刷新游玩页后底部「暂无选项」，尽管叙事里有一串文字选项；Zustand 的 `choices` 仅来自 SSE / 开场响应，未从服务端消息恢复。  
**根因**：结构化选项在 `session_messages.metadata.choices`；refetch 后若不同步则 store 为空。  
**规则**：每次 `resetAndHydrate` 后立刻调用 `applyChoicesFromMessages`：最后一条为 **assistant** 时用其 `metadata.choices`；为 **user** 时清空（等待本轮回复）。另：气泡展示层对 assistant 正文做 `stripMetaSuffixForDisplay`，后端落库前用 `strip_leaking_meta_suffix` 截断误入正文的 `---META---` 段。

### 2026-03-23 | 选项「全不见」：区分 SSE/metadata 与气泡展示

**问题**：底部无选项按钮，且气泡里文末编号也被剥掉，体验像「工作流错位」。  
**根因**：`choices` 来自 SSE `choices` 与 `metadata`（`applyChoicesFromMessages`），与 `stripMetaSuffixForDisplay` **无关**；但若 `metadata.choices` 为空而前端仍 `stripTrailingNumberedChoiceBlock`，会形成双重空白。短选项（原兜底要求正文 ≥6 字）也会导致后端 `extract_choice_lines_from_narrative` 不命中。  
**规则**：排查时管理员看折叠内 **metadata** + Network 里 SSE 的 `type:choices`。气泡仅在「已落库 + `coerceChoicesFromMetadata` ≥2」时去文末编号；后端/前端编号行最短正文与 `meta_parse` 对齐为 **≥2 字**（仍要求至少 2 条编号行）。`stripLooseMetaLeak` 误截断仅在实际复现后再收紧。

### 2026-03-23 | `parse_error` 为空但 `choices:[]`：模型交了空 JSON 数组

**现象**：管理员调试里 `choices` 为空、`parse_error` 为 null，叙事很长。  
**根因**：META 后 JSON 合法但 `"choices":[]`（或项被滤空）；正文里若没有匹配兜底正则的编号行（格式非 `1.`/`1）`/（1）` 等，或选项不在尾部扫描窗口内，则整条链路仍为空。  
**规则**：看 `metadata.choices_source`（`model_json` / `narrative_regex` / `llm_fallback` / `none`）。省成本可设 `NARRATIVE_CHOICES_LLM_FALLBACK=false`；要根治模型习惯需更新 DB 内系统模板（`seed_prompt_templates` 的 `META_BLOCK`）并禁止空 `choices` 数组。提示词灌库后须重新执行 seed 或管理端同步。

### 2026-03-23 | 叙事推进：`choice_beats` 与 turn_hints 不对玩家气泡展示

**规则**：`choice_beats` 仅落库 `metadata`，下回合经 `build_turn_hints_text` 注入 prompt；遵守 RULES §5.7。`NARRATIVE_INPUT_BRIDGE` 只拼接进**发给模型的** user 内容，落库 user 消息仍为玩家原文。`NARRATIVE_STRICT_CHOICE_REFINE` 多一轮 RTT，默认关。

### 2026-03-23 | 假 META 在规范 `---META---` 之前：须 pre-marker 剥离

**现象**：玩家气泡出现「【META JSON】」「```json」等，底部选项仍正常。  
**根因**：`MetaStreamSplitter` 以**首个**合法 marker 切分，其前的伪造块整段进入 `narrative_all`；仅靠 `strip_leaking_meta_suffix` 截 `---META---` 无法去掉 marker **之前**的垃圾。  
**规则**：落库前走 `strip_pre_marker_meta_leak`（已并入 `strip_leaking_meta_suffix`）；前端 `stripMetaSuffixForDisplay` 内同逻辑，流式亦执行。单轮略短靠 `NARRATIVE_CONCISE_MODE` + seed 模板引导，非硬截断。

### 2026-03-23 | `---` + `**choices:**` / `**choice_beats:**` 泄漏

**现象**：叙事后单独一行 `---`，再出现 Markdown 加粗的 `**choices:**`、列表与 `**choice_beats:**`，玩家可见选项与剧透大纲。  
**根因**：仍在首个 `---META---` 之前，整段进入 `narrative_all`；`strip_pre_marker_meta_leak` 不认此类形态。  
**规则**：`strip_pseudo_markdown_meta_tail`（并入 `strip_leaking_meta_suffix`）：自文末找伪字段标题行，若其上方 ≤12 行内有单独 `---` 则截在 `---`，否则截在标题行；前端 `stripPseudoMarkdownMetaTail` 同构。提示词 META_BLOCK 禁止叙事中用 Markdown 枚举结构化字段。

### 2026-03-23 | 容错切分：`---` / `-----` 后多行 JSON

**现象**：模型用单独一行 `---` 接 `{` 与多行 JSON，未输出 `---META---`，整段被当作叙事推给玩家。  
**根因**：`find_meta_split` 原不认 HR+JSON。  
**规则**：`find_meta_split` 第三优先级 `_find_hr_json_split`（文末向上：整行 `---` 或 `-----+`，其后 JSON 须能解析且含 choices/state 等键）；`MetaStreamSplitter` 用 `_hr_json_withhold_start` 流式 withhold；`finalize` 在无 marker 时改走 `parse_complete_model_output` 整缓冲。提示词 `META_BLOCK` 第 2 条要求首选 `---META---`，多行 JSON 须 `-----` 空行分隔；**灌库须重跑** `seed_prompt_templates.py`。

**双阶段**：`NARRATIVE_TWO_PHASE_ENABLED=true` 时第一轮只叙事、第二轮 `build_two_phase_meta_prompt` 专出 META；与 `NARRATIVE_SPLIT_CHOICES_LLM` 同时开时以前者为准（见 `engine.py`）。**多轮真实 LLM 回归**：`scripts/narrative_llm_roundtrip_soak.py`（需已启动 API、配置 `SOAK_USERNAME`/`SOAK_PASSWORD`/`SOAK_STORY_ID`，费 token；客户端为 httpx 流式读 POST SSE，非 EventSource，与 RULES §5.1 一致）。

### 2026-03-23 | 伪字段扩展 `**META**` / `**META JSON**` 须与 choices 类同等剥离

**现象**：`---` 后出现加粗仿协议标题 `**META**`，主气泡与流式阶段可见，与合法分隔符 `---META---` 混淆。  
**根因**：`_MD_FIELD_LINE` 曾仅含 `choices|choice_beats|state_update|internal_notes`。  
**规则**：关键词组增加 `meta(?:\\s+json)?`（与 Python `re` / TS `RegExp` 同构）；`_META_FIELD_KEYS` 增加 `meta`、`meta json` 供流式前缀截断。扩展白名单时**必须**双端 + `test_meta_parse.py` + Vitest 同步。提示词 `META_BLOCK` 显式禁止 `**META**` 等；模板更新后须重跑 `seed_prompt_templates.py` 灌库。

### 2026-03-23 | 伪字段标题 `**choices**`（无冒号）与 `**choices:**` 须同等剥离

**现象**：非流式开场气泡仍显示 `---` + `**choices**` + 列表，底部 JSON 选项正常。  
**根因**：`_MD_FIELD_LINE` / `_RE_MD_FIELD_LINE` 曾强制 `choices` 后必有 `:`，模型输出无冒号加粗标题时不命中，`strip_pseudo_markdown_meta_tail` 跳过。  
**规则**：前后端正则统一为 `(?:\\s*:\\s*\\*+|\\s*\\*+)` 两种尾部；`stripInflightChoiceMarkdownDisplay` 的 relaxed 与 `_lastLineCouldBeMetaFieldPrefix`（去尾 `*`）对齐；变更时同步 `test_meta_parse.py` 与 Vitest。

### 2026-03-19 | soak 脚本 `ReadTimeout`：`POST /opening` 须长读超时

**现象**：`narrative_llm_roundtrip_soak` 在 `POST /api/sessions/{id}/opening` 抛 `httpx.ReadTimeout`。  
**根因**：主 `httpx.Client` 未设 `timeout` 时用默认读超时（约 5s），开场接口在服务端同步调用 DeepSeek，耗时远超默认值。  
**规则**：soak 主客户端设 `httpx.Timeout(SOAK_HTTP_TIMEOUT 默认 300s, connect=30s)`；流式 `/messages` 仍用脚本内 300s。极慢网络可调大 `SOAK_HTTP_TIMEOUT`。

### 2026-03-19 | soak 脚本 `register 502`：本机 API 被系统代理劫持

**现象**：后端在本机正常运行、浏览器能打开 `/docs`，但 `soak_autorun.py` / `narrative_llm_roundtrip_soak.py` 报 `register 502` 或登录 502。  
**根因**：`httpx` 默认 `trust_env=True`，会读 `HTTP_PROXY`/`HTTPS_PROXY`；请求被发到代理，代理无法正确转发 `127.0.0.1` 时常返回 **502 Bad Gateway**。  
**规则**：本地 soak 脚本对显式 `base_url` 使用 **`trust_env=False`**（已写入两脚本）。若仍异常：核对 `SOAK_API_BASE` 与 uvicorn 端口一致；或在 CMD 设 `set NO_PROXY=127.0.0.1,localhost`。

### 2026-03-23 | 流式 in-flight 须截断伪字段前缀 + 开场无内置时间轴

**问题**：流式阶段玩家短暂看到 `**choices:**`、列表或 `**cho…` 逐字出现；误以为系统有「严格故事时间线」状态机。  
**根因**：`stripPseudoMarkdownMetaTail` 等依赖**整行**匹配，字符级流式下先出现不完整行或列表再满足正则；开场仅靠检索相似度，易从高光片段而非最早锚点切入。  
**规则**：① **展示层**：`streaming === true` 时先跑 `stripInflightChoiceMarkdownDisplay`（最后一行前缀状态机 + 放宽的伪标题行 + 可选 `---` 回退），再跑原有 strip 链；仍用 `fetch`+ReadableStream，SSE 序列不变（RULES §5.1）。② **产品/提示**：`OPENING_USER_PROMPT` 与 seed `META_BLOCK` 明确要求按作品内时序从较早合理锚点开场；真正「序」若需加强，再评估检索侧元数据加权，而非协议字段。
