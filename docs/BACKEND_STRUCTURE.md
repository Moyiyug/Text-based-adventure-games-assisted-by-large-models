# BACKEND_STRUCTURE.md — 后端结构

> 版本：V1
> 最后更新：2026-03-19

---

## 1. 数据库 Schema（SQLite via SQLAlchemy）

所有表使用 SQLAlchemy ORM 定义，通过 Alembic 管理迁移。主键统一使用自增整数 `id`。时间字段统一使用 UTC。

---

### 1.1 用户与鉴权

#### `users` 表

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK, autoincrement | |
| username | String(20) | UNIQUE, NOT NULL | 登录用户名 |
| password_hash | String(128) | NOT NULL | bcrypt 哈希 |
| display_name | String(30) | NOT NULL | 显示昵称 |
| avatar_path | String(256) | NULL | 头像文件路径 |
| bio | Text | NULL | 个人简介 |
| role | String(10) | NOT NULL, DEFAULT 'player' | 'admin' 或 'player' |
| created_at | DateTime | NOT NULL, DEFAULT utcnow | |
| updated_at | DateTime | NOT NULL, onupdate utcnow | |

---

### 1.2 作品与知识库

#### `stories` 表

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK | |
| title | String(200) | NOT NULL | 作品标题 |
| description | Text | NULL | 作品简介 |
| source_file_path | String(512) | NULL | 原始上传文件路径 |
| status | String(20) | NOT NULL, DEFAULT 'pending' | pending / ingesting / ready / failed |
| created_at | DateTime | NOT NULL | |
| updated_at | DateTime | NOT NULL | |

#### `story_versions` 表

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK | |
| story_id | Integer | FK → stories.id, NOT NULL | |
| version_number | Integer | NOT NULL | 递增版本号 |
| is_active | Boolean | NOT NULL, DEFAULT false | 当前生效版本 |
| is_backup | Boolean | NOT NULL, DEFAULT false | 备份版本 |
| ingestion_config | JSON | NULL | 入库时的配置快照 |
| created_at | DateTime | NOT NULL | |

约束：同一 story_id 最多一个 `is_active=true`，最多一个 `is_backup=true`。

#### `chapters` 表

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK | |
| story_version_id | Integer | FK → story_versions.id, NOT NULL | |
| chapter_number | Integer | NOT NULL | |
| title | String(200) | NULL | 章节标题 |
| raw_text | Text | NOT NULL | 章节原文 |
| summary | Text | NULL | 自动生成摘要 |
| created_at | DateTime | NOT NULL | |

#### `scenes` 表

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK | |
| chapter_id | Integer | FK → chapters.id, NOT NULL | |
| scene_number | Integer | NOT NULL | 章节内场景序号 |
| raw_text | Text | NOT NULL | 场景原文 |
| summary | Text | NULL | 场景摘要 |
| created_at | DateTime | NOT NULL | |

#### `text_chunks` 表

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK | |
| story_version_id | Integer | FK → story_versions.id, NOT NULL | |
| chapter_id | Integer | FK → chapters.id, NULL | |
| scene_id | Integer | FK → scenes.id, NULL | |
| chunk_index | Integer | NOT NULL | 全局切块序号 |
| content | Text | NOT NULL | 切块文本内容 |
| token_count | Integer | NULL | Token 数 |
| chroma_id | String(64) | NULL | Chroma 向量 ID |
| created_at | DateTime | NOT NULL | |

---

### 1.3 知识抽取

#### `entities` 表

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK | |
| story_version_id | Integer | FK → story_versions.id, NOT NULL | |
| name | String(100) | NOT NULL | 实体原始名 |
| canonical_name | String(100) | NOT NULL | 归一化标准名 |
| entity_type | String(30) | NOT NULL | character / location / organization / item |
| description | Text | NULL | |
| aliases | JSON | DEFAULT '[]' | 别名列表 ["xxx", "yyy"] |
| created_at | DateTime | NOT NULL | |

