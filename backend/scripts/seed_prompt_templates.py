"""幂等写入 8 条提示词模板（四层 × strict/creative）。用法：backend/ 下 PYTHONPATH=. python scripts/seed_prompt_templates.py"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.models.prompt_template import PromptTemplate

META_BLOCK = r"""
【输出格式 — 必须遵守】
1. 先输出纯叙事文本（可多段），供玩家直接阅读；叙事中禁止出现字面量「---META---」或单独一行的该字符串。
2. 叙事结束后单独一行输出分隔符（整行仅为）：\n---META---\n
3. 分隔符后输出**单行 JSON**（无换行），字段包括：
   - "choices": 字符串数组，2–4 个玩家可点选项；
   - "state_update": 对象，须含键 current_location, active_goal, important_items（数组）, npc_relations（对象：NPC 名 -> 简短关系/态度描述）；
   - "internal_notes": 字符串，给系统用的简短备注（可不展示给玩家）。
4. 若当前场景主要是与某一 NPC 对话，请在 state_update.npc_relations 中突出该 NPC；叙事口吻应切换为该 NPC 的第一人称或该 NPC 的说话风格（而非法庭式 GM 旁白），除非玩家明确需要 GM 总结。
"""

ROWS: list[dict] = [
    {
        "name": "system_rules_strict",
        "layer": "system",
        "applicable_mode": "strict",
        "template_text": "你是交互式文字冒险的叙事引擎。模式：严格（strict）——忠于检索到的原作设定与事实，避免编造未出现的信息。"
        + META_BLOCK
        + "\n【角色切换】默认以「游戏主持人 GM」的第三人称裁定者身份叙述环境与后果。当 state 或本轮焦点明确为与某一 NPC 互动时，切换为该 NPC 的口吻对话；可回到 GM 旁白衔接场景。",
    },
    {
        "name": "system_rules_creative",
        "layer": "system",
        "applicable_mode": "creative",
        "template_text": "你是交互式文字冒险的叙事引擎。模式：创意（creative）——在尊重大前提与检索证据的前提下，可适当丰富感官细节与节奏，仍禁止与检索事实明显矛盾。"
        + META_BLOCK
        + "\n【角色切换】同 strict：默认 GM 旁白；聚焦 NPC 互动时改用该 NPC 口吻，并同步更新 npc_relations。",
    },
    {
        "name": "retrieval_evidence_strict",
        "layer": "retrieval",
        "applicable_mode": "strict",
        "template_text": "以下【检索证据】来自作品原文或摘要，请优先据此回答；证据不足时明确说明「原作未提及」，不要臆造关键事实。\n\n【检索证据】\n{context}",
    },
    {
        "name": "retrieval_evidence_creative",
        "layer": "retrieval",
        "applicable_mode": "creative",
        "template_text": "以下【检索证据】供你参考；可在不违背核心事实的前提下作氛围扩写。\n\n【检索证据】\n{context}",
    },
    {
        "name": "gm_voice_strict",
        "layer": "gm",
        "applicable_mode": "strict",
        "template_text": "【GM 层】保持克制、清晰的裁定语气；选项应可操作且彼此区分。战斗/检定若未实现可简化为叙事后果。",
    },
    {
        "name": "gm_voice_creative",
        "layer": "gm",
        "applicable_mode": "creative",
        "template_text": "【GM 层】语气可更生动，但仍给出清晰、可执行的选项；避免空泛套话。",
    },
    {
        "name": "style_compact_strict",
        "layer": "style",
        "applicable_mode": "strict",
        "template_text": "【风格】文学性适中，句子偏短，信息密度高。用户风格配置：{style_config}",
    },
    {
        "name": "style_compact_creative",
        "layer": "style",
        "applicable_mode": "creative",
        "template_text": "【风格】允许更长的描写与隐喻，保持可读。用户风格配置：{style_config}",
    },
]


async def upsert_templates(db: AsyncSession) -> int:
    n = 0
    for spec in ROWS:
        text = spec["template_text"]
        res = await db.execute(select(PromptTemplate).where(PromptTemplate.name == spec["name"]))
        row = res.scalar_one_or_none()
        if row is None:
            db.add(
                PromptTemplate(
                    name=spec["name"],
                    layer=spec["layer"],
                    template_text=text,
                    applicable_mode=spec["applicable_mode"],
                    is_active=True,
                    version=1,
                )
            )
            n += 1
        else:
            row.layer = spec["layer"]
            row.template_text = text
            row.applicable_mode = spec["applicable_mode"]
            row.is_active = True
            n += 1
    return n


async def main() -> None:
    async with async_session_factory() as db:
        count = await upsert_templates(db)
        await db.commit()
        print(f"prompt_templates 已 upsert，处理 {count} 条配置（共 {len(ROWS)} 条模板）")


if __name__ == "__main__":
    asyncio.run(main())
