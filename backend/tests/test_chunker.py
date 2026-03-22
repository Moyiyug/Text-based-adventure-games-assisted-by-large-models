"""场景切分合并过短片段等单元测试。"""

from app.services.ingestion.chunker import MIN_SCENE_BODY_CHARS, _merge_short_scene_parts, detect_scenes


def test_merge_short_preface_into_body() -> None:
    preface = "很短的前言"
    body = "x" * (MIN_SCENE_BODY_CHARS + 10)
    merged = _merge_short_scene_parts([preface, body])
    assert len(merged) == 1
    assert preface in merged[0]
    assert body in merged[0]


def test_merge_keeps_two_long_parts() -> None:
    a = "a" * (MIN_SCENE_BODY_CHARS + 5)
    b = "b" * (MIN_SCENE_BODY_CHARS + 5)
    merged = _merge_short_scene_parts([a, b])
    assert len(merged) == 2


def test_detect_scenes_merges_short_leading_block() -> None:
    short = "作者的话"
    long_block = "正文段落一。" * 50
    text = f"{short}\n\n\n\n{long_block}"
    scenes = detect_scenes(text)
    assert len(scenes) == 1
    assert short in scenes[0].text
    assert "正文" in scenes[0].text
