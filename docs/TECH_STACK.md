# TECH_STACK.md — 技术栈

> 版本：V1
> 最后更新：2026-03-19
> 原则：锁定具体版本号，消除依赖幻觉。安装时使用 `==` 精确版本。

---

## 1. 总体架构

```
┌─────────────────────────────────────────────────┐
│              用户浏览器（桌面端）                  │
│              React + Vite SPA                    │
│              :5173 (dev)                         │
└──────────────────┬──────────────────────────────┘
                   │ HTTP / SSE
┌──────────────────▼──────────────────────────────┐
│              FastAPI 后端                         │
│              :8000 (uvicorn)                     │
│  ┌──────────┬──────────┬──────────┬──────────┐  │
│  │ Auth API │ Story API│ Play API │ Admin API│  │
│  └────┬─────┴────┬─────┴────┬─────┴────┬─────┘  │
│       │          │          │          │         │
│  ┌────▼──────────▼──────────▼──────────▼─────┐  │
│  │         RAG Pipeline Layer                │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐     │  │
│  │  │Variant A│ │Variant B│ │Variant C│     │  │
│  │  └─────────┘ └─────────┘ └─────────┘     │  │
│  └──────────────────┬────────────────────────┘  │
│                     │                            │
│  ┌──────────────────▼────────────────────────┐  │
│  │              Storage Layer                │  │
│  │  SQLite (业务) + Chroma (向量) + 文件系统  │  │
│  └───────────────────────────────────────────┘  │
└──────────────────┬──────────────────────────────┘
                   │ HTTPS API Calls
        ┌──────────▼──────────┐
        │    外部 AI 服务      │
        │  DeepSeek API (生成) │
        │  SiliconFlow API     │
        │  (Embedding)         │
        └─────────────────────┘
```

---

## 2. 后端技术栈

### 2.1 运行时

| 组件 | 版本 | 说明 |
|------|------|------|
| Python | `>=3.12, <4.0` | 主语言。workspace 已有 3.13 可直接使用 |

### 2.2 Web 框架

| 包名 | 版本 | 说明 |
|------|------|------|
| fastapi | `==0.135.1` | 异步 Web 框架 |
| uvicorn[standard] | `>=0.34.0` | ASGI 服务器 |
| pydantic | `>=2.10.0` | 数据校验与序列化 |
| pydantic-settings | `>=2.7.0` | 环境变量管理 |
| python-multipart | `>=0.0.18` | 文件上传支持 |

### 2.3 数据库与 ORM

| 包名 | 版本 | 说明 |
|------|------|------|
| sqlalchemy | `>=2.0.36` | ORM + 数据库抽象层 |
| alembic | `>=1.14.0` | 数据库迁移工具（为未来迁移到 Postgres 预留） |
| aiosqlite | `>=0.20.0` | SQLite 异步驱动 |

### 2.4 鉴权

| 包名 | 版本 | 说明 |
|------|------|------|
| python-jose[cryptography] | `>=3.3.0` | JWT 令牌生成与验证 |
| passlib[bcrypt] | `>=1.7.4` | 密码哈希 |
| bcrypt | `>=4.2.0` | bcrypt 实现 |

### 2.5 AI / RAG 核心

| 包名 | 版本 | 说明 |
|------|------|------|
| langchain | `==1.2.12` | RAG 编排框架 |
| langchain-core | `==1.2.20` | LangChain 核心抽象 |
| langchain-community | `>=0.3.0` | 社区集成 |
| langchain-openai | `>=0.3.0` | OpenAI 兼容接口（DeepSeek/SiliconFlow 均兼容 OpenAI 格式） |
| chromadb | `==1.5.5` | 本地向量数据库 |
| rank-bm25 | `>=0.2.2` | BM25 关键词检索 |
| tiktoken | `>=0.8.0` | Token 计数 |

### 2.6 文档解析

| 包名 | 版本 | 说明 |
|------|------|------|
| pypdf | `>=5.0.0` | PDF 文本提取 |
| python-docx | `>=1.1.0` | DOCX 文本提取 |
| chardet | `>=5.2.0` | 文本编码检测 |

### 2.7 工具库

| 包名 | 版本 | 说明 |
|------|------|------|
| httpx | `>=0.28.0` | 异步 HTTP 客户端 |
| aiofiles | `>=24.1.0` | 异步文件操作 |
| loguru | `>=0.7.3` | 结构化日志 |

---

## 3. 前端技术栈

### 3.1 核心框架