#### `relationships` 表

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK | |
| story_version_id | Integer | FK → story_versions.id, NOT NULL | |
| entity_a_id | Integer | FK → entities.id, NOT NULL | |
| entity_b_id | Integer | FK → entities.id, NOT NULL | |
| relationship_type | String(50) | NOT NULL | 如 father_of / ally / enemy |
| description | Text | NULL | 关系描述 |
| confidence | Float | DEFAULT 1.0 | 抽取置信度 |
| created_at | DateTime | NOT NULL | |

#### `timeline_events` 表

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK | |
| story_version_id | Integer | FK → story_versions.id, NOT NULL | |
| event_description | Text | NOT NULL | 事件描述 |
| chapter_id | Integer | FK → chapters.id, NULL | |
| scene_id | Integer | FK → scenes.id, NULL | |
| order_index | Integer | NOT NULL | 时间排序序号 |
| participants | JSON | DEFAULT '[]' | 参与实体 ID 列表 |
| created_at | DateTime | NOT NULL | |

#### `risk_segments` 表

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK | |
| story_version_id | Integer | FK → story_versions.id, NOT NULL | |
| chapter_id | Integer | FK → chapters.id, NULL | |
| original_text | Text | NOT NULL | 原始敏感文本 |
| rewritten_text | Text | NOT NULL | 文艺化改写版本 |
| risk_level | String(10) | NOT NULL | low / medium / high |
| created_at | DateTime | NOT NULL | |

---

### 1.4 用户画像

#### `user_profiles` 表

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK | |
| user_id | Integer | FK → users.id, UNIQUE, NOT NULL | 一个用户仅一份全局画像 |
| preferences | JSON | DEFAULT '{}' | {reading_style, difficulty_level, moral_tendency, ...} |
| created_at | DateTime | NOT NULL | |
| updated_at | DateTime | NOT NULL | |

#### `story_profiles` 表

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK | |
| user_id | Integer | FK → users.id, NOT NULL | |
| story_id | Integer | FK → stories.id, NOT NULL | |
| overrides | JSON | DEFAULT '{}' | {world_identity, npc_relations, stage_goals, ...} |
| created_at | DateTime | NOT NULL | |
| updated_at | DateTime | NOT NULL | |

UNIQUE(user_id, story_id)

---

### 1.5 会话与游玩

#### `sessions` 表

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK | |
| user_id | Integer | FK → users.id, NOT NULL | |
| story_id | Integer | FK → stories.id, NOT NULL | |
| story_version_id | Integer | FK → story_versions.id, NOT NULL | 创建时绑定的版本 |
| rag_config_id | Integer | FK → rag_configs.id, NOT NULL | 创建时绑定的方案 |
| mode | String(10) | NOT NULL | 'strict' 或 'creative' |
| opening_goal | Text | NOT NULL | 用户输入的冒险目标 |
| style_config | JSON | DEFAULT '{}' | {literary_level, pacing, difficulty} |
| status | String(15) | NOT NULL, DEFAULT 'active' | active / archived |
| turn_count | Integer | DEFAULT 0 | |
| created_at | DateTime | NOT NULL | |
| updated_at | DateTime | NOT NULL | |

#### `session_states` 表

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK | |
| session_id | Integer | FK → sessions.id, NOT NULL | |
| turn_number | Integer | NOT NULL | 0 = 初始状态 |
| state | JSON | NOT NULL | {current_location, active_goal, important_items: [], npc_relations: {}} |
| created_at | DateTime | NOT NULL | |

#### `session_events` 表

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK | |
| session_id | Integer | FK → sessions.id, NOT NULL | |
| turn_number | Integer | NOT NULL | |
| event_type | String(30) | NOT NULL | action / state_change / system |
| content | JSON | NOT NULL | 事件内容 |
| created_at | DateTime | NOT NULL | |

#### `session_messages` 表

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK | |
| session_id | Integer | FK → sessions.id, NOT NULL | |
| turn_number | Integer | NOT NULL | |
| role | String(10) | NOT NULL | 'user' / 'assistant' / 'system' |
| content | Text | NOT NULL | 消息正文 |
| metadata | JSON | DEFAULT '{}' | {retrieved_chunks_count, prompt_token_count, ...} |
| created_at | DateTime | NOT NULL | |

