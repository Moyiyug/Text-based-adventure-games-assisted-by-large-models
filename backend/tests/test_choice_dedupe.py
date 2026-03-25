"""choice_dedupe：规范化去重与 beats 对齐。"""

from app.services.narrative.choice_dedupe import dedupe_choices_with_beats, normalize_choice_dedupe_key


def test_normalize_choice_dedupe_key_collapses_whitespace() -> None:
    assert normalize_choice_dedupe_key("同步  率") == normalize_choice_dedupe_key("同步 率")


def test_dedupe_choices_preserves_order_first_occurrence() -> None:
    ch, be = dedupe_choices_with_beats(
        ["靠近", "靠近", "离开"],
        ["b1", "b2", "b3"],
    )
    assert ch == ["靠近", "离开"]
    assert be == ["b1", "b3"]


def test_dedupe_choices_nfkc_duplicate() -> None:
    ch, _be = dedupe_choices_with_beats(["选项Ａ", "选项A"], None)
    assert len(ch) == 1


def test_dedupe_beats_dropped_when_length_mismatch() -> None:
    ch, be = dedupe_choices_with_beats(["a", "b"], ["only_one"])
    assert ch == ["a", "b"]
    assert be is None
