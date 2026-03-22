"""一次性探测 DeepSeek：从 RAG/.env 读配置，不打印密钥。"""
from __future__ import annotations

import asyncio
import sys

from app.services.llm.deepseek import deepseek_chat


async def main() -> None:
    try:
        text = await deepseek_chat(
            [{"role": "user", "content": "Reply with exactly: ok"}],
            timeout=30.0,
        )
        print("OK", (text or "").strip()[:200])
    except Exception as e:  # noqa: BLE001
        print("FAIL", type(e).__name__, str(e)[:800])
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