#### `user_feedback` 表

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK | |
| session_id | Integer | FK → sessions.id, NOT NULL | |
| message_id | Integer | FK → session_messages.id, NOT NULL | |
| feedback_type | String(30) | NOT NULL | setting_error / preference_mismatch / other |
| content | Text | NULL | 用户补充说明 |
| reviewed | Boolean | DEFAULT false | 管理员是否已查看 |
| created_at | DateTime | NOT NULL | |

---

### 1.6 RAG 与提示词配置

#### `rag_configs` 表

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK | |
| name | String(50) | NOT NULL | 如 "朴素混合RAG" |
| variant_type | String(20) | NOT NULL | 'naive_hybrid' / 'parent_child' / 'structured' |
| config | JSON | NOT NULL | 方案专属参数（top_k, bm25_weight 等） |
| is_active | Boolean | DEFAULT false | 当前生效 |
| created_at | DateTime | NOT NULL | |
| updated_at | DateTime | NOT NULL | |

约束：全局最多一个 `is_active=true`。

#### `prompt_templates` 表

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK | |
| name | String(50) | NOT NULL | 如 "system_rules" |
| layer | String(20) | NOT NULL | system / retrieval / gm / style |
| template_text | Text | NOT NULL | 提示词模板正文 |
| applicable_mode | String(10) | DEFAULT 'all' | 'strict' / 'creative' / 'all' |
| is_active | Boolean | DEFAULT true | |
| version | Integer | DEFAULT 1 | |
| created_at | DateTime | NOT NULL | |
| updated_at | DateTime | NOT NULL | |

---

### 1.7 评测

#### `eval_runs` 表

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK | |
| rag_config_id | Integer | FK → rag_configs.id, NOT NULL | |
| story_version_id | Integer | FK → story_versions.id, NOT NULL | |
| status | String(15) | NOT NULL, DEFAULT 'pending' | pending / running / completed / failed |
| total_cases | Integer | DEFAULT 0 | |
| avg_faithfulness | Float | NULL | 忠实性平均分 |
| avg_story_quality | Float | NULL | 叙事质量平均分 |
| error_message | Text | NULL | |
| started_at | DateTime | NULL | |
| completed_at | DateTime | NULL | |
| created_at | DateTime | NOT NULL | |

#### `eval_cases` 表

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK | |
| story_version_id | Integer | FK → story_versions.id, NOT NULL | |
| case_type | String(30) | NOT NULL | fact_qa / timeline_qa / consistency / gm_adjudication / personalization |
| question | Text | NOT NULL | 测试问题 |
| evidence_spans | JSON | DEFAULT '[]' | 预期证据片段引用 |
| rubric | Text | NULL | 评分规则描述 |
| created_at | DateTime | NOT NULL | |

#### `eval_results` 表

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK | |
| eval_run_id | Integer | FK → eval_runs.id, NOT NULL | |
| eval_case_id | Integer | FK → eval_cases.id, NOT NULL | |
| generated_answer | Text | NOT NULL | 模型生成的回答 |
| retrieved_context | JSON | DEFAULT '[]' | 检索到的上下文摘要 |
| structured_facts_used | JSON | DEFAULT '[]' | 使用的结构化事实 |
| faithfulness_score | Float | NULL | 0-1 |
| story_quality_score | Float | NULL | 0-1 |
| judge_reasoning | Text | NULL | 评委打分理由 |
| created_at | DateTime | NOT NULL | |

---

### 1.8 入库管线

#### `ingestion_jobs` 表

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK | |
| story_id | Integer | FK → stories.id, NOT NULL | |
| story_version_id | Integer | FK → story_versions.id, NULL | 入库完成后回填 |
| status | String(15) | NOT NULL, DEFAULT 'pending' | pending / running / completed / failed |
| progress | Float | DEFAULT 0.0 | 0.0-1.0 |
| steps_completed | JSON | DEFAULT '[]' | 已完成步骤列表 |
| error_message | Text | NULL | |
| started_at | DateTime | NULL | |
| completed_at | DateTime | NULL | |
| created_at | DateTime | NOT NULL | |

