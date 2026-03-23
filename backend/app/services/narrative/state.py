"""会话状态初始化、软校验与落库。参照 IMPLEMENTATION_PLAN 4.4。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import SessionState

if TYPE_CHECKING:
    from app.models.session import Session as NarrativeSession

_STATE_KEYS = frozenset(
    {"current_location", "active_goal", "important_items", "npc_relations"}
)


def initialize_state(session: NarrativeSession) -> dict[str, Any]:
    """创建 turn 0 状态骨架；active_goal 来自会话的 opening_goal。"""
    goal = (session.opening_goal or "").strip()
    return {
        "current_location": "",
        "active_goal": goal,
        "important_items": [],
        "npc_relations": {},
    }


def validate_state_update(current: dict[str, Any], proposed: dict[str, Any]) -> dict[str, Any]:
    """
    将 proposed 软合并进 current：仅接受已知键；类型不对则跳过该键。
    important_items 尽量收敛为字符串列表；npc_relations 必须为 dict。
    """
    base = {k: current.get(k) for k in _STATE_KEYS}
    # 默认值
    if not isinstance(base.get("important_items"), list):
        base["important_items"] = []
    if not isinstance(base.get("npc_relations"), dict):
        base["npc_relations"] = {}
    for k, v in proposed.items():
        if k not in _STATE_KEYS:
            continue
        if k == "important_items":
            if isinstance(v, list):
                base[k] = [str(x) for x in v]
            continue
        if k == "npc_relations":
            if isinstance(v, dict):
                merged = dict(base[k])
                merged.update({str(a): str(b) for a, b in v.items()})
                base[k] = merged
            continue
        if k in ("current_location", "active_goal"):
            base[k] = str(v) if v is not None else ""
    return base


async def apply_state_update(
    db: AsyncSession,
    session_id: int,
    turn_number: int,
    validated: dict[str, Any],
) -> SessionState:
    """插入一条新的 session_states 记录。"""
    row = SessionState(
        session_id=session_id,
        turn_number=turn_number,
        state=dict(validated),
    )
    db.add(row)
    await db.flush()
    return row
