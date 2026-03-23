"""turn_context：匹配与相似度。"""

from app.services.narrative.turn_context import (
    build_turn_hints_text,
    match_choice_beat_index,
    word_jaccard_similarity,
)


def test_match_choice_beat_index_exact() -> None:
    assert match_choice_beat_index("离开", ["离开", "留下"]) == 0


def test_match_choice_beat_index_substring() -> None:
    assert match_choice_beat_index("离开教室", ["离开教室，前往音乐室", "留下"]) == 0


def test_word_jaccard_identical() -> None:
    s = "春希坐在座位上翻开英语书"
    assert word_jaccard_similarity(s, s) == 1.0


def test_word_jaccard_different() -> None:
    a = "猫在屋檐上睡觉"
    b = "飞船跃迁到第二象限"
    assert word_jaccard_similarity(a, b) < 0.3


def test_build_turn_hints_contains_stall_when_similar() -> None:
    from app.core.config import settings

    prev = "教室里很安静。春希看着窗外。雪音在远处弹琴。"
    hints = build_turn_hints_text(
        mode="creative",
        state={"active_goal": "观察", "current_location": "教室"},
        prev_gm_content=prev,
        prev_meta=None,
        user_text="我走近钢琴",
        prev_prev_gm_content=prev,
    )
    assert hints is not None
    assert settings.NARRATIVE_STALL_SIMILARITY_THRESHOLD <= 1.0
    if word_jaccard_similarity(prev, prev) >= settings.NARRATIVE_STALL_SIMILARITY_THRESHOLD:
        assert "僵局打破" in hints
