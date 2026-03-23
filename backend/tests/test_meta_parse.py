"""meta_parse 拆分与流式缓冲。"""

from app.services.narrative.meta_parse import (
    META_MARKER,
    MetaStreamSplitter,
    extract_choice_lines_from_narrative,
    parse_complete_model_output,
    strip_incomplete_separator_tail,
    strip_leaking_meta_suffix,
    strip_pre_marker_meta_leak,
    strip_pseudo_markdown_meta_tail,
)


def test_parse_complete_with_meta() -> None:
    raw = "你站在门口。\n\n---META---\n" + '{"choices":["进"],"state_update":{"current_location":"门厅"},"internal_notes":""}'
    out = parse_complete_model_output(raw)
    assert "门口" in out.narrative
    assert out.choices == ["进"]
    assert out.state_update.get("current_location") == "门厅"
    assert out.parse_error is None
    assert out.choices_source == "model_json"


def test_parse_complete_no_meta() -> None:
    out = parse_complete_model_output("仅叙事")
    assert out.narrative == "仅叙事"
    assert out.choices == []


def test_parse_complete_options_alias_no_choices() -> None:
    """模型误用 options 时仍应解析出选项。"""
    meta = (
        '{"options":["A","B"],"state_update":{"current_location":"教室"},'
        '"internal_notes":""}'
    )
    raw = f"叙事。\n\n---META---\n{meta}"
    out = parse_complete_model_output(raw)
    assert out.choices == ["A", "B"]
    assert out.state_update.get("current_location") == "教室"


def test_parse_complete_multiline_meta_json() -> None:
    """META 后为多行 pretty JSON 时仍能解析 choices。"""
    meta = """{
  "choices": ["甲", "乙"],
  "state_update": {"current_location": "此处"},
  "internal_notes": ""
}"""
    raw = f"起\n---META---\n{meta}"
    out = parse_complete_model_output(raw)
    assert out.choices == ["甲", "乙"]
    assert out.state_update.get("current_location") == "此处"
    assert out.parse_error is None


def test_strip_incomplete_separator_tail() -> None:
    assert strip_incomplete_separator_tail("正文\n---\n**") == "正文"
    assert strip_incomplete_separator_tail("正文") == "正文"


def test_parse_complete_flat_state_with_options() -> None:
    """顶层摊平 state + options，无 state_update 包裹。"""
    meta = (
        '{"current_location":"音乐教室","active_goal":"体验",'
        '"important_items":["钢琴"],"npc_relations":{},"options":["一","二"]}'
    )
    raw = f"正文\n---META---\n{meta}"
    out = parse_complete_model_output(raw)
    assert out.choices == ["一", "二"]
    assert out.state_update.get("current_location") == "音乐教室"
    assert out.state_update.get("active_goal") == "体验"


def test_strip_leaking_meta_suffix() -> None:
    raw = '故事一段\n---META---\n{"choices":["a"]}'
    assert strip_leaking_meta_suffix(raw) == "故事一段"
    assert strip_leaking_meta_suffix("无分隔符正文") == "无分隔符正文"


def test_strip_pre_marker_meta_leak_chinese_heading_and_fence() -> None:
    """规范 ---META--- 之前的假 META（截图形态）：须在 narrative 卫生阶段剥掉。"""
    nar = (
        "春希坐下。\n\n接下来，你会怎么做？\n\n"
        "1. 选项甲\n2. 选项乙\n\n"
        "---\n\n"
        "【META JSON】\n"
        "```json\n"
        "{∫"
    )
    assert strip_pre_marker_meta_leak(nar) == (
        "春希坐下。\n\n接下来，你会怎么做？\n\n1. 选项甲\n2. 选项乙"
    )
    assert strip_leaking_meta_suffix(nar) == (
        "春希坐下。\n\n接下来，你会怎么做？\n\n1. 选项甲\n2. 选项乙"
    )


