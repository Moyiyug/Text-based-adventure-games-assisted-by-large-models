# 入库 / 预处理 RAG 验收快照（只读分析）

> 生成方式：读取 `RAG/data/app.db` 与目录结构，**不修改业务数据**。  
> 可重复执行：`cd RAG/backend && python scripts/inspect_ingestion_snapshot.py`

## 结论摘要

| 维度 | 结果 | 说明 |
|------|------|------|
| **文件落盘** | ✅ | `data/uploads/1/` 下存在源 txt（文件名正常） |
| **规则预处理** | ✅ | 已解析、分章、分场景并写入 **text_chunks** |
| **LLM 抽取/摘要/安全** | ❌ 未执行成功 | 入库任务在调用 **DeepSeek** 时返回 **HTTP 401** |
| **结构化知识库** | ❌ 为空 | `entities` / `relationships` / `timeline_events` / `risk_segments` 均为 **0** |
| **向量化（Chroma）** | ❌ 未写入 | `text_chunks.chroma_id` 全部为 **空**（192 条均未量纲化） |
| **作品状态** | `failed` | 与任务失败一致，玩家端 `GET /api/stories` 不会出现该作品 |

## 量化数据（当前库内 story_id=1、活跃版本 version_id=1）

- **章节**：4  
- **场景**：39  
- **切块**：192  
- **实体 / 关系 / 时间线 / 敏感段**：0 / 0 / 0 / 0  
- **章节摘要**：未生成（`summary` 长度 0，与未跑通 LLM 一致）  

## 失败原因（来自 `ingestion_jobs.error_message`）

- `Client error '401 Authorization Required' for url 'https://api.deepseek.com/chat/completions'`  
- 已完成步骤（`steps_completed`）：`parse` → `split_chapters` → `persist_chunks`  
- 进度约 **0.4** 后中断，符合「切块落库之后、进入 DeepSeek 抽取环节」的失败位置。  

## 建议操作（验收「完整 RAG 预处理」前）

1. **核对 `.env`**：`DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL` 是否与当前账号/套餐一致；401 多为 Key 无效、过期或未开通该端点。  
2. **勿将 `.env` 提交 Git**；若 Key 曾暴露在聊天/截图中，建议轮换。  
3. Key 修复后：在管理端对该作品 **再次触发入库**（`POST .../ingest`），观察任务是否走完 `extract_summarize` → `index`，且 `chroma_id` 非空。  
4. **SiliconFlow**：向量写入依赖 `SILICONFLOW_API_KEY`；即使 DeepSeek 修好，若 Embedding 失败，会在警告中体现且可能仍无 `chroma_id`。  

## 对「肤浅自动预处理」的一句话评价

- **不调用模型的结构流水线**（解析 + 章节/场景边界 + 切块）对你这本小说 **已跑出可用规模**（4 章 / 39 场 / 192 块）。  
- **依赖 DeepSeek 的「RAG 语义准备」**（实体、关系、时间线、摘要、敏感改写、再往后 SiliconFlow 向量）**当前整段未成功**，需先解决 **401** 后复验。  

---

*本文件遵循 `ChatsDocs/RULES.md`，仅作验收记录，不含任何密钥。*
