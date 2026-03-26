from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ 目录，所有相对路径以此为基准
BASE_DIR = Path(__file__).resolve().parent.parent.parent
# RAG/ 根目录（.env 放在此处）
RAG_ROOT = BASE_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(RAG_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        # 环境变量优先于 .env；若系统里存在空的 DEEPSEEK_API_KEY= 等，勿让其覆盖 .env
        env_ignore_empty=True,
    )

    # --- DeepSeek ---
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # --- SiliconFlow Embedding ---
    SILICONFLOW_API_KEY: str = ""
    SILICONFLOW_BASE_URL: str = "https://api.siliconflow.cn/v1"
    SILICONFLOW_EMBEDDING_MODEL: str = "BAAI/bge-m3"

    # --- Database ---
    DATABASE_URL: str = "sqlite+aiosqlite:///../data/app.db"

    # --- ChromaDB ---
    CHROMA_PERSIST_DIR: str = "../data/chroma"

    # --- Upload ---
    UPLOAD_DIR: str = "../data/uploads"

    # --- JWT ---
    JWT_SECRET_KEY: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # --- Narrative safety (Phase 4.6) ---
    # 为 True 时：开场在落库前对叙事正文额外调用一次 DeepSeek 做软化（流式回合暂不软化，避免与已推送 token 不一致）。
    NARRATIVE_SAFETY_SOFTEN: bool = False

    # --- Choices LLM fallback ---
    # 当 META JSON 与正文编号兜底均未得到选项时，再调用一次 DeepSeek 生成 2～4 条行动（仅服务端，不改变 SSE 协议）。
    NARRATIVE_CHOICES_LLM_FALLBACK: bool = True
    NARRATIVE_CHOICES_LLM_MAX_INPUT_CHARS: int = 3500

    # --- Narrative progression / turn hints（不向玩家展示，仅注入 prompt）---
    NARRATIVE_TURN_HINTS_ENABLED: bool = True
    NARRATIVE_STALL_BREAK_ENABLED: bool = True
    # 相邻两轮 GM 词 Jaccard 大于等于该值时追加「僵局打破」提示。
    NARRATIVE_STALL_SIMILARITY_THRESHOLD: float = 0.55

    # 为 True 时：落库 user 原文不变，仅在生成用 messages 中追加「叙事承接用」桥接句（多一次 DeepSeek）。
    NARRATIVE_INPUT_BRIDGE: bool = False

    # 为 True 且 session.mode=strict 时：主流结束后对最终 choices/choice_beats 再调一次 DeepSeek 精炼。
    NARRATIVE_STRICT_CHOICE_REFINE: bool = False

    # 为 True 时：主流/开场第一轮只产出叙事+state 的 META，选项由第二次 DeepSeek 调用生成（与第一轮同检索证据块，见 choice_synthesis_rag）。
    NARRATIVE_SPLIT_CHOICES_LLM: bool = False

    # 为 True 时：第一轮只流式叙事（无 META），第二轮非流式专出 ---META--- + JSON（与 SPLIT_CHOICES 二选一：本开关优先，另一自动关闭语义见 engine 注释）。
    NARRATIVE_TWO_PHASE_ENABLED: bool = False

    # 为 True 时：在生成用 system 消息末尾追加一句「略短叙事」软提示（非硬截断，见 prompts.build_generation_prompt）。
    NARRATIVE_CONCISE_MODE: bool = True

    # --- Choice grounding (Phase 9)：合并原 strict refine 与事实对齐；与 NARRATIVE_STRICT_CHOICE_REFINE 互斥（回合 SSE 路径）。---
    NARRATIVE_CHOICE_GROUNDING_ENABLED: bool = True
    # 每轮一次 DeepSeek 调用计 1；含 grounding_ok 判定与定稿选项，至多如此次数。
    NARRATIVE_CHOICE_GROUNDING_MAX_ATTEMPTS: int = 2
    NARRATIVE_CHOICE_GROUNDING_EVIDENCE_CHARS: int = 2500
    NARRATIVE_CHOICE_GROUNDING_NARRATIVE_CHARS: int = 3500
    # 为 False 时不向选项 grounding / refine / synthesize 注入时间线弧线块（回滚开关）。
    NARRATIVE_CHOICE_TIMELINE_HINT_ENABLED: bool = True
    # 选项「可能跳时间线」启发式：off 关闭；log 仅打日志；note 时在 grounding 第 2 次 attempt 的 note 中追加改写提示。
    NARRATIVE_CHOICE_TIMELINE_HEURISTIC_MODE: str = "off"

    # --- Turn wall-clock timing (Phase 10 / BACKEND_STRUCTURE §4.4.6) ---
    # true 时每轮 SSE 叙事在 INFO 打一条 turn_timing JSON（含 session_id、turn、各段 ms）。
    NARRATIVE_TURN_TIMING_LOG: bool = True
    # true 时在日志中附带 grounding 每 attempt 的 ms（grounding_attempt_1_ms 等）。
    NARRATIVE_TURN_TIMING_VERBOSE: bool = False

    # --- Profile inference (Phase 5) ---
    # false 时不调用 DeepSeek 推断画像（开发省成本）。
    PROFILE_INFERENCE_ENABLED: bool = False
    # 每 N 轮成功落库后异步触发一次推断（3～5 轮建议 4）。
    PROFILE_INFERENCE_EVERY_N_TURNS: int = 4
    # 参与推断的最近消息条数（user+assistant 各算一条）。
    PROFILE_INFERENCE_HISTORY_MESSAGES: int = 24
    PROFILE_INFERENCE_TEMPERATURE: float = 0.2
    # 角色卡 JSON 上传单文件上限（字节）。
    PROFILE_IMPORT_MAX_BYTES: int = 262144

    # --- Eval (Phase 6) ---
    EVAL_MAX_CASES_PER_RUN: int = 24
    EVAL_CONTEXT_TOKEN_BUDGET: int = 6000
    EVAL_GENERATE_TIMEOUT: float = 120.0
    EVAL_ANSWER_TIMEOUT: float = 90.0
    EVAL_JUDGE_TIMEOUT: float = 90.0
    # 会话消息 metadata 中 eval_grounding_context 最大字符数（防止 SQLite JSON 过大）。
    EVAL_SNAPSHOT_CONTEXT_MAX_CHARS: int = 120000

    # --- App ---
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def upload_dir_path(self) -> Path:
        p = Path(self.UPLOAD_DIR)
        if p.is_absolute():
            return p.resolve()
        return (BASE_DIR / p).resolve()

    @property
    def chroma_dir_path(self) -> Path:
        p = Path(self.CHROMA_PERSIST_DIR)
        if p.is_absolute():
            return p.resolve()
        return (BASE_DIR / p).resolve()


settings = Settings()
