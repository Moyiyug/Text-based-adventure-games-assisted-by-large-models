"""
DeepSeek 调用：与 PythonAgent 等项目中「OpenAI SDK + base_url」方式对齐，
避免裸 httpx 与官方 SDK 在路径/客户端行为上的差异；并显式关闭 trust_env 以防系统代理干扰。
参照 RULES.md、DeepSeek 官方 OpenAI 兼容说明。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

import httpx
from openai import APIConnectionError, APIStatusError, AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

# 与 LLMService 中思路一致：可重试的瞬时错误（非 401）
_RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}
_MAX_USER_RETRIES = 3
_BASE_DELAY_S = 1.0
_MAX_DELAY_S = 20.0


def _deepseek_api_key() -> str:
    """去掉首尾空白与 UTF-8 BOM，避免 .env 里不可见字符导致鉴权失败。"""
    k = (settings.DEEPSEEK_API_KEY or "").strip()
    if k.startswith("\ufeff"):
        k = k[1:].strip()
    if (k.startswith('"') and k.endswith('"')) or (k.startswith("'") and k.endswith("'")):
        k = k[1:-1].strip()
    return k


def _detail_from_status_error(e: APIStatusError) -> str:
    msg = getattr(e, "message", None) or ""
    if msg:
        return str(msg)[:2000]
    body = getattr(e, "body", None)
    if body is not None:
        return str(body)[:2000]
    resp = getattr(e, "response", None)
    if resp is not None:
        try:
            return (resp.text or "")[:2000]
        except Exception:  # noqa: BLE001
            pass
    return str(e)[:2000]


async def deepseek_chat(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.3,
    timeout: float = 120.0,
) -> str:
    """
    使用 AsyncOpenAI 调用 DeepSeek（与另一项目中 OpenAI(api_key, base_url=...) 一致）。
    - trust_env=False：不读取 HTTP(S)_PROXY，避免本机代理/抓包导致异常 401。
    - 连接超时单独放宽，避免冷启动 TLS 慢被误判失败。
    - SDK max_retries + 外层对 429/5xx 的指数退避，给服务端与网络留缓冲。
    """
    api_key = _deepseek_api_key()
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY 未配置，无法调用 DeepSeek API")

    base = settings.DEEPSEEK_BASE_URL.rstrip("/")
    connect_timeout = min(45.0, max(15.0, timeout * 0.25))
    httpx_timeout = httpx.Timeout(connect=connect_timeout, read=timeout, write=timeout, pool=timeout)

    http_client = httpx.AsyncClient(
        trust_env=False,
        timeout=httpx_timeout,
        limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
    )
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=base,
        http_client=http_client,
        max_retries=2,
    )

    last_err: Exception | None = None
    try:
        for attempt in range(_MAX_USER_RETRIES):
            try:
                resp = await client.chat.completions.create(
                    model=settings.DEEPSEEK_MODEL,
                    messages=messages,
                    temperature=temperature,
                )
                content = resp.choices[0].message.content
                return str(content or "")

            except APIStatusError as e:
                last_err = e
                code = getattr(e, "status_code", None) or 0
                if code == 401 or code == 403:
                    raise RuntimeError(f"DeepSeek HTTP {code}: {_detail_from_status_error(e)}") from e
                if code not in _RETRYABLE_STATUS and code < 500:
                    raise RuntimeError(f"DeepSeek HTTP {code}: {_detail_from_status_error(e)}") from e
                if attempt >= _MAX_USER_RETRIES - 1:
                    raise RuntimeError(f"DeepSeek HTTP {code}: {_detail_from_status_error(e)}") from e
                delay = min(_BASE_DELAY_S * (2**attempt), _MAX_DELAY_S)
                logger.warning(
                    "DeepSeek 可重试错误 status=%s，第 %s/%s 次，%.1fs 后重试",
                    code,
                    attempt + 1,
                    _MAX_USER_RETRIES,
                    delay,
                )
                await asyncio.sleep(delay)

            except APIConnectionError as e:
                last_err = e
                if attempt >= _MAX_USER_RETRIES - 1:
                    raise RuntimeError(
                        "DeepSeek 连接失败（已重试）。若仅本仓库失败，请检查是否被系统代理拦截；"
                        f"详情: {e}"
                    ) from e
                delay = min(_BASE_DELAY_S * (2**attempt), _MAX_DELAY_S)
                logger.warning("DeepSeek 连接失败，%.1fs 后重试: %s", delay, e)
                await asyncio.sleep(delay)

        if last_err:
            raise RuntimeError(f"DeepSeek 调用失败: {last_err}") from last_err
        raise RuntimeError("DeepSeek 调用失败: 未知原因")

    finally:
        await client.close()


async def deepseek_chat_stream(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.3,
    timeout: float = 120.0,
) -> AsyncIterator[str]:
    """
    流式输出文本 delta（不含工具调用）。错误时向上抛，由 narrative 层转 SSE error。
    """
    api_key = _deepseek_api_key()
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY 未配置，无法调用 DeepSeek API")

    base = settings.DEEPSEEK_BASE_URL.rstrip("/")
    connect_timeout = min(45.0, max(15.0, timeout * 0.25))
    httpx_timeout = httpx.Timeout(connect=connect_timeout, read=timeout, write=timeout, pool=timeout)

    http_client = httpx.AsyncClient(
        trust_env=False,
        timeout=httpx_timeout,
        limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
    )
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=base,
        http_client=http_client,
        max_retries=2,
    )
    try:
        stream = await client.chat.completions.create(
            model=settings.DEEPSEEK_MODEL,
            messages=messages,
            temperature=temperature,
            stream=True,
        )
        async for chunk in stream:
            choice0 = chunk.choices[0] if chunk.choices else None
            if choice0 is None:
                continue
            delta = getattr(choice0, "delta", None)
            if delta is None:
                continue
            piece = getattr(delta, "content", None)
            if piece:
                yield str(piece)
    finally:
        await client.close()
