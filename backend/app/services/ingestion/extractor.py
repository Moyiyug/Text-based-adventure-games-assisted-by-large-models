"""实体/关系/时间线抽取（DeepSeek JSON）。参照 IMPLEMENTATION_PLAN Phase 2.5。"""

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


async def extract_entities(chapter_text: str) -> tuple[list[dict[str, Any]], list[str]]:
    """从章节文本抽取实体列表。每项含 name, canonical_name, entity_type, description, aliases。"""
    warnings: list[str] = []
    sample = chapter_text[:12000]
    if len(chapter_text) > 12000:
        warnings.append("章节过长，仅将前 12000 字符送入模型抽取实体")
    prompt = (
        "你是文本分析助手。从下列小说章节中提取主要实体（人物、地点、组织、物品）。\n"
        "严格只输出一个 JSON 对象，不要 Markdown，格式如下：\n"
        '{"entities":[{"name":"原文名","canonical_name":"标准名","entity_type":"character|location|organization|item","description":"简短描述或null","aliases":[]}]}\n\n'
        f"章节文本：\n{sample}"
    )
    raw = await deepseek_chat(
        [{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    try:
        data = _parse_llm_json(raw)
        entities = data.get("entities") if isinstance(data, dict) else None
        if not isinstance(entities, list):
            warnings.append("模型返回的 entities 非列表，已置空")
            return [], warnings
        out: list[dict[str, Any]] = []
        for e in entities:
            if not isinstance(e, dict):
                continue
            out.append(
                {
                    "name": str(e.get("name", "")).strip() or "未命名",
                    "canonical_name": str(
                        e.get("canonical_name") or e.get("name", "")
                    ).strip()
                    or str(e.get("name", "")).strip(),
                    "entity_type": str(e.get("entity_type", "character")).strip()
                    or "character",
                    "description": e.get("description"),
                    "aliases": e.get("aliases") if isinstance(e.get("aliases"), list) else [],
                }
            )
        return out, warnings
    except (json.JSONDecodeError, TypeError, KeyError) as e:
        warnings.append(f"实体 JSON 解析失败: {e}")
        return [], warnings


async def extract_relationships(
    entities: list[dict[str, Any]],
    chapter_text: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    sample = chapter_text[:10000]
    ent_lines = [
        f"- {e.get('canonical_name', e.get('name'))} ({e.get('entity_type')})"
        for e in entities[:80]
    ]
    prompt = (
        "已知实体列表：\n"
        + "\n".join(ent_lines)
        + "\n\n请根据章节内容，抽取实体之间的关系。输出严格 JSON：\n"
        '{"relationships":[{"entity_a_name":"标准名A","entity_b_name":"标准名B",'
        '"relationship_type":"如 friend_of","description":"可选","confidence":0.0-1.0}]}\n\n'
        f"章节：\n{sample}"
    )
    raw = await deepseek_chat([{"role": "user", "content": prompt}], temperature=0.2)
    try:
        data = _parse_llm_json(raw)
        rels = data.get("relationships") if isinstance(data, dict) else None
        if not isinstance(rels, list):
            warnings.append("模型返回的 relationships 非列表")
            return [], warnings
        known: set[str] = set()
        for e in entities:
            for k in (e.get("canonical_name"), e.get("name")):
                if k:
                    known.add(str(k).strip().lower())
        out: list[dict[str, Any]] = []
        for r in rels:
            if not isinstance(r, dict):
                continue
            na = str(r.get("entity_a_name", "")).strip()
            nb = str(r.get("entity_b_name", "")).strip()
            if na.lower() not in known or nb.lower() not in known:
                warnings.append(f"关系跳过（名称不在实体列表）: {na} -> {nb}")
                continue
            out.append(
                {
                    "entity_a_name": na,
                    "entity_b_name": nb,
                    "relationship_type": str(r.get("relationship_type", "related")).strip(),
                    "description": r.get("description"),
                    "confidence": float(r.get("confidence", 1.0)),
                }
            )
        return out, warnings
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        warnings.append(f"关系 JSON 解析失败: {e}")
        return [], warnings


async def extract_timeline(chapter_text: str) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    sample = chapter_text[:12000]
    prompt = (
        "从下列章节中按叙事顺序提取关键事件。严格输出 JSON：\n"
        '{"events":[{"order_index":1,"event_description":"事件描述","participant_names":["可选人物名"]}]}\n\n'
        f"章节：\n{sample}"
    )
    raw = await deepseek_chat([{"role": "user", "content": prompt}], temperature=0.2)
    try:
        data = _parse_llm_json(raw)
        events = data.get("events") if isinstance(data, dict) else None
        if not isinstance(events, list):
            return [], warnings + ["timeline events 非列表"]
        out: list[dict[str, Any]] = []
        for i, ev in enumerate(events):
            if not isinstance(ev, dict):
                continue
            desc = str(ev.get("event_description", "")).strip()
            if not desc:
                continue
            participants = ev.get("participant_names")
            if not isinstance(participants, list):
                participants = []
            out.append(
                {
                    "order_index": int(ev.get("order_index", i + 1)),
                    "event_description": desc,
                    "participants": [str(x) for x in participants],
                }
            )
        out.sort(key=lambda x: x["order_index"])
        return out, warnings
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        warnings.append(f"时间线 JSON 解析失败: {e}")
        return [], warnings


def merge_entities(all_entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按 canonical_name（小写）归并别名。"""
    buckets: dict[str, dict[str, Any]] = {}
    for e in all_entities:
        key = str(e.get("canonical_name", e.get("name", ""))).strip().lower()
        if not key:
            continue
        if key not in buckets:
            buckets[key] = {
                "name": e.get("name"),
                "canonical_name": e.get("canonical_name") or e.get("name"),
                "entity_type": e.get("entity_type", "character"),
                "description": e.get("description"),
                "aliases": list(e.get("aliases") or []),
            }
        else:
            b = buckets[key]
            aliases = set(b.get("aliases") or [])
            aliases.update(e.get("aliases") or [])
            aliases.add(str(e.get("name", "")))
            aliases.discard(b.get("canonical_name"))
            b["aliases"] = sorted(a for a in aliases if a)
    return list(buckets.values())
