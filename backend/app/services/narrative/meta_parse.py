"""模型输出中叙事正文与 ---META--- 后 JSON 的拆分与解析。"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

META_MARKER = "---META---"
# 流式阶段保留末尾避免误切分 marker 前缀
_HOLD_BACK = max(len(META_MARKER) + 5, 24)


@dataclass
class ParsedTurnOutput:
    narrative: str
    choices: list[str]
    state_update: dict[str, Any]
    internal_notes: str
    parse_error: str | None = None


def parse_complete_model_output(full: str) -> ParsedTurnOutput:
    """
    对非流式整段输出：拆叙事与 meta JSON（取 marker 后第一行 JSON）。
    """
    if META_MARKER not in full:
        return ParsedTurnOutput(
            narrative=full.strip(),
            choices=[],
            state_update={},
            internal_notes="",
            parse_error=None,
        )
    i = full.index(META_MARKER)
    narrative = full[:i].strip()
    rest = full[i + len(META_MARKER) :].strip()
    return _parse_meta_after_marker(narrative, rest)


def _parse_meta_after_marker(narrative: str, meta_block: str) -> ParsedTurnOutput:
    if not meta_block:
        return ParsedTurnOutput(
            narrative=narrative,
            choices=[],
            state_update={},
            internal_notes="",
            parse_error="META 后为空",
        )
    line = meta_block.splitlines()[0].strip()
    try:
        data = json.loads(line)
        if not isinstance(data, dict):
            raise ValueError("meta 须为 JSON 对象")
        choices = data.get("choices") or []
        if not isinstance(choices, list):
            choices = []
        choices = [str(x) for x in choices]
        su = data.get("state_update") or {}
        if not isinstance(su, dict):
            su = {}
        notes = data.get("internal_notes", "")
        if notes is not None and not isinstance(notes, str):
            notes = str(notes)
        return ParsedTurnOutput(
            narrative=narrative,
            choices=choices,
            state_update=su,
            internal_notes=notes or "",
            parse_error=None,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("META JSON 解析失败: %s", e)
        return ParsedTurnOutput(
            narrative=narrative,
            choices=[],
            state_update={},
            internal_notes="",
            parse_error=str(e)[:500],
        )


@dataclass
class MetaStreamSplitter:
    """边收流边输出叙事片段；流结束后解析 JSON。"""

    _buffer: str = ""
    _emitted_narrative_len: int = 0
    _meta_found: bool = False
    _meta_index: int = -1

    def feed(self, delta: str) -> list[str]:
        """返回本轮可立刻转发给前端的叙事文本片段（可能为空列表）。"""
        if not delta:
            return []
        self._buffer += delta
        if self._meta_found:
            return []

        idx = self._buffer.find(META_MARKER)
        if idx >= 0:
            self._meta_found = True
            self._meta_index = idx
            narrative_all = self._buffer[:idx]
            chunk = narrative_all[self._emitted_narrative_len :]
            self._emitted_narrative_len = len(narrative_all)
            return [chunk] if chunk else []

        safe_end = len(self._buffer) - _HOLD_BACK
        if safe_end <= self._emitted_narrative_len:
            return []
        chunk = self._buffer[self._emitted_narrative_len : safe_end]
        self._emitted_narrative_len = safe_end
        return [chunk] if chunk else []

    def finalize(self) -> ParsedTurnOutput:
        """流结束后调用，解析 meta（若曾出现 marker）。"""
        if not self._meta_found:
            return ParsedTurnOutput(
                narrative=self._buffer.strip(),
                choices=[],
                state_update={},
                internal_notes="",
                parse_error=None,
            )

        narrative_all = self._buffer[: self._meta_index]
        rest = self._buffer[self._meta_index + len(META_MARKER) :].strip()
        return _parse_meta_after_marker(narrative_all.strip(), rest)