#### `ingestion_warnings` 表

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK | |
| job_id | Integer | FK → ingestion_jobs.id, NOT NULL | |
| warning_type | String(30) | NOT NULL | parse_error / entity_conflict / scene_boundary_uncertain |
| message | Text | NOT NULL | |
| chapter_id | Integer | FK → chapters.id, NULL | |
| created_at | DateTime | NOT NULL | |

---

### 1.9 审计

#### `audit_logs` 表

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK | |
| admin_id | Integer | FK → users.id, NOT NULL | |
| action | String(50) | NOT NULL | 如 story_upload / story_delete / rag_switch / prompt_update |
| target_type | String(30) | NULL | story / rag_config / prompt / session |
| target_id | Integer | NULL | |
| details | JSON | DEFAULT '{}' | 变更详情 |
| created_at | DateTime | NOT NULL | |

---

## 2. API 端点

### 2.1 鉴权 `/api/auth`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| POST | `/api/auth/register` | 注册 | 无 |
| POST | `/api/auth/login` | 登录，返回 JWT | 无 |
| POST | `/api/auth/logout` | 退出（前端清除 token） | Bearer |
| GET | `/api/auth/me` | 获取当前用户信息 | Bearer |

**POST /api/auth/register**
```json
// Request
{"username": "str 3-20", "password": "str >=8", "display_name": "str 1-30"}
// Response 201
{"id": 1, "username": "xxx", "display_name": "xxx", "role": "player"}
// Error 409
{"detail": "用户名已存在"}
```

**POST /api/auth/login**
```json
// Request
{"username": "str", "password": "str"}
// Response 200
{"access_token": "jwt...", "token_type": "bearer", "user": {...}}
// Error 401
{"detail": "用户名或密码错误"}
```

---

### 2.2 用户 `/api/users`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/api/users/me/profile` | 获取我的全局画像 | Bearer |
| GET | `/api/users/me/profile/story/{story_id}` | 获取我在某作品的覆写画像 | Bearer |
| PUT | `/api/users/me/settings` | 更新昵称/头像/简介 | Bearer |
| POST | `/api/users/me/profile/import` | 上传角色卡 JSON | Bearer |

---

### 2.3 故事 `/api/stories`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/api/stories` | 列出所有已就绪作品 | Bearer |
| GET | `/api/stories/{id}` | 作品详情 | Bearer |

---

### 2.4 会话 `/api/sessions`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| POST | `/api/sessions` | 创建新会话 | Bearer |
| GET | `/api/sessions` | 列出我的会话 | Bearer |
| GET | `/api/sessions/{id}` | 会话详情（含状态） | Bearer(owner) |
| DELETE | `/api/sessions/{id}` | 硬删除会话 | Bearer(owner) |
| POST | `/api/sessions/{id}/archive` | 归档会话 | Bearer(owner) |
| GET | `/api/sessions/{id}/messages` | 获取消息列表 | Bearer(owner) |
| POST | `/api/sessions/{id}/messages` | 发送消息/行动（流式 SSE） | Bearer(owner) |
| GET | `/api/sessions/{id}/state` | 获取当前状态快照 | Bearer(owner) |
| POST | `/api/sessions/{id}/feedback` | 提交反馈 | Bearer(owner) |

**POST /api/sessions**
```json
// Request
{"story_id": 1, "mode": "strict", "opening_goal": "寻找失踪的公主..."}
// Response 201 (含系统生成的开场白)
{"id": 1, "story_id": 1, "mode": "strict", "status": "active",
 "opening_message": {"role": "assistant", "content": "你来到了..."}}
```

**POST /api/sessions/{id}/messages** — SSE 流式
```json
// Request
{"content": "我查看四周"}
// Response: text/event-stream
// data: {"type": "token", "content": "你"}
// data: {"type": "token", "content": "注意到"}
// ...
// data: {"type": "choices", "choices": ["跟踪足迹", "询问路人", "查看告示牌"]}
// data: {"type": "state_update", "state": {"current_location": "森林入口"}}
// data: {"type": "done"}
```

