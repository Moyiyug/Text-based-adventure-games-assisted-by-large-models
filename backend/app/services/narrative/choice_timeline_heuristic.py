"""选项文案是否可能暗示「跳过时间线 / 直达终局」的轻量启发式（观测与 grounding 重试 note，不替代 F16）。"""

from __future__ import annotations

# 保守词表：仅在与「尚未到达弧线上界」组合时触发。
_TIMELINE_JUMP_SUBSTRINGS: tuple[str, ...] = (
    "大结局",
    "全书终",
    "终局",
    "完结篇",
    "尘埃落定",
    "多年后",
    "多年以后",
    "尾声",
)


def choices_suggest_timeline_skip(
    current_timeline_order: int,
    arc_end_order: int,
    choices: list[str],
) -> bool:
    """
    当当前次序仍低于弧线上界时，若任一条选项含终局/大跨度时间跳跃类措辞则返回 True。
    已到达或越过弧线上界时不触发（终局回合合法）。
    """
    if not choices:
        return False
    if current_timeline_order >= arc_end_order:
        return False
    blob = "".join(choices)
    return any(s in blob for s in _TIMELINE_JUMP_SUBSTRINGS)
