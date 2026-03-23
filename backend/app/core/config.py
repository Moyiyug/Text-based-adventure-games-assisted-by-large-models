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