---

### 2.5 管理员 - 作品管理 `/api/admin/stories`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/api/admin/stories` | 所有作品列表（含状态） | Admin |
| POST | `/api/admin/stories/upload` | 上传作品文件 | Admin |
| PUT | `/api/admin/stories/{id}` | 更新作品基础信息 | Admin |
| DELETE | `/api/admin/stories/{id}` | 软删除作品（设 `deleted_at`，关联数据保留但不再检索可见） | Admin |
| POST | `/api/admin/stories/{id}/ingest` | 触发入库 | Admin |
| POST | `/api/admin/stories/{id}/rollback` | 回滚到备份版本 | Admin |
| GET | `/api/admin/stories/{id}/ingestion-jobs` | 入库任务列表 | Admin |

---

### 2.6 管理员 - 元数据编辑 `/api/admin/stories/{story_id}/metadata`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `.../entities` | 列出实体 |
| POST | `.../entities` | 新增实体 |
| PUT | `.../entities/{id}` | 编辑实体 |
| DELETE | `.../entities/{id}` | 删除实体 |
| GET | `.../relationships` | 列出关系 |
| POST | `.../relationships` | 新增关系 |
| PUT | `.../relationships/{id}` | 编辑关系 |
| DELETE | `.../relationships/{id}` | 删除关系 |
| GET | `.../timeline` | 列出时间线事件 |
| POST | `.../timeline` | 新增事件 |
| PUT | `.../timeline/{id}` | 编辑事件 |
| DELETE | `.../timeline/{id}` | 删除事件 |
| GET | `.../chapters` | 列出章节与场景 |
| PUT | `.../chapters/{id}` | 编辑章节（标题/摘要） |
| PUT | `.../scenes/{id}` | 编辑场景（摘要/切分边界） |
| GET | `.../risk-segments` | 列出敏感段落 |
| PUT | `.../risk-segments/{id}` | 编辑改写版本 |

所有元数据编辑接口均需 Admin 权限。

---

### 2.7 管理员 - 提示词 `/api/admin/prompts`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/prompts` | 列出所有提示词模板 |
| PUT | `/api/admin/prompts/{id}` | 更新提示词内容 |
| POST | `/api/admin/prompts` | 新增提示词模板 |

---

### 2.8 管理员 - RAG 配置 `/api/admin/rag-configs`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/rag-configs` | 列出所有方案 |
| PUT | `/api/admin/rag-configs/{id}` | 更新方案参数 |
| POST | `/api/admin/rag-configs/{id}/activate` | 激活某方案 |

---

### 2.9 管理员 - 评测 `/api/admin/eval`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/admin/eval/runs` | 发起新评测 |
| GET | `/api/admin/eval/runs` | 列出评测运行 |
| GET | `/api/admin/eval/runs/{id}` | 评测运行详情 |
| GET | `/api/admin/eval/runs/{id}/results` | 评测结果列表 |
| POST | `/api/admin/eval/sample-sessions` | 抽取会话样本评测 |

---

### 2.10 管理员 - 会话查看 `/api/admin/sessions`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/sessions` | 所有用户会话列表 |
| GET | `/api/admin/sessions/{id}/transcript` | 完整对话记录 |
| GET | `/api/admin/sessions/{id}/feedback` | 用户反馈列表 |

---

### 2.11 管理员 - 审计 `/api/admin/audit`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/audit-logs` | 操作日志列表（分页） |

---

## 3. 鉴权逻辑

### 3.1 JWT 流程

```
登录 → 服务端生成 JWT（含 user_id, role, exp）→ 返回给前端
前端 → 每次请求在 Header 带 Authorization: Bearer <token>
后端 → 中间件解码验证 → 注入 current_user 依赖
```

### 3.2 权限守卫

