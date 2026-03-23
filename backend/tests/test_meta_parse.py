"""meta_parse 拆分与流式缓冲。"""

from app.services.narrative.meta_parse import (
    META_MARKER,
    MetaStreamSplitter,
    parse_complete_model_output,
)


def test_parse_complete_with_meta() -> None:
    raw = "你站在门口。\n\n---META---\n" + '{"choices":["进"],"state_update":{"current_location":"门厅"},"internal_notes":""}'
    out = parse_complete_model_output(raw)
    assert "门口" in out.narrative
    assert out.choices == ["进"]
    assert out.state_update.get("current_location") == "门厅"
    assert out.parse_error is None


def test_parse_complete_no_meta() -> None:
    out = parse_complete_model_output("仅叙事")
    assert out.narrative == "仅叙事"
    assert out.choices == []


def test_stream_splitter_emits_before_meta() -> None:
    sp = MetaStreamSplitter()
    parts: list[str] = []
    for d in ["你好", f"，世界\n{META_MARKER}\n", '{"choices":[]}']:
        parts.extend(sp.feed(d))
    assert "".join(parts) == "你好，世界\n"
    fin = sp.finalize()
    assert fin.choices == []
