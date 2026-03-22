"""插入三种 RAG 默认方案；首条 naive_hybrid 设为激活。用法：在 backend/ 下 PYTHONPATH=. python scripts/seed_rag_configs.py"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# 保证可导入 app
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.core.database import async_session_factory
from app.models.rag_config import RagConfig


DEFAULT_CONFIGS: list[dict] = [
    {
        "name": "朴素混合 RAG",
        "variant_type": "naive_hybrid",
        "config": {
            "bm25_top_k": 10,
            "vector_top_k": 10,
            "bm25_weight": 0.3,
            "final_top_k": 5,
        },
        "is_active": True,
    },
    {
        "name": "父子块分层检索",
        "variant_type": "parent_child",
        "config": {"child_top_k": 5, "parent_expand": 2},
        "is_active": False,
    },
    {
        "name": "结构化辅助检索",
        "variant_type": "structured",
        "config": {"text_top_k": 3, "event_top_k": 5},
        "is_active": False,
    },
]


async def main() -> None:
    async with async_session_factory() as db:
        res = await db.execute(select(RagConfig))
        if list(res.scalars().all()):
            print("rag_configs 已有数据，跳过")
            return
        for row in DEFAULT_CONFIGS:
            db.add(
                RagConfig(
                    name=row["name"],
                    variant_type=row["variant_type"],
                    config=row["config"],
                    is_active=row["is_active"],
                )
            )
        await db.commit()
        print("已插入 3 条 rag_configs")


if __name__ == "__main__":
    asyncio.run(main())
