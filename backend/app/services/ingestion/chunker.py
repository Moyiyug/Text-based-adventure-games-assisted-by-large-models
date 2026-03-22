"""章节/场景/文本切块。参照 IMPLEMENTATION_PLAN Phase 2.4。"""

from __future__ import annotations

import re
from dataclasses import dataclass

import tiktoken

# 中文章节 + 常见西文章节标题
_CHAPTER_LINE_PATTERNS = [
    re.compile(
        r"^\s*(第\s*[0-9零一二三四五六七八九十百千]+\s*[章节回卷部集])\s*[：:．.\s]?\s*(.*)$"
    ),
    re.compile(
        r"^\s*(Chapter|CHAPTER|Ch\.?)\s+(\d+|[IVXLC]+)\b[：:.\s]?\s*(.*)$",
        re.IGNORECASE,
    ),
    re.compile(r"^\s*(\d+)\s*[、.．．]\s*(.{0,80})$"),
]


@dataclass
class ChapterBlock:
    chapter_number: int
    title: str | None
    text: str


@dataclass
class SceneBlock:
    scene_number: int
    text: str


def _is_chapter_heading(line: str) -> bool:
    s = line.strip()
    if len(s) > 120:
        return False
    for pat in _CHAPTER_LINE_PATTERNS:
        if pat.match(s):
            return True
    return False


def detect_chapters(text: str) -> list[ChapterBlock]:
    """基于行首模式切分章节；若无明显标题则整篇作为第 1 章。"""
    lines = text.splitlines()
    if not lines:
        return [ChapterBlock(1, None, "")]

    chunks: list[tuple[str | None, list[str]]] = []
    current_title: str | None = None
    buf: list[str] = []

    def flush(title: str | None) -> None:
        nonlocal buf, current_title
        body = "\n".join(buf).strip()
        if body or title:
            chunks.append((title, buf.copy()))
        buf = []

    for line in lines:
        if _is_chapter_heading(line) and buf:
            flush(current_title)
            current_title = line.strip()
            buf = []
        elif _is_chapter_heading(line) and not buf:
            current_title = line.strip()
        else:
            buf.append(line)

    flush(current_title)

    if not chunks:
        return [ChapterBlock(1, None, text.strip())]

    out: list[ChapterBlock] = []
    for i, (title, blines) in enumerate(chunks, start=1):
        body = "\n".join(blines).strip()
        out.append(ChapterBlock(chapter_number=i, title=title, text=body))
    return out


_SCENE_SPLIT = re.compile(r"\n{3,}|\n\s*[-*_]{3,}\s*\n")

# 少于此长度的场景块并入相邻块（优先并入下一段），减少「前言单独成场景」
MIN_SCENE_BODY_CHARS = 120


def _merge_short_scene_parts(parts: list[str], min_chars: int = MIN_SCENE_BODY_CHARS) -> list[str]:
    """将过短片段并入后一段；最后一段仍过短则并入前一段。"""
    parts = [p.strip() for p in parts if p.strip()]
    if not parts:
        return []
    merged: list[str] = []
    pending = parts[0]
    for p in parts[1:]:
        if len(pending) < min_chars:
            pending = f"{pending}\n\n{p}"
        else:
            merged.append(pending)
            pending = p
    if pending:
        if len(pending) < min_chars and merged:
            merged[-1] = f"{merged[-1]}\n\n{pending}"
        else:
            merged.append(pending)
    return merged


def detect_scenes(chapter_text: str) -> list[SceneBlock]:
    """按空行块或分隔线切分场景；合并过短碎片。"""
    parts = _SCENE_SPLIT.split(chapter_text.strip())
    parts = [p.strip() for p in parts if p.strip()]
    if not parts:
        return [SceneBlock(1, chapter_text.strip())]
    merged = _merge_short_scene_parts(parts)
    if not merged:
        return [SceneBlock(1, chapter_text.strip())]
    return [SceneBlock(scene_number=i + 1, text=p) for i, p in enumerate(merged)]


def _encoding():
    try:
        return tiktoken.get_encoding("cl100k_base")
    except Exception:  # noqa: BLE001
        return None


def chunk_text(
    text: str,
    max_tokens: int = 512,
    overlap: int = 64,
) -> list[str]:
    """在段落边界上切块，控制近似 token 数（tiktoken cl100k_base）。"""
    text = text.strip()
    if not text:
        return []

    enc = _encoding()
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [text]

    def approx_tokens(s: str) -> int:
        if enc:
            return len(enc.encode(s))
        return max(1, len(s) // 2)

    chunks: list[str] = []
    current: list[str] = []
    cur_tokens = 0

    def flush_current() -> None:
        nonlocal current, cur_tokens
        if current:
            chunks.append("\n\n".join(current))
        current = []
        cur_tokens = 0

    for para in paragraphs:
        pt = approx_tokens(para)
        if pt > max_tokens:
            flush_current()
            if enc:
                tokens = enc.encode(para)
                start = 0
                while start < len(tokens):
                    end = min(start + max_tokens, len(tokens))
                    piece = enc.decode(tokens[start:end]).strip()
                    if piece:
                        chunks.append(piece)
                    if end >= len(tokens):
                        break
                    start = max(start + 1, end - overlap)
            else:
                step = max_tokens * 2
                start = 0
                while start < len(para):
                    end = min(start + step, len(para))
                    piece = para[start:end].strip()
                    if piece:
                        chunks.append(piece)
                    if end >= len(para):
                        break
                    start = max(start + 1, end - overlap)
            continue

        if cur_tokens + pt > max_tokens and current:
            flush_current()
        current.append(para)
        cur_tokens += pt

    flush_current()
    return chunks
