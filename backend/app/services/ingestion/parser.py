"""文档解析（best-effort，附带 warnings）。参照 IMPLEMENTATION_PLAN Phase 2.3。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import chardet
from docx import Document
from pypdf import PdfReader


def parse_txt(filepath: str | Path) -> tuple[str, list[str]]:
    """读取 .txt / .md 纯文本，返回 (text, warnings)。"""
    path = Path(filepath)
    raw = path.read_bytes()
    warnings: list[str] = []
    try:
        return raw.decode("utf-8"), warnings
    except UnicodeDecodeError:
        det = chardet.detect(raw)
        enc = det.get("encoding") or "utf-8"
        try:
            text = raw.decode(enc, errors="replace")
            warnings.append(f"非 UTF-8 文件，已用 {enc} 解码（可能含替换字符）")
            return text, warnings
        except LookupError:
            warnings.append("编码未知，已用 UTF-8 replace 解码")
            return raw.decode("utf-8", errors="replace"), warnings


def parse_pdf(filepath: str | Path) -> tuple[str, list[str]]:
    warnings: list[str] = []
    try:
        reader = PdfReader(str(filepath))
        parts: list[str] = []
        for i, page in enumerate(reader.pages):
            try:
                t = page.extract_text() or ""
                parts.append(t)
            except Exception as e:  # noqa: BLE001
                warnings.append(f"PDF 第 {i + 1} 页提取失败: {e}")
        text = "\n".join(parts)
        if not text.strip():
            warnings.append("PDF 未提取到可见文本（可能是扫描件）")
        return text, warnings
    except Exception as e:  # noqa: BLE001
        return "", [f"PDF 解析失败: {e}"]


def parse_docx(filepath: str | Path) -> tuple[str, list[str]]:
    warnings: list[str] = []
    try:
        doc = Document(str(filepath))
        paras = [p.text for p in doc.paragraphs if p.text.strip()]
        text = "\n".join(paras)
        if not text.strip():
            warnings.append("DOCX 正文为空")
        return text, warnings
    except Exception as e:  # noqa: BLE001
        return "", [f"DOCX 解析失败: {e}"]


def parse_json(filepath: str | Path) -> tuple[Any, list[str]]:
    """解析 JSON 文件为 Python 对象。"""
    warnings: list[str] = []
    raw = Path(filepath).read_bytes()
    try:
        return json.loads(raw.decode("utf-8")), warnings
    except UnicodeDecodeError:
        data = json.loads(raw.decode("utf-8", errors="replace"))
        warnings.append("JSON 文件按 UTF-8 replace 解码")
        return data, warnings
    except json.JSONDecodeError as e:
        warnings.append(f"JSON 解析失败: {e}")
        return {}, warnings