def test_strip_pre_marker_meta_leak_plain_meta_json_line() -> None:
    nar = "叙事尾\n\nMETA JSON\n\n```json\n{\"a\":1}"
    assert strip_pre_marker_meta_leak(nar) == "叙事尾"


def test_strip_pre_marker_meta_leak_negative_inline_meta_words() -> None:
    """正文行内出现 META JSON 字样但非整行标题：不误截断。"""
    nar = "角色解释道：这是 META JSON 字段的含义。\n\n再见。"
    assert strip_pre_marker_meta_leak(nar) == nar


def test_strip_pre_marker_meta_leak_negative_code_fence_without_json_lang() -> None:
    """非 ```json 围栏：不当作泄漏（避免误伤正文代码块）。"""
    nar = "示例：\n```\n{ not json }\n```\n\n结束。"
    assert strip_pre_marker_meta_leak(nar) == nar


def test_strip_pseudo_markdown_meta_tail_hr_then_choices_and_beats() -> None:
    """--- 后 **choices:** / **choice_beats:** 泄漏（用户截图形态）。"""
    nar = (
        "“这首曲子……”春希喃喃道。\n\n"
        "---\n\n"
        "**choices:**\n"
        "- 选项一\n"
        "- 选项二\n\n"
        "**choice_beats:**\n"
        "['大纲一', '大纲二']\n"
    )
    assert strip_pseudo_markdown_meta_tail(nar) == "“这首曲子……”春希喃喃道。"
    assert strip_leaking_meta_suffix(nar) == "“这首曲子……”春希喃喃道。"


def test_strip_pseudo_markdown_meta_tail_no_hr_cut_at_field() -> None:
    """无近距 --- 时从伪字段标题行截断。"""
    nar = "叙事一段。\n\n**choices:**\n- A\n- B"
    assert strip_pseudo_markdown_meta_tail(nar) == "叙事一段。"


def test_strip_pseudo_markdown_meta_tail_hr_then_choices_bold_no_colon() -> None:
    """--- 后 **choices**（无冒号）+ 列表泄漏：与 **choices:** 同等截断。"""
    nar = (
        "“这首曲子……”春希喃喃道。\n\n"
        "---\n"
        "**choices**\n"
        "- 笑着承认\n"
        "- 转移话题\n"
    )
    assert strip_pseudo_markdown_meta_tail(nar) == "“这首曲子……”春希喃喃道。"
    assert strip_leaking_meta_suffix(nar) == "“这首曲子……”春希喃喃道。"


def test_strip_pseudo_markdown_meta_tail_no_hr_choices_bold_no_colon() -> None:
    """无 --- 时 **choices**（无冒号）仍从标题行截断。"""
    nar = "叙事一段。\n\n**choices**\n- A\n- B"
    assert strip_pseudo_markdown_meta_tail(nar) == "叙事一段。"


def test_strip_pseudo_markdown_meta_tail_negative_inline_choices_word() -> None:
    """行内 “choices” 非 Markdown 标题行：不截断。"""
    nar = "他说：请从 choices: 里选一项。\n\n再见。"
    assert strip_pseudo_markdown_meta_tail(nar) == nar


def test_strip_pseudo_markdown_meta_tail_hr_then_meta_bold() -> None:
    """--- 后 **META** 仿协议标题泄漏（管理员截图形态）。"""
    nar = (
        "班长递来课本。\n\n"
        "---\n"
        "**META**\n"
        "下面是一段 JSON 预览……\n"
    )
    assert strip_pseudo_markdown_meta_tail(nar) == "班长递来课本。"
    assert strip_leaking_meta_suffix(nar) == "班长递来课本。"


def test_strip_pseudo_markdown_meta_tail_hr_then_meta_json_bold() -> None:
    """--- 后 **META JSON** 泄漏。"""
    nar = "叙事结束。\n\n---\n**META JSON**\n{\"choices\":[]}\n"
    assert strip_pseudo_markdown_meta_tail(nar) == "叙事结束。"
    assert strip_leaking_meta_suffix(nar) == "叙事结束。"