| 包名 | 版本 | 说明 |
|------|------|------|
| react | `>=19.0.0` | UI 框架 |
| react-dom | `>=19.0.0` | DOM 渲染 |
| typescript | `>=5.7.0` | 类型安全 |
| vite | `>=6.2.0` | 构建工具与开发服务器 |
| @vitejs/plugin-react | `>=4.3.0` | React Vite 插件 |

### 3.2 路由与状态

| 包名 | 版本 | 说明 |
|------|------|------|
| react-router-dom | `>=7.0.0` | 客户端路由 |
| zustand | `>=5.0.0` | 轻量客户端状态管理 |
| @tanstack/react-query | `>=5.60.0` | 服务端数据获取与缓存 |

### 3.3 UI 组件与样式

| 包名 | 版本 | 说明 |
|------|------|------|
| tailwindcss | `>=4.0.0` | 原子化 CSS 框架 |
| @radix-ui/react-dialog | `>=1.1.0` | 无障碍对话框原语 |
| @radix-ui/react-dropdown-menu | `>=2.1.0` | 无障碍下拉菜单原语 |
| @radix-ui/react-tabs | `>=1.1.0` | 无障碍标签页原语 |
| @radix-ui/react-tooltip | `>=1.1.0` | 无障碍工具提示原语 |
| @radix-ui/react-collapsible | `>=1.1.0` | 无障碍折叠面板原语 |
| lucide-react | `>=0.460.0` | 图标库 |
| clsx | `>=2.1.0` | 条件 className 工具 |
| tailwind-merge | `>=2.6.0` | Tailwind 类名冲突合并 |

### 3.4 功能库

| 包名 | 版本 | 说明 |
|------|------|------|
| axios | `>=1.7.0` | HTTP 客户端 |
| react-markdown | `>=9.0.0` | Markdown 渲染（叙事文本中可能有格式） |
| recharts | `>=2.15.0` | 图表（评测面板用） |
| react-hot-toast | `>=2.4.0` | 轻量通知提示 |

### 3.5 开发工具

| 包名 | 版本 | 说明 |
|------|------|------|
| eslint | `>=9.0.0` | 代码检查 |
| prettier | `>=3.4.0` | 代码格式化 |
| @types/react | `>=19.0.0` | React 类型定义 |
| @types/react-dom | `>=19.0.0` | React DOM 类型定义 |

---

## 4. 外部 AI 服务

### 4.1 DeepSeek API（文本生成）

| 项目 | 值 |
|------|---|
| 用途 | 所有文本生成任务：叙事、实体抽取、摘要、敏感改写、评测评委 |
| 接口格式 | OpenAI 兼容 Chat Completions API |
| 基础 URL | `https://api.deepseek.com` |
| 推荐模型 | `deepseek-chat`（通用对话）；如需推理可选 `deepseek-reasoner` |
| 鉴权 | Bearer Token，存储在本地 `.env` |
| 调用方式 | 通过 `langchain-openai` 的 `ChatOpenAI` 类，设置 `base_url` |
| 流式 | 支持，使用 SSE stream=true |

### 4.2 硅基流动 SiliconFlow API（Embedding）

| 项目 | 值 |
|------|---|
| 用途 | 文本向量化 |
| 接口格式 | OpenAI 兼容 Embeddings API |
| 基础 URL | `https://api.siliconflow.cn/v1` |
| 推荐模型 | `BAAI/bge-m3`（多语言，中文表现优秀，1024 维） |
| 备选模型 | `BAAI/bge-large-zh-v1.5`（纯中文优化） |
| 鉴权 | Bearer Token，存储在本地 `.env` |
| 调用方式 | 通过 `langchain-openai` 的 `OpenAIEmbeddings` 类，设置 `base_url` |
| 免费额度 | 有免费额度，超出后按量计费，价格极低 |

---

## 5. 数据存储

| 存储 | 技术 | 存什么 |
|------|------|--------|
| 业务数据库 | SQLite（via SQLAlchemy + aiosqlite） | 账号、会话、画像、作品元数据、实体关系时间线、评测结果、配置、审计日志。路径：`data/app.db` |
| 向量数据库 | ChromaDB（本地持久化模式） | 文本切块向量索引。路径：`data/chroma/` |
| 文件存储 | 本地文件系统 | 原始上传文件。路径：`data/uploads/` |

### 5.1 迁移预留

- SQLAlchemy 的数据库 URL 通过环境变量配置，未来可直接切换为 `postgresql+asyncpg://...`。
- Alembic 管理所有 schema 变更，确保可迁移。
- ChromaDB 可替换为其他 LangChain 支持的向量存储。
- 文件存储路径可配置，未来可改为对象存储接口。

