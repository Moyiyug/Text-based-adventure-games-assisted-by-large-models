# RAG 交互式叙事冒险平台

基于多种 RAG 架构的交互式文字叙事冒险平台。用户上传故事/小说，系统向量化入库后，根据个人画像生成沉浸式交互冒险体验。

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | React 19 + Vite + TypeScript + Tailwind CSS 4 |
| 后端 | Python + FastAPI + Uvicorn |
| 数据库 | SQLite (SQLAlchemy + Alembic) |
| 向量库 | ChromaDB |
| LLM | DeepSeek |
| Embedding | SiliconFlow (BGE-M3) |

## 快速启动

### 1. 环境准备

```bash
# 复制环境变量模板并填入 API Key
cp .env.example .env
```

### 2. 启动后端

```bash
cd backend

# 安装依赖（使用项目虚拟环境）
pip install -r requirements.txt

# 执行数据库迁移
alembic upgrade head

# 启动开发服务器
uvicorn app.main:app --reload --port 8000
```

后端运行于 `http://localhost:8000`，Swagger 文档：`http://localhost:8000/docs`

### 3. 启动前端

```bash
cd frontend

# 安装依赖
npm install

# （可选）后端不是 8000 端口时，复制并修改代理目标
# copy .env.example .env

# 启动开发服务器
npm run dev
```

前端运行于 `http://localhost:5173`，开发模式下 `/api` 请求由 Vite 代理到 `VITE_DEV_API_PROXY`（默认 `http://localhost:8000`）。

**上传失败 / Not Found**：不要用浏览器直接打开 `dist` 文件测试上传；须 `npm run dev` 走代理。若仍失败，检查 axios 是否对 `FormData` 手动设置了 `Content-Type`（会缺少 `boundary`）。

## 项目结构

```
RAG/
├── frontend/          # React + Vite 前端
├── backend/           # FastAPI 后端
├── data/              # 运行时数据（gitignore）
├── docs/              # 规范文档
├── .env.example       # 环境变量模板
├── .gitignore
└── README.md
```

## 开发与多轮 LLM 测试

- **叙事回合真实 LLM soak**（经 HTTP + Bearer，消耗 DeepSeek token；脚本用 httpx 流式读 SSE，符合 RULES §5.1 语义；已 `trust_env=False` 避免系统代理把 localhost 走成 502）：  
  先启动后端，在 `backend/` 下设置 `SOAK_USERNAME`、`SOAK_PASSWORD`、`SOAK_STORY_ID`（及可选 `SOAK_API_BASE`、`SOAK_ROUNDS`），执行  
  `python scripts/narrative_llm_roundtrip_soak.py --rounds 20`。详见脚本文件头注释。
- **双阶段叙事**：`.env` 中 `NARRATIVE_TWO_PHASE_ENABLED=true` 时第一轮只流式正文、第二轮非流式生成 META；与 `NARRATIVE_SPLIT_CHOICES_LLM` 同时开启时以前者为准（见 `docs/BACKEND_STRUCTURE.md` §4.4）。

## 规范文档

| 文档 | 说明 |
|------|------|
| `docs/PRD.md` | 产品需求文档 |
| `docs/APP_FLOW.md` | 页面流程与交互 |
| `docs/TECH_STACK.md` | 技术栈与版本 |
| `docs/FRONTEND_GUIDELINES.md` | 前端设计规范 |
| `docs/BACKEND_STRUCTURE.md` | 后端架构与 API |
| `docs/IMPLEMENTATION_PLAN.md` | 分阶段实施计划 |