```python
# 依赖注入
async def get_current_user(token) -> User:      # 解码 JWT，查库，返回 User
async def require_admin(user) -> User:           # 检查 user.role == 'admin'
async def require_session_owner(session_id, user) -> Session:  # 检查 session.user_id == user.id
```

### 3.3 安全规则

- JWT 过期时间 60 分钟（可配置）。
- 密码存储使用 `passlib.hash.bcrypt`，rounds=12。
- 所有管理员接口使用 `Depends(require_admin)`。
- 所有用户数据接口使用 `Depends(require_session_owner)` 或按 `user_id` 过滤。

---

## 4. RAG 管线架构

### 4.1 入库管线（Ingestion Pipeline）

```
上传文件
    ↓
[1. Parser]     parse_pdf / parse_docx / parse_txt / parse_json
    ↓                返回：raw_text + detected_chapters[]
[2. Splitter]   detect_chapters → detect_scenes
    ↓                返回：chapters[] → scenes[]
[3. Chunker]    chunk_text → text_chunks[]
    ↓                返回：text_chunks[] (带 chapter_id, scene_id 引用)
[4. Extractor]  extract_entities → extract_relationships → extract_timeline
    ↓                调用 DeepSeek，返回结构化数据写入 DB
[5. Summarizer] summarize_chapters → summarize_scenes
    ↓                调用 DeepSeek，返回摘要写入 DB
[6. Safety]     detect_risk_segments → rewrite_segments
    ↓                调用 DeepSeek，返回改写版本写入 DB
[7. Indexer]    embed_chunks → store_in_chroma
                     调用 SiliconFlow Embedding，写入 ChromaDB
```

每步完成后更新 `ingestion_jobs.progress` 和 `steps_completed`。任一步失败记录到 `ingestion_warnings`，管线继续执行后续步骤（尽力而为）。

### 4.2 检索管线（Runtime Retrieval）

#### 方案 A — 朴素混合检索

```python
def retrieve_variant_a(query: str, story_version_id: int, config: dict):
    bm25_results = bm25_search(query, story_version_id, top_k=config["bm25_top_k"])
    vector_results = chroma_search(query, story_version_id, top_k=config["vector_top_k"])
    merged = reciprocal_rank_fusion(bm25_results, vector_results, weight=config["bm25_weight"])
    return merged[:config["final_top_k"]]
```

#### 方案 B — 父子块分层检索

```python
def retrieve_variant_b(query: str, story_version_id: int, config: dict):
    child_chunks = chroma_search(query, story_version_id, top_k=config["child_top_k"])
    parent_ids = {c.scene_id or c.chapter_id for c in child_chunks}
    parent_contexts = fetch_parent_summaries(parent_ids, expand=config["parent_expand"])
    return combine_parent_child(parent_contexts, child_chunks)
```

#### 方案 C — 结构化辅助检索

```python
def retrieve_variant_c(query: str, story_version_id: int, config: dict):
    mentioned_entities = extract_query_entities(query)  # 用 DeepSeek 从 query 中识别实体名
    entity_facts = fetch_entity_profiles(mentioned_entities, story_version_id)
    relation_facts = fetch_relationships(mentioned_entities, story_version_id)
    timeline_facts = fetch_relevant_events(mentioned_entities, story_version_id, top_k=config["event_top_k"])
    text_chunks = chroma_search(query, story_version_id, top_k=config["text_top_k"])
    return combine_structured_and_text(entity_facts, relation_facts, timeline_facts, text_chunks)
```

### 4.3 上下文拼装（Context Assembly）

```
[系统指令层]        系统规则 + 安全指令 + 模式指令
    +
[检索证据层]        按当前 RAG 方案检索到的内容
    +
[结构化事实层]      实体/关系/时间线（方案 C 独有，A/B 跳过）
    +
[会话状态层]        当前状态 JSON + 最近 N 条事件日志
    +
[用户画像层]        全局画像 + 当前作品覆写画像
    +
[对话历史层]        最近 M 轮对话消息
    +
[当前输入]          用户本轮行动/消息
```

当总 Token 超过预算时：
1. 先对检索证据做摘要压缩。
2. 缩减对话历史轮数。
3. 按模式优先级（见 PRD 4.4.3）决定保留顺序。

