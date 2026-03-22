# RULES.md — AI 会话全局规则手册

> 这是活文档。AI 犯错后应被要求更新此文件。
> 每次新会话或上下文切换时，AI 必须先读取本文件 + `progress.txt` + `lessons.md`。

---

## 1. 项目概要

交互式文字叙事冒险平台，复现多种 RAG 架构，使用低成本模型（DeepSeek）实现低幻觉内容生成。  
用户上传故事/小说 → 入库向量化 → 根据个人画像体验交互式冒险。

- 角色：`admin`（管理入库/配置/评测）、`player`（游玩/反馈）
- 仅桌面端（最小视口 1024px），不做移动端

---

## 2. 技术栈速查

| 层 | 技术 | 备注 |
|----|------|------|
| 前端 | React 19 + Vite + TypeScript | `RAG/frontend/` |
| 样式 | Tailwind CSS 4 + Radix UI + Lucide Icons | 不写自定义 CSS 类名 |
| 状态 | Zustand（客户端）+ React Query（服务端） | |
| 后端 | Python + FastAPI + Uvicorn | `RAG/backend/` |
| 数据库 | SQLite（SQLAlchemy + Alembic） | `data/app.db` |
| 向量库 | ChromaDB | `data/chroma/` |
| LLM | DeepSeek（生成/抽取/评测） | 仅文本，不做图像 |
| Embedding | SiliconFlow (BGE-M3) | 远程 API |

> 完整版本号 → `docs/TECH_STACK.md` §2-3

---

## 3. 命名规范速查

### 前端（TypeScript）

| 类型 | 格式 | 示例 |
|------|------|------|
| 页面组件 | `PascalCasePage.tsx` | `StoryLibraryPage.tsx` |
| UI 组件 | `PascalCase.tsx` | `Button.tsx`, `ChatBubble.tsx` |
| Hooks | `camelCase.ts` | `useSSEStream.ts` |
| Store | `camelCase.ts` | `authStore.ts` |
| API 封装 | `camelCase.ts` | `storyApi.ts` |
| 类型定义 | `camelCase.ts` | `session.ts` |
| Props 接口 | `XxxProps` | `ChatBubbleProps` |
| CSS 变量 | `--kebab-case` | `--bg-primary`, `--accent-primary` |

### 后端（Python）

| 类型 | 格式 | 示例 |
|------|------|------|
| 文件/模块 | `snake_case.py` | `variant_a.py` |
| ORM 模型 | `PascalCase` | `StoryVersion`, `SessionState` |
| Pydantic Schema | `PascalCase` | `RegisterRequest`, `TokenResponse` |
| API 路由函数 | `snake_case` | `create_session`, `upload_story` |
| 数据库表名 | `snake_case` 复数 | `stories`, `session_messages` |
| URL 路径 | `kebab-case` | `/api/admin/rag-configs` |

> 完整规范 → `docs/FRONTEND_GUIDELINES.md` §10, `docs/TECH_STACK.md` §8

---

## 4. 关键设计令牌

### 配色（游玩页 Dark Theme）

| 用途 | 变量 | 色值 |
|------|------|------|
| 背景 | `--bg-primary` | `#0F0F14` |
| 面板背景 | `--bg-secondary` | `#1A1A2E` |
| 主文本 | `--text-primary` | `#E8E0D4` |
| 主强调 | `--accent-primary` | `#D4A853` (琥珀金) |
| 次强调 | `--accent-secondary` | `#4ADE80` (翡翠绿) |
| 危险 | `--danger` | `#EF4444` |

### 间距 & 圆角

- 间距倍数：4px（`space-1` = 4px, `space-2` = 8px, ...）
- 默认圆角：`rounded-lg` (8px)
- 卡片圆角：`rounded-xl` (12px)

> 完整色板/管理端配色/字体/阴影 → `docs/FRONTEND_GUIDELINES.md` §2-5

---

## 5. 架构约束（必须遵守）

1. **SSE 流式只能用 `fetch + ReadableStream`**，不可用 `EventSource`（后端是 POST + Bearer 鉴权）
2. **叙事输出使用 `\n---META---\n` 分隔符协议**：纯文本在前，JSON 元数据在后 → `docs/BACKEND_STRUCTURE.md` §4.4
3. **JWT 鉴权**：所有 `/api/*` 需 Bearer token，`/api/admin/*` 额外需 `require_admin`
4. **公共组件按需创建**：不集中一次性构建，首次使用时创建，后续复用
5. **环境变量**：所有密钥放 `.env`，通过 `pydantic-settings` 读取，绝不硬编码
6. **数据库迁移**：任何 model 变更必须通过 `alembic revision --autogenerate` 生成迁移

---

## 6. 规范文档索引

| 问题域 | 查阅文档 | 关键章节 |
|--------|---------|---------|
| 做什么/不做什么/成功标准 | `docs/PRD.md` | §3 功能列表, §6 范围外, §7 成功标准 |
| 页面列表/用户流程/交互行为 | `docs/APP_FLOW.md` | §2 导航, §3 各页面流程 |
| 包版本/目录结构/环境变量 | `docs/TECH_STACK.md` | §2-3 版本, §7 .env, §8 目录树 |
| 色号/字体/组件视觉/动画 | `docs/FRONTEND_GUIDELINES.md` | §2-5 令牌, §6 组件, §8 动画 |
| 数据库表/API 端点/鉴权/管线 | `docs/BACKEND_STRUCTURE.md` | §1 Schema, §2 API, §3 鉴权, §4 管线 |
| 按步实施顺序/每日检查点 | `docs/IMPLEMENTATION_PLAN.md` | 各 Phase, 每日检查点表 |

---

## 7. 工作习惯

- 编码前用 **Ask/Plan 模式** 梳理架构，确认方案后再切 Agent 执行
- 每个任务必须引用规范文档具体章节（如 "参照 FRONTEND_GUIDELINES §6.8 实现状态面板"）
- 每个有效功能完成后：提交 Git → 更新 `progress.txt`
- 踩坑后更新 `lessons.md`
- 卡住超过 3 轮切 Debug mode