---

## 6. 开发工具

| 工具 | 用途 |
|------|------|
| Git | 版本控制 |
| npm | 前端包管理 |
| pip + venv / uv | 后端包管理与虚拟环境 |
| Alembic | 数据库迁移 |
| pytest | 后端单元测试与集成测试 |
| Vitest | 前端组件测试 |

---

## 7. 环境变量模板（`.env.example`）

```env
# === DeepSeek ===
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# === SiliconFlow Embedding ===
SILICONFLOW_API_KEY=sk-xxx
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
SILICONFLOW_EMBEDDING_MODEL=BAAI/bge-m3

# === Database ===
DATABASE_URL=sqlite+aiosqlite:///./data/app.db

# === ChromaDB ===
CHROMA_PERSIST_DIR=./data/chroma

# === Upload ===
UPLOAD_DIR=./data/uploads

# === JWT ===
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60

# === App ===
APP_ENV=development
APP_DEBUG=true
CORS_ORIGINS=http://localhost:5173
```

---

## 8. 项目目录结构

```
RAG/
├── frontend/                    # React + Vite 前端
│   ├── public/
│   ├── src/
│   │   ├── api/                 # API 客户端封装
│   │   ├── components/          # 可复用 UI 组件
│   │   │   ├── ui/              # 基础原子组件
│   │   │   ├── layout/          # 布局组件
│   │   │   ├── story/           # 故事相关组件
│   │   │   ├── play/            # 游玩页组件
│   │   │   └── admin/           # 管理后台组件
│   │   ├── pages/               # 页面组件
│   │   ├── stores/              # Zustand 状态仓库
│   │   ├── hooks/               # 自定义 Hooks
│   │   ├── types/               # TypeScript 类型定义
│   │   ├── utils/               # 工具函数
│   │   ├── styles/              # 全局样式
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── index.html
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   └── package.json
│
├── backend/                     # FastAPI 后端
│   ├── app/
│   │   ├── api/                 # 路由层
│   │   │   ├── auth.py
│   │   │   ├── stories.py
│   │   │   ├── sessions.py
│   │   │   ├── users.py
│   │   │   └── admin/
│   │   │       ├── stories.py
│   │   │       ├── metadata.py
│   │   │       ├── prompts.py
│   │   │       ├── rag_config.py
│   │   │       ├── eval.py
│   │   │       ├── sessions.py
│   │   │       └── audit.py
│   │   ├── core/                # 核心配置
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   ├── security.py
│   │   │   └── dependencies.py
│   │   ├── models/              # SQLAlchemy 模型
│   │   ├── schemas/             # Pydantic 模型
│   │   ├── services/            # 业务逻辑层
│   │   │   ├── auth.py
│   │   │   ├── story.py
│   │   │   ├── ingestion/       # 入库管线
│   │   │   │   ├── parser.py
│   │   │   │   ├── chunker.py
│   │   │   │   ├── extractor.py
│   │   │   │   ├── summarizer.py
│   │   │   │   ├── safety.py
│   │   │   │   ├── indexer.py
│   │   │   │   └── pipeline.py
│   │   │   ├── rag/             # RAG 方案
│   │   │   │   ├── base.py
│   │   │   │   ├── variant_a.py
│   │   │   │   ├── variant_b.py
│   │   │   │   ├── variant_c.py
│   │   │   │   ├── dispatcher.py
│   │   │   │   └── context.py
│   │   │   ├── narrative/       # 叙事引擎
│   │   │   │   ├── engine.py
│   │   │   │   ├── state.py
│   │   │   │   ├── prompts.py
│   │   │   │   └── safety.py
│   │   │   ├── profile.py       # 画像系统
│   │   │   └── eval.py          # 评测系统
│   │   └── main.py              # FastAPI 入口
│   ├── alembic/                 # 数据库迁移
│   ├── tests/                   # 测试
│   ├── alembic.ini
│   └── requirements.txt
│
├── data/                        # 运行时数据（gitignore）
│   ├── app.db
│   ├── chroma/
│   └── uploads/
│
├── docs/                        # 规范文档
│   ├── PRD.md
│   ├── APP_FLOW.md
│   ├── TECH_STACK.md
│   ├── FRONTEND_GUIDELINES.md
│   ├── BACKEND_STRUCTURE.md
│   └── IMPLEMENTATION_PLAN.md
│
├── .env.example
├── .gitignore
└── README.md
```
