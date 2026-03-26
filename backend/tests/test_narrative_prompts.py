"""叙事提示词拼装单测（无 DB）。"""

from app.schemas.narrative_plan import NarrativePlan
from app.services.narrative.prompts import (
    NARRATIVE_CONCISE_SYSTEM_SUFFIX,
    build_generation_prompt,
    build_retrieval_prompt,
    build_system_prompt,
    format_opening_arc_constraints_for_turn_hints,
    format_opening_two_phase_user_block,
    roleplay_pov_hint_for_opening,
)


def _templates() -> dict[str, str]:
    return {
        "system": "SYS。含 ---META--- 与 npc_relations 约定。",
        "gm": "GM 层。",
        "style": "风格：{style_config}",
        "retrieval": "证据：\n{context}",
    }


def test_build_system_prompt_injects_style_json() -> None:
    out = build_system_prompt("strict", {"pacing": "slow"}, _templates())
    assert "SYS" in out
    assert "slow" in out
    assert "pacing" in out


def test_build_retrieval_prompt_replaces_context() -> None:
    out = build_retrieval_prompt("  片段A  ", _templates())
    assert "片段A" in out


def test_build_generation_prompt_meta_and_npc_in_system() -> None:
    msgs = build_generation_prompt(
        "我向左走",
        "证据文本",
        {"npc_relations": {"老者": "初遇"}},
        {"prefs": {}},
        mode="strict",
        style_config={},
        templates=_templates(),
        history=[{"role": "assistant", "content": "此前叙事"}],
    )
    assert msgs[0]["role"] == "system"
    assert "---META---" in msgs[0]["content"]
    assert "npc_relations" in msgs[0]["content"]
    assert any(m["role"] == "user" and "证据" in m["content"] for m in msgs)
    assert msgs[-1]["role"] == "user"
    assert "我向左走" in msgs[-1]["content"]
    assert "老者" in msgs[-1]["content"]


def test_build_generation_prompt_accepts_empty_history() -> None:
    msgs = build_generation_prompt(
        "hi",
        "",
        {},
        None,
        mode="creative",
        style_config=None,
        templates=_templates(),
    )
    assert len(msgs) >= 2


def test_build_generation_prompt_injects_turn_hints_before_user_input() -> None:
    msgs = build_generation_prompt(
        "走",
        "ctx",
        {},
        None,
        mode="strict",
        style_config=None,
        templates=_templates(),
        turn_hints="[回合推进提示]\n须回应输入。",
    )
    tail = msgs[-1]["content"]
    assert "须回应输入" in tail
    assert tail.index("须回应输入") < tail.index("走")


def test_format_opening_arc_and_two_phase_blocks() -> None:
    plan = NarrativePlan(
        opening_anchor_summary="序章港口",
        arc_goal="抵达王都",
        current_timeline_order=1,
        arc_end_order=10,
        fallback_reason="unit_test_fb",
    )
    hints = format_opening_arc_constraints_for_turn_hints(plan)
    assert "序章港口" in hints
    assert "时间线" in hints
    assert "unit_test_fb" in hints
    assert "玩家介入意图" in hints

    block = format_opening_two_phase_user_block(plan=plan, player_intent="我想钓鱼")
    assert "序章港口" in block
    assert "我想钓鱼" in block
    assert "次要" in block


def test_roleplay_pov_hint_for_opening_hit_and_miss() -> None:
    hit = roleplay_pov_hint_for_opening("想代入主角第一人称体验故事")
    assert hit is not None
    assert "第一人称" in hit
    assert "时间线锚点" in hit

    assert roleplay_pov_hint_for_opening("想调查失踪案") is None
    assert roleplay_pov_hint_for_opening("") is None
    assert roleplay_pov_hint_for_opening("   ") is None

    assert roleplay_pov_hint_for_opening("以路人甲身份经历开场") is not None
    assert roleplay_pov_hint_for_opening("用主角视角代入剧情") is not None


def test_build_generation_prompt_narrative_concise_suffix() -> None:
    msgs = build_generation_prompt(
        "hi",
        "",
        {},
        None,
        mode="creative",
        style_config=None,
        templates=_templates(),
        narrative_concise_mode=True,
    )
    sys0 = msgs[0]["content"]
    assert NARRATIVE_CONCISE_SYSTEM_SUFFIX in sys0
    assert "篇幅软约束" in sys0