def test_strip_pseudo_markdown_meta_tail_negative_line_with_meta_word() -> None:
    """整行仅普通叙述含单词 meta，无加粗伪标题：不截断。"""
    nar = "我们在讨论 meta 学习率的问题。\n\n下一段继续。"
    assert strip_pseudo_markdown_meta_tail(nar) == nar


def test_strip_pseudo_markdown_meta_tail_negative_scene_hr_only() -> None:
    """仅有分幕 ---，其后 12 行内无伪字段：不截断。"""
    nar = "上幕结束。\n\n---\n\n下幕开始，很长\n" + "x\n" * 15
    assert strip_pseudo_markdown_meta_tail(nar) == nar


def test_stream_splitter_emits_before_meta() -> None:
    sp = MetaStreamSplitter()
    parts: list[str] = []
    for d in ["你好", f"，世界\n{META_MARKER}\n", '{"choices":[]}']:
        parts.extend(sp.feed(d))
    assert "".join(parts) == "你好，世界\n"
    fin = sp.finalize()
    assert fin.choices == []


def test_parse_meta_leak_META_dash_only() -> None:
    """无标准 ---META---，仅有 META--- 泄漏且后跟 JSON。"""
    meta = '{"choices":["东","西"],"state_update":{"current_location":"此处"},"internal_notes":""}'
    raw = f"叙事一段。\n**META---\n{meta}"
    out = parse_complete_model_output(raw)
    assert "叙事一段" in out.narrative
    assert out.choices == ["东", "西"]
    assert out.parse_error is None


def test_parse_meta_with_markdown_fence() -> None:
    meta = '```json\n{"choices":["甲","乙"],"state_update":{},"internal_notes":""}\n```'
    raw = f"正文\n{META_MARKER}\n{meta}"
    out = parse_complete_model_output(raw)
    assert out.choices == ["甲", "乙"]


def test_parse_meta_brace_scan_with_noise() -> None:
    """META 前有说明、JSON 前有噪声时仍抽出对象。"""
    meta = '请解析：{"choices":["一"],"state_update":{"current_location":"X"},"internal_notes":""} 完毕'
    raw = f"起\n{META_MARKER}\n{meta}"
    out = parse_complete_model_output(raw)
    assert out.choices == ["一"]


def test_extract_choice_lines_from_narrative_tail() -> None:
    nar = (
        "场景描写。\n\n"
        "1. 第一个可执行行动较长一些文字\n"
        "2. 第二个行动也足够长度\n"
        "3. 第三个选项同样满足六字以上\n"
    )
    assert extract_choice_lines_from_narrative(nar) == [
        "第一个可执行行动较长一些文字",
        "第二个行动也足够长度",
        "第三个选项同样满足六字以上",
    ]


def test_extract_choice_lines_short_labels() -> None:
    """选项正文 ≥2 字即可命中兜底（与前端编号行规则对齐）。"""
    nar = "你站在路口。\n\n1. 逃跑\n2. 迎战\n"
    assert extract_choice_lines_from_narrative(nar) == ["逃跑", "迎战"]


def test_extract_choice_lines_paren_suffix() -> None:
    """半角/全角括号编号 1) / 1）。"""
    nar = "场景。\n\n1）离开教室\n2）留下\n"
    assert extract_choice_lines_from_narrative(nar) == ["离开教室", "留下"]


def test_extract_choice_lines_wrapped_number() -> None:
    nar = "结尾\n\n（1）选择甲\n（2）选择乙\n"
    assert extract_choice_lines_from_narrative(nar) == ["选择甲", "选择乙"]


def test_parse_meta_choice_beats_passthrough() -> None:
    meta = (
        '{"choices":["甲","乙"],"choice_beats":["若选甲则冲突升级","若选乙则暂时撤退"],'
        '"state_update":{"current_location":"此处"},"internal_notes":""}'
    )
    raw = f"正文\n{META_MARKER}\n{meta}"
    out = parse_complete_model_output(raw)
    assert out.choices == ["甲", "乙"]
    assert out.choice_beats == ["若选甲则冲突升级", "若选乙则暂时撤退"]


