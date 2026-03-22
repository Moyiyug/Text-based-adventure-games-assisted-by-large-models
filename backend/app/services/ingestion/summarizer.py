"""章节/场景摘要（DeepSeek，约 200 字内）。参照 IMPLEMENTATION_PLAN Phase 2.6。"""

from __future__ import annotations

import re

from app.services.llm.deepseek import deepseek_chat

# 场景正文短于此则不调模型摘要，避免套话回复
MIN_SCENE_TEXT_CHARS_FOR_LLM = 30

# 模型常见拒答/套话（小写匹配）
_SUMMARY_BOILERPLATE_PATTERNS = (
    r"请提供.*摘要",
    r"请给出.*场景",
    r"无法摘要",
    r"没有.*内容.*摘要",
    r"作为\s*(ai|人工智能|语言模型)",
    r"i cannot summarize",
    r"unable to summarize",
)


def is_junk_summary(text: str) -> bool:
    """是否为非叙事的模型套话，应丢弃且不写入库。"""
    t = (text or "").strip()
    if not t:
        return True
    for pat in _SUMMARY_BOILERPLATE_PATTERNS:
        if re.search(pat, t, re.IGNORECASE):
            return True
    return False


def _clamp_chinese_length(text: str, max_chars: int = 200) -> str:
    t = text.strip()
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 1] + "…"


async def summarize_chapter(chapter_text: str) -> str:
    sample = chapter_text[:16000]
    prompt = (
        "请用中文为下列小说章节写一段摘要，不超过 200 个汉字，不要列表或标题，一段即可。\n\n"
        f"{sample}"
    )
    raw = await deepseek_chat([{"role": "user", "content": prompt}], temperature=0.4)
    cleaned = re.sub(r"\s+", " ", raw.strip())
    out = _clamp_chinese_length(cleaned, 200)
    if is_junk_summary(out):
        return ""
    return out


async def summarize_scene(scene_text: str) -> str:
    if len(scene_text.strip()) < MIN_SCENE_TEXT_CHARS_FOR_LLM:
        return ""
    sample = scene_text[:8000]
    prompt = (
        "请用中文为下列场景写一句到两句摘要，不超过 200 个汉字。\n\n"
        f"{sample}"
    )
    raw = await deepseek_chat([{"role": "user", "content": prompt}], temperature=0.4)
    cleaned = re.sub(r"\s+", " ", raw.strip())
    out = _clamp_chinese_length(cleaned, 200)
    if is_junk_summary(out):
        return ""
    return out
