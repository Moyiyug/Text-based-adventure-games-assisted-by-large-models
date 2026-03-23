"""叙事提示词拼装单测（无 DB）。"""

from app.services.narrative.prompts import (
    build_generation_prompt,
    build_retrieval_prompt,
    build_system_prompt,
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