def test_parse_meta_choice_beats_wrong_length_ignored() -> None:
    meta = (
        '{"choices":["甲","乙"],"choice_beats":["仅一条"],'
        '"state_update":{},"internal_notes":""}'
    )
    raw = f"正文\n{META_MARKER}\n{meta}"
    out = parse_complete_model_output(raw)
    assert out.choices == ["甲", "乙"]
    assert out.choice_beats is None


def test_parse_empty_json_choices_paren_narrative() -> None:
    """JSON choices 为空时从正文 1）列表兜底。"""
    meta = '{"choices":[],"state_update":{}}'
    raw = (
        "旁白。\n\n"
        "1）离开教室\n"
        "2）继续观察\n"
        f"{META_MARKER}\n{meta}"
    )
    out = parse_complete_model_output(raw)
    assert out.choices == ["离开教室", "继续观察"]
    assert out.choices_source == "narrative_regex"


def test_parse_complete_json_choices_not_overridden_by_narrative_numbers() -> None:
    """JSON 已有 choices 时不得用正文末尾编号覆盖。"""
    meta = '{"choices":["仅JSON"],"state_update":{}}'
    raw = (
        "末段有干扰\n1. 假选项甲很长文字\n2. 假选项乙也很长\n"
        f"{META_MARKER}\n{meta}"
    )
    out = parse_complete_model_output(raw)
    assert out.choices == ["仅JSON"]


def test_stream_alt_meta_marker() -> None:
    sp = MetaStreamSplitter()
    parts: list[str] = []
    blob = '{"choices":["流"],"state_update":{}}'
    for d in ["旁白", "\n**META---\n", blob]:
        parts.extend(sp.feed(d))
    assert "".join(parts) == "旁白\n"
    fin = sp.finalize()
    assert fin.choices == ["流"]


def test_parse_hr_three_then_multiline_json() -> None:
    """非规范：单独 --- 后多行 JSON（截图形态）。"""
    raw = (
        "河风微凉。\n\n"
        "---\n"
        "{\n"
        '  "current_location": "河堤",\n'
        '  "active_goal": "体验故事",\n'
        '  "important_items": [],\n'
        '  "npc_relations": {},\n'
        '  "choices": ["留下", "离开"]\n'
        "}\n"
    )
    out = parse_complete_model_output(raw)
    assert out.narrative.strip() == "河风微凉。"
    assert out.choices == ["留下", "离开"]
    assert out.parse_error is None


def test_parse_hr_five_then_json() -> None:
    raw = (
        "正文一段。\n\n-----\n\n"
        '{"choices":["甲","乙"],"state_update":{"current_location":"X"},"internal_notes":""}'
    )
    out = parse_complete_model_output(raw)
    assert "正文一段" in out.narrative
    assert out.choices == ["甲", "乙"]


def test_parse_hr_json_negative_scene_break_then_prose() -> None:
    """分幕 --- 后是大段正文而非 JSON：不误切。"""
    nar = "上幕。\n\n---\n\n下幕很长\n" + "字\n" * 30
    out = parse_complete_model_output(nar)
    assert out.narrative == nar.strip()
    assert not out.choices


def test_stream_hr_then_json_no_meta_marker() -> None:
    sp = MetaStreamSplitter()
    parts: list[str] = []
    chunks = [
        "风起时。\n\n",
        "---\n",
        '{\n  "choices": ["一", "二"],\n  "state_update": {"current_location": "此处"},',
        '\n  "internal_notes": ""\n}',
    ]
    for d in chunks:
        parts.extend(sp.feed(d))
    joined = "".join(parts)
    assert "choices" not in joined
    assert '"一"' not in joined
    fin = sp.finalize()
    assert fin.choices == ["一", "二"]
    assert fin.narrative.strip() == "风起时。"
