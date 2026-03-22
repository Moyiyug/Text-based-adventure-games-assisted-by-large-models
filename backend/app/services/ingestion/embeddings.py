"""SiliconFlow OpenAI 兼容 Embeddings API。参照 TECH_STACK / Phase 2.8。"""

from __future__ import annotations

import httpx

from app.core.config import settings


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """对一批文本做向量；空列表返回空。"""
    if not texts:
        return []
    if not settings.SILICONFLOW_API_KEY.strip():
        raise RuntimeError("SILICONFLOW_API_KEY 未配置，无法生成向量")

    base = settings.SILICONFLOW_BASE_URL.rstrip("/")
    url = f"{base}/embeddings"
    headers = {
        "Authorization": f"Bearer {settings.SILICONFLOW_API_KEY}",
        "Content-Type": "application/json",
    }
    out_vectors: list[list[float]] = []
    batch_size = 32
    async with httpx.AsyncClient() as client:
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            payload = {"model": settings.SILICONFLOW_EMBEDDING_MODEL, "input": batch}
            resp = await client.post(url, headers=headers, json=payload, timeout=120.0)
            resp.raise_for_status()
            data = resp.json()
            items = data.get("data") or []
            # OpenAI 风格按 index 排序
            items.sort(key=lambda x: x.get("index", 0))
            for item in items:
                vec = item.get("embedding")
                if isinstance(vec, list):
                    out_vectors.append([float(x) for x in vec])
            if len(items) != len(batch):
                raise RuntimeError(
                    f"Embedding 返回条数不一致: 期望 {len(batch)} 得到 {len(items)}"
                )
    return out_vectors
