"""narrative.state 软合并单测。"""

from types import SimpleNamespace

from app.services.narrative.state import initialize_state, validate_state_update


def test_initialize_state_uses_opening_goal() -> None:
    s = SimpleNamespace(opening_goal="  找公主  ")
    st = initialize_state(s)
    assert st["active_goal"] == "找公主"
    assert st["npc_relations"] == {}
    assert st["important_items"] == []


def test_validate_state_update_merge() -> None:
    cur = {
        "current_location": "A",
        "active_goal": "g",
        "important_items": ["x"],
        "npc_relations": {"b": "1"},
    }
    prop = {
        "current_location": "B",
        "unknown": "skip",
        "important_items": [1, 2],
        "npc_relations": {"c": "d"},
    }
    out = validate_state_update(cur, prop)
    assert out["current_location"] == "B"
    assert out["active_goal"] == "g"
    assert out["important_items"] == ["1", "2"]
    assert out["npc_relations"] == {"b": "1", "c": "d"}
