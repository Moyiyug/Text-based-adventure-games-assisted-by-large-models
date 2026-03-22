"""敏感内容检测与文艺化改写。参照 IMPLEMENTATION_PLAN Phase 2.7。"""

from __future__ import annotations

import json
import re
from typing import Any

from app.services.llm.deepseek import deepseek_chat


def _parse_llm_json(raw: str) -> Any:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```\w*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text, flags=re.DOTALL)
    return json.loads(text)


async def detect_risk_segments(
    text: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    """
    识别高风险段落。返回 [{"original_text": str, "risk_level": "low|medium|high"}, ...]
    """
    warnings: list[str] = []
    sample = text[:14000]
    if len(text) > 14000:
        warnings.append("安全检测仅覆盖前 14000 字符")
    prompt = (
        "你是内容安全审核助手。识别下列小说文本中可能不适宜直接展示给未成年或公众的段落"
        "（暴力、色情暗示、仇恨、违法指导等）。\n"
        "严格只输出 JSON："
        '{"segments":[{"original_text":"原文片段（保持原句）","risk_level":"low|medium|high"}]}\n'
        "若无风险段落，返回 {\"segments\":[]}。\n\n"
        f"文本：\n{sample}"
    )
    try:
        raw = await deepseek_chat(
            [{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        data = _parse_llm_json(raw)
        segs = data.get("segments") if isinstance(data, dict) else None
        if not isinstance(segs, list):
            return [], warnings + ["安全检测返回格式异常"]
        out: list[dict[str, Any]] = []
        for s in segs:
            if not isinstance(s, dict):
                continue
            ot = str(s.get("original_text", "")).strip()
            if not ot:
                continue
            rl = str(s.get("risk_level", "medium")).lower()
            if rl not in ("low", "medium", "high"):
                rl = "medium"
            out.append({"original_text": ot, "risk_level": rl})
        return out, warnings
    except Exception as e:  # noqa: BLE001
        return [], warnings + [f"安全检测失败: {e}"]


async def rewrite_segment(
    original: str,
    risk_level: str = "medium",
) -> tuple[str, list[str]]:
    """对敏感片段做文艺化、弱化处理。"""
    warnings: list[str] = []
    prompt = (
        f"以下段落风险等级为 {risk_level}。请改写为仍可推进剧情、但弱化直白刺激描写的文学性中文，"
        "保持第三人称叙事风格，不要添加评论。只输出改写后的正文一段，不要 JSON。\n\n"
        f"原文：\n{original[:6000]}"
    )
    try:
        raw = await deepseek_chat(
            [{"role": "user", "content": prompt}],
            temperature=0.5,
        )
        rewritten = raw.strip()
        if not rewritten:
            warnings.append("改写结果为空，已回退为原文截断")
            return original[:2000], warnings
        return rewritten, warnings
    except Exception as e:  # noqa: BLE001
        warnings.append(f"改写失败: {e}")
        return original[:2000], warnings
