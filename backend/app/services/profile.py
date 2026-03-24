"""画像推断、合并与异步任务。与 profile_loader（只读）分离。参照 IMPLEMENTATION_PLAN Phase 5.1–5.2。"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Literal, Protocol, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.profile import StoryProfile, UserProfile
from app.models.session import Session as NarrativeSession
from app.models.session import SessionMessage
from app.services.llm.deepseek import deepseek_chat
from app.services.narrative.meta_parse import strip_leaking_meta_suffix
from app.services.profile_loader import load_session_profile_bundle

logger = logging.getLogger(__name__)

# BACKEND_STRUCTURE §1.4 示例键
_STORY_PREFERENCE_KEYS = frozenset({"world_identity", "npc_relations", "stage_goals"})
_GLOBAL_PREFERENCE_KEYS = frozenset({"reading_style", "difficulty_level", "moral_tendency"})


class _MessageLike(Protocol):
    role: str
    content: str


def merge_profile_json(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """顶层键合并：patch 覆盖同名键。"""
    out = dict(base)
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge_profile_json(cast(dict[str, Any], out[k]), cast(dict[str, Any], v))
        else:
            out[k] = v
    return out


def classify_update_target(update: dict[str, Any]) -> Literal["global", "story"]:
    """
    根据 LLM 返回的 update（含 target / patch）判断写入全局偏好还是作品覆写。
    """
    raw_target = update.get("target")
    patch = update.get("patch")
    if not isinstance(patch, dict):
        patch = {}

    if raw_target in ("global", "story"):
        t = cast(Literal["global", "story"], raw_target)
        keys = set(patch.keys())
        if t == "global" and keys and keys.isdisjoint(_GLOBAL_PREFERENCE_KEYS) and keys & _STORY_PREFERENCE_KEYS:
            return "story"
        if t == "story" and keys and keys.isdisjoint(_STORY_PREFERENCE_KEYS) and keys & _GLOBAL_PREFERENCE_KEYS:
            return "global"
        return t

    keys = set(patch.keys())
    if keys & _STORY_PREFERENCE_KEYS:
        return "story"
    if keys & _GLOBAL_PREFERENCE_KEYS:
        return "global"
    return "global"


def _extract_json_object(text: str) -> dict[str, Any] | None:
    t = text.strip()
    if not t:
        return None
    try:
        data = json.loads(t)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", t)
    if m:
        try:
            data = json.loads(m.group(1))
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None
    i = t.find("{")
    j = t.rfind("}")
    if i >= 0 and j > i:
        try:
            data = json.loads(t[i : j + 1])
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _format_messages_for_prompt(messages: list[_MessageLike]) -> str:
    lines: list[str] = []
    for m in messages:
        r = m.role
        if r not in ("user", "assistant"):
            continue
        body = m.content or ""
        if r == "assistant":
            body = strip_leaking_meta_suffix(body)
        label = "玩家" if r == "user" else "GM"
        lines.append(f"[{label}]\n{body.strip()}")
    return "\n\n---\n\n".join(lines)


_INFER_SYSTEM = """你是用户阅读/游玩偏好分析助手。根据对话摘录与当前画像，推断是否有稳定的偏好变化。
只输出一个 JSON 对象，不要 markdown，不要解释。格式严格为：
{"updates":[{"target":"global"|"story","patch":{...}}]}
- target=global 时 patch 键仅限：reading_style, difficulty_level, moral_tendency（字符串或简短描述）。
- target=story 时 patch 键仅限：world_identity, npc_relations, stage_goals（可为字符串或对象）。
若无明确新信息，返回 {"updates":[]}。
不要编造对话中未体现的内容。"""


async def infer_preferences(
    session_messages: list[_MessageLike],
    current_profile: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    调用 DeepSeek 得到 profile 更新列表；解析失败返回 []。
    """
    transcript = _format_messages_for_prompt(session_messages)
    if not transcript.strip():
        return []

    prefs = current_profile.get("user_preferences") or {}
    over = current_profile.get("story_overrides") or {}
    user_block = json.dumps(prefs, ensure_ascii=False)
    story_block = json.dumps(over, ensure_ascii=False)
    user_msg = (
        f"[当前全局偏好 JSON]\n{user_block}\n\n"
        f"[当前作品覆写 JSON]\n{story_block}\n\n"
        f"[近期对话]\n{transcript}"
    )

    try:
        raw = await deepseek_chat(
            [
                {"role": "system", "content": _INFER_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            temperature=settings.PROFILE_INFERENCE_TEMPERATURE,
            timeout=90.0,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("infer_preferences deepseek_chat failed: %s", exc)
        return []

    data = _extract_json_object(raw)
    if not data:
        logger.warning("infer_preferences JSON parse failed, tail=%s", raw[:400])
        return []

    updates = data.get("updates")
    if not isinstance(updates, list):
        return []

    normalized: list[dict[str, Any]] = []
    for item in updates:
        if not isinstance(item, dict):
            continue
        patch = item.get("patch")
        if not isinstance(patch, dict) or not patch:
            continue
        tgt = item.get("target")
        if tgt not in ("global", "story"):
            tgt = classify_update_target({"patch": patch})
        normalized.append({"target": tgt, "patch": patch})
    return normalized


async def apply_profile_update(
    db: AsyncSession,
    user_id: int,
    story_id: int,
    updates: list[dict[str, Any]],
) -> None:
    """将 updates 合并写入 user_profiles / story_profiles 并 commit。"""
    global_patch: dict[str, Any] = {}
    story_patch: dict[str, Any] = {}
    for u in updates:
        if not isinstance(u, dict):
            continue
        patch = u.get("patch")
        if not isinstance(patch, dict) or not patch:
            continue
        target = classify_update_target(u)
        if target == "global":
            global_patch = merge_profile_json(global_patch, patch)
        else:
            story_patch = merge_profile_json(story_patch, patch)

    try:
        if global_patch:
            row = (
                await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
            ).scalar_one_or_none()
            if row is None:
                db.add(
                    UserProfile(
                        user_id=user_id,
                        preferences=dict(global_patch),
                    )
                )
            else:
                row.preferences = merge_profile_json(dict(row.preferences or {}), global_patch)

        if story_patch:
            row = (
                await db.execute(
                    select(StoryProfile).where(
                        StoryProfile.user_id == user_id,
                        StoryProfile.story_id == story_id,
                    )
                )
            ).scalar_one_or_none()
            if row is None:
                db.add(
                    StoryProfile(
                        user_id=user_id,
                        story_id=story_id,
                        overrides=dict(story_patch),
                    )
                )
            else:
                row.overrides = merge_profile_json(dict(row.overrides or {}), story_patch)

        if global_patch or story_patch:
            await db.commit()
    except Exception:  # noqa: BLE001
        logger.exception(
            "apply_profile_update failed user_id=%s story_id=%s",
            user_id,
            story_id,
        )
        await db.rollback()


async def run_profile_inference_job(session_id: int) -> None:
    """独立 DB 会话：拉取近期消息 → 推断 → 写入画像。"""
    try:
        async with async_session_factory() as db:
            sess = await db.get(NarrativeSession, session_id)
            if sess is None:
                return
            user_id = sess.user_id
            story_id = sess.story_id
            limit = max(1, settings.PROFILE_INFERENCE_HISTORY_MESSAGES)
            result = await db.execute(
                select(SessionMessage)
                .where(SessionMessage.session_id == session_id)
                .order_by(SessionMessage.id.desc())
                .limit(limit)
            )
            rows = list(result.scalars().all())
            rows.reverse()
            bundle = await load_session_profile_bundle(db, user_id, story_id)
            updates = await infer_preferences(rows, bundle)
            if updates:
                await apply_profile_update(db, user_id, story_id, updates)
    except Exception:  # noqa: BLE001
        logger.exception("run_profile_inference_job session_id=%s", session_id)


def schedule_profile_inference_after_turn(session_id: int, turn_count: int) -> None:
    """在叙事回合成功落库后调用：按间隔异步触发，不阻塞 SSE。"""
    if not settings.PROFILE_INFERENCE_ENABLED:
        return
    n = settings.PROFILE_INFERENCE_EVERY_N_TURNS
    if n <= 0 or turn_count <= 0:
        return
    if turn_count % n != 0:
        return
    asyncio.create_task(run_profile_inference_job(session_id))