### 4.4 叙事生成（Narrative Generation）

#### 4.4.1 流式分隔符协议

模型输出分为两个区域，用固定分隔符 `\n---META---\n` 隔开：

```
你来到了一片幽暗的森林，枯叶在脚下发出细碎的声响。一位身披灰袍的老者正倚靠在古树旁，
似乎在等待着什么人...
---META---
{"choices":["上前与老者搭话","悄悄绕过他","查看周围环境"],"state_update":{"current_location":"幽暗森林入口","active_goal":"寻找失踪的公主","important_items":[],"npc_relations":{"灰袍老者":"初遇，态度未知"}},"internal_notes":"玩家刚进入场景，老者是关键NPC"}
```

- **分隔符前**：纯叙事文本，可直接流式逐 token 发送给前端。
- **分隔符后**：单行 JSON 元数据，不发送给前端，由服务端缓冲解析。
- 提示词中需明确指示模型遵守此格式，禁止在叙事文本中出现分隔符字符串。
- **解析容错（仍以上述为规范）**：`meta_parse` 可识别泄漏形态 `**META---` / `META---`（其后须出现 JSON）、**文末**单独一行 `---` 或 `-----+` 后接可解析且「像 META」的 JSON 对象（须含 `choices` / `options` / `state_update` 或扁平 state 键之一）、META 段外层的 \`\`\`json 围栏、以及从噪声中提取首个平衡花括号 JSON 对象；`MetaStreamSplitter` 在 JSON 未闭合前用 `_hr_json_withhold_start` 减少把 `{` 推给前端；`finalize` 在无 marker 时整缓冲再走 `parse_complete_model_output` 以兜住 HR+JSON。若仍无结构化 `choices`，对叙事**尾部约 60 行（约 4000 字上限）**的编号列表做保守兜底，支持 `1.` / `1、` / `1）` / `（1）` 等形态（2–4 条，优先文末连续块）。若仍为空且环境变量 `NARRATIVE_CHOICES_LLM_FALLBACK=true`，服务端再调用一次 DeepSeek 从叙事节选生成 2–4 条行动（`app/services/narrative/choice_fallback.py`）。落库 `session_messages.metadata` 中增加 `choices_source`：`model_json` / `narrative_regex` / `llm_fallback` / `none`，便于排障。
- **双阶段生成（可选）**：`NARRATIVE_TWO_PHASE_ENABLED=true` 时第一轮只流式叙事（`prompts.TWO_PHASE_ROUND_ONE_SUFFIX`），第二轮 `build_two_phase_meta_prompt` + `deepseek_chat` 非流式专出 META JSON；与 `NARRATIVE_SPLIT_CHOICES_LLM` 同时开启时**以双阶段为准**（engine 内对 split 第一轮关闭）。SSE 事件类型与顺序不变，回合墙钟与 token 成本上升。
- **推进与衔接（不向玩家展示）**：可选 META 键 `choice_beats`（与 `choices` 等长）落库于 `metadata`，供**下一回合**在 `build_generation_prompt` 前经 `turn_context.build_turn_hints_text` 注入「选中项隐含推进」类提示；玩家气泡仍仅展示叙事正文。`NARRATIVE_TURN_HINTS_ENABLED` / `NARRATIVE_STALL_BREAK_*` 控制回合提示与相邻 GM 相似度僵局提示；`NARRATIVE_INPUT_BRIDGE=true` 时多一次 DeepSeek 生成「叙事承接用」短句，**仅写入 prompt**，`session_messages` 中 user 行仍为玩家原文；`NARRATIVE_STRICT_CHOICE_REFINE=true` 且 `mode=strict` 时主流结束后再调用 `choice_refine.refine_strict_choices`，成功则 `metadata.choices_refined=true`。
- **前置假 META 卫生处理**：若模型在**首个**规范分隔符之前输出「【META JSON】」、单独一行 `` ```json `` 等，流式切分仍会把该段算进叙事；`strip_leaking_meta_suffix` 在截断重复 `---META---` 之后会调用 `strip_pre_marker_meta_leak` 剥掉上述尾部，再 `strip_incomplete_separator_tail`；前端 `stripMetaSuffixForDisplay` 与之同构，避免玩家气泡泄漏。
- **Markdown 伪字段尾段**：若叙事尾出现单独一行 `---` 后紧跟 `**choices:**` / `**choice_beats:**` 等（仍在 `---META---` 之前），由 `strip_pseudo_markdown_meta_tail` 截断（与近距 `---` 联动，窗口 12 行）；在 `strip_pre_marker_meta_leak` 之后执行；前端 `stripPseudoMarkdownMetaTail` 同构。
- **篇幅软提示**：`NARRATIVE_CONCISE_MODE=true`（默认）时在 `build_generation_prompt` 的 system 末尾追加一句略短叙事/选项建议，**非**硬截断；与 `seed_prompt_templates` 的 META_BLOCK 第 8 条互补。

#### 4.4.2 服务端流式处理流程

```
DeepSeek stream=true 逐 token 返回
    ↓
[阶段1: 叙事流式阶段]
    服务端逐 token 转发给前端（SSE type=token）
    同时在内存累积完整文本
    ↓ 检测到 "---META---" 分隔符
[阶段2: 元数据缓冲阶段]
    停止向前端发送 token
    缓冲后续所有 token 直到流结束
    ↓ 流结束
[阶段3: 解析与写入]
    解析 JSON → choices + state_update + internal_notes
    ↓
    校验 state_update（软约束，异常仅记录不拦截）
    写入 session_states
    写入 session_messages（叙事部分）
    写入 session_events
    记录 internal_notes 到日志
    ↓
    发送 SSE type=choices
    发送 SSE type=state_update
    发送 SSE type=done
```

#### 4.4.3 异常处理

- **JSON 解析失败**：叙事文本已发送给用户（不可撤回），choices 和 state_update 置空，本轮不更新状态，记录错误日志，向前端发送 `type=error` 提示"状态更新失败，不影响继续游玩"。
- **未检测到分隔符**：整段输出视为纯叙事文本，choices 和 state_update 置空，同上处理。
- **DeepSeek 风控拦截**：触发 `safety.py` 柔化重试流程。

#### 4.4.4 提示词同步与原始输出采样

- 仓库内 `scripts/seed_prompt_templates.py` 中的 `META_BLOCK` 与系统模板变更后，应在目标环境执行该脚本（或经管理端 `/api/admin/prompts` 等价更新），否则 DB 中仍可能是旧版提示，模型易偏离 `\n---META---\n` + JSON 协议。
- 本地调试可运行 `scripts/sample_narrative_meta_output.py`（`PYTHONPATH=.`、`--session-id` 或 `--fixture-user-prompt`），将模型完整原始输出写入 `logs/meta_samples/`（勿提交）；用于对照调整 `meta_parse` 或提示词。
- 流式/开场在 **`choices` 为空或存在 `parse_error`** 时，服务端会打 `narrative_meta_parse_issue` 警告日志并附带输出尾部截断，便于区分「未到 META」「JSON 截断」等；若已走 LLM 二次抽取仍为空，检查 `choice_fallback` 日志与 `DEEPSEEK_API_KEY`。

---

## 5. 日志与可观测性

### 5.1 应用日志

- 使用 `loguru` 写入文件 `logs/app.log`，按日切割。
- 日志级别：DEBUG（开发）/ INFO（生产）。

### 5.2 RAG 调用记录

每次叙事生成时，在 `session_messages.metadata` 中记录：

```json
{
  "rag_variant": "variant_c",
  "retrieved_chunks_count": 5,
  "structured_facts_count": 8,
  "profile_context_used": true,
  "prompt_token_count": 3200,
  "completion_token_count": 450,
  "total_latency_ms": 4500
}
```

### 5.3 评测调用记录

`eval_results` 表中的 `retrieved_context`、`structured_facts_used`、`judge_reasoning` 字段即为评测可追溯记录。
