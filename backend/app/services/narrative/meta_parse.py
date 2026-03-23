"""模型输出中叙事正文与 ---META--- 后 JSON 的拆分与解析。"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

META_MARKER = "---META---"
_ALT_META_VARIANTS = ("**META---", "META---")
_CANONICAL_LEN = len(META_MARKER)
_STATE_KEYS_FLAT = (
    "current_location",
    "active_goal",
    "important_items",
    "npc_relations",
)

# 叙事末尾编号行兜底：多形态 + 尾部窗口（见 extract_choice_lines_from_narrative）
_CHOICE_LINE_TAIL_LINES = 60
_CHOICE_LINE_TAIL_CHARS = 4000
_CHOICE_LINE_RES: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.MULTILINE)
    for p in (
        r"^\s*\d+[\.\、．]\s*(.{2,200})\s*$",  # 1. / 1、 / 1．
        r"^\s*\d+[\)）]\s*(.{2,200})\s*$",  # 1) / 1）
        r"^\s*[（(]\s*\d+\s*[)）]\s*(.{2,200})\s*$",  # （1）/ (1)
    )
)


def normalize_model_text(s: str) -> str:
    """统一换行、去 BOM；不改变语义外的空白策略。"""
    t = s.replace("\r\n", "\n").replace("\r", "\n")
    if t.startswith("\ufeff"):
        t = t[1:]
    return t


def _find_alt_meta_leak(text: str, *, require_brace_after: bool) -> tuple[int, int] | None:
    """
    模型泄漏形态：未输出完整 ---META---；优先匹配 **META---，再匹配裸 META---。
    裸 META--- 若属于标准 marker 内部、或 **META--- 的子串，则跳过。
    """
    for needle in _ALT_META_VARIANTS:
        nlen = len(needle)
        pos = 0
        while True:
            j = text.find(needle, pos)
            if j < 0:
                break
            if needle == "META---":
                if j >= 3 and text[j - 3 : j + 8] == META_MARKER:
                    pos = j + 1
                    continue
                if j >= 2 and text[j - 2 : j + 7] == "**META---":
                    pos = j + 1
                    continue
            tail = text[j + nlen :]
            if require_brace_after and "{" not in tail:
                pos = j + 1
                continue
            return (j, nlen)
    return None


# 容错：单独一行 --- 或 ≥5 连字符后接多行 JSON（非规范 ---META---）
_RE_HR_META_THREE = re.compile(r"^---\s*$")
_RE_HR_META_LONG = re.compile(r"^-{5,}\s*$")
# withhold：HR 后至首个 `{` 的窗口内须出现 `{`，避免误锁分幕 ---
_HR_JSON_LEAD_MAX_CHARS = 800


def _is_hr_meta_separator_line(line: str) -> bool:
    return bool(_RE_HR_META_THREE.match(line) or _RE_HR_META_LONG.match(line))


def _line_offsets_for_split(text: str) -> tuple[list[str], list[int]]:
    lines = text.split("\n")
    offsets: list[int] = []
    pos = 0
    for i, ln in enumerate(lines):
        offsets.append(pos)
        if i < len(lines) - 1:
            pos += len(ln) + 1
        else:
            pos += len(ln)
    return lines, offsets


def _tail_pos_after_line(lines: list[str], offsets: list[int], idx: int) -> int:
    start = offsets[idx]
    if idx < len(lines) - 1:
        return start + len(lines[idx]) + 1
    return start + len(lines[idx])


def _is_meta_like_dict(data: Any) -> bool:
    """HR 后 JSON 须像 META：含 choices/options/state 键或扁平 state 字段。"""
    if not isinstance(data, dict):
        return False
    if isinstance(data.get("choices"), list):
        return True
    if isinstance(data.get("options"), list) and data["options"]:
        return True
    su = data.get("state_update")
    if isinstance(su, dict) and su:
        return True
    if any(k in data for k in _STATE_KEYS_FLAT):
        return True
    return False


def _find_hr_json_split(text: str) -> tuple[int, int] | None:
    """
    自文末向上找单独一行 --- 或 -----+，其后子串须能抽出完整 JSON 对象且像 META。
    返回 (HR 行起点, HR 行首到 JSON「{」起点的长度)，供 rest = text[i+mlen:].
    """
    t = normalize_model_text(text)
    if not t.strip():
        return None
    lines, offsets = _line_offsets_for_split(t)
    for idx in range(len(lines) - 1, -1, -1):
        if not _is_hr_meta_separator_line(lines[idx]):
            continue
        tail_pos = _tail_pos_after_line(lines, offsets, idx)
        tail = t[tail_pos:]
        stripped = tail.lstrip("\n\r\t ")
        if not stripped.startswith("{"):
            continue
        rel = len(tail) - len(stripped)
        brace_abs = tail_pos + rel
        blob = _extract_first_json_object(t[brace_abs:])
        if not blob:
            continue
        try:
            data = json.loads(blob)
        except json.JSONDecodeError:
            continue
        if not _is_meta_like_dict(data):
            continue
        line_start = offsets[idx]
        mlen = brace_abs - line_start
        return (line_start, mlen)
    return None


def find_meta_split(text: str) -> tuple[int, int] | None:
    """返回 (marker 起始下标, marker 长度)；未找到返回 None。"""
    if META_MARKER in text:
        return (text.index(META_MARKER), _CANONICAL_LEN)
    alt = _find_alt_meta_leak(text, require_brace_after=True)
    if alt is not None:
        return alt
    return _find_hr_json_split(text)


def _hr_json_withhold_start(text: str) -> int | None:
    """
    流式：在 JSON 未闭合前避免把 HR 及之后内容推给前端。
    - HR 后窗口内已出现「{」；或
    - 缓冲以 HR 行结尾且其后仅空白（模型即将写 JSON）。
    """
    t = normalize_model_text(text)
    if not t:
        return None
    lines, offsets = _line_offsets_for_split(t)
    for idx in range(len(lines) - 1, -1, -1):
        if not _is_hr_meta_separator_line(lines[idx]):
            continue
        tail_pos = _tail_pos_after_line(lines, offsets, idx)
        tail = t[tail_pos:]
        window = tail.lstrip("\n\t ")[:_HR_JSON_LEAD_MAX_CHARS]
        if "{" in window:
            return offsets[idx]
    j = len(lines) - 1
    while j >= 0 and not lines[j].strip():
        j -= 1
    if j < 0:
        return None
    if _is_hr_meta_separator_line(lines[j]):
        tail_pos = _tail_pos_after_line(lines, offsets, j)
        if not t[tail_pos:].strip():
            return offsets[j]
    return None


def _tail_lines_for_choice_scan(narrative: str) -> list[str]:
    """取叙事尾部若干行，超长时按字符截断尾部子串再分行，降低长旁白把选项顶出窗口的概率。"""
    lines = narrative.strip().split("\n")
    chunk = lines[-_CHOICE_LINE_TAIL_LINES:] if lines else []
    text = "\n".join(chunk)
    if len(text) > _CHOICE_LINE_TAIL_CHARS:
        text = text[-_CHOICE_LINE_TAIL_CHARS:]
    return text.split("\n") if text else []


def _match_choice_line_label(line: str) -> str | None:
    sline = line.strip()
    for cre in _CHOICE_LINE_RES:
        m = cre.match(sline)
        if m:
            s = m.group(1).strip()
            if len(s) >= 2:
                return s
    return None


def _extract_consecutive_numbered_block(lines: list[str]) -> list[str]:
    """从最后一行向上取连续编号行（与前端文末块语义一致），至少 2 条。"""
    i = len(lines) - 1
    while i >= 0 and not lines[i].strip():
        i -= 1
    if i < 0:
        return []
    block: list[str] = []
    while i >= 0:
        raw = lines[i]
        if not raw.strip():
            break
        label = _match_choice_line_label(raw)
        if label is None:
            break
        block.insert(0, label)
        i -= 1
    if len(block) < 2:
        return []
    return block[:4]


def _extract_scattered_choice_lines(tail: str) -> list[str]:
    """在尾部文本内按出现顺序收集编号行，去重，至少 2 条。"""
    matches: list[tuple[int, str]] = []
    for cre in _CHOICE_LINE_RES:
        for m in cre.finditer(tail):
            s = m.group(1).strip()
            if len(s) >= 2:
                matches.append((m.start(), s))
    matches.sort(key=lambda x: x[0])
    found: list[str] = []
    for _, s in matches:
        if s not in found:
            found.append(s)
        if len(found) >= 4:
            break
    if len(found) < 2:
        return []
    return found[:4]


def extract_choice_lines_from_narrative(narrative: str) -> list[str]:
    """
    当 JSON 无 choices 时的保守兜底：扫尾部约 60 行（约 4000 字上限），支持 1. / 1）/ （1）等形态。
    优先尝试文末连续编号块，不足再回退到尾部任意位置匹配（保持与历史测试兼容）。
    """
    if not narrative or not narrative.strip():
        return []
    lines = _tail_lines_for_choice_scan(narrative)
    consec = _extract_consecutive_numbered_block(lines)
    if len(consec) >= 2:
        return consec
    tail = "\n".join(lines)
    return _extract_scattered_choice_lines(tail)


def _coerce_choice_beats(data: dict[str, Any], choices: list[str]) -> list[str] | None:
    """META 可选键 choice_beats：须与 choices 等长。"""
    raw = data.get("choice_beats")
    if not isinstance(raw, list) or not raw or not choices:
        return None
    out = [str(x).strip() for x in raw]
    if len(out) != len(choices):
        return None
    if any(not x for x in out):
        return None
    return out


def _coerce_choice_list(data: dict[str, Any]) -> list[str]:
    """协议字段为 choices；兼容模型误用 options。"""
    raw = data.get("choices")
    if not isinstance(raw, list) or not raw:
        alt = data.get("options")
        if isinstance(alt, list) and alt:
            raw = alt
        else:
            raw = []
    if not isinstance(raw, list):
        return []
    return [str(x) for x in raw if str(x).strip()]


def _merge_state_update_from_dict(data: dict[str, Any]) -> dict[str, Any]:
    """优先 state_update；若缺失或空则从顶层拷贝叙事 state 键（模型偶发扁平 JSON）。"""
    su = data.get("state_update")
    if not isinstance(su, dict):
        su = {}
    if not su:
        return {k: data[k] for k in _STATE_KEYS_FLAT if k in data}
    for k in _STATE_KEYS_FLAT:
        if k not in su and k in data:
            su[k] = data[k]
    return su


# 流式阶段保留末尾避免误切分 marker 前缀
_HOLD_BACK = max(len(META_MARKER) + 5, 24)


def strip_incomplete_separator_tail(text: str) -> str:
    """
    去掉叙事末尾流式 withhold 残留的短行（仅含 - * 与空白，长度受限），避免 UI 出现孤立 --- / **。
    """
    s = text.rstrip()
    while s:
        lines = s.split("\n")
        last = lines[-1].strip()
        if (
            last
            and len(last) <= 16
            and all(c in "-* \t" for c in last)
            and any(c in "-*" for c in last)
        ):
            s = "\n".join(lines[:-1]).rstrip()
            continue
        break
    return s


# 模型在规范 ---META--- 之前输出的「假 META」标题（整行），须从叙事尾部剥掉（与前端 narrativeDisplay 同语义）。
_RE_PRE_MARKER_META_BRACKET = re.compile(r"^\s*【\s*META\s*(?:JSON)?\s*】\s*$", re.IGNORECASE)
_RE_PRE_MARKER_META_PLAIN = re.compile(r"^\s*META\s*JSON\s*$", re.IGNORECASE)
# 仅 ```json 行作为泄漏围栏起点，避免误伤正文中的普通代码块。
_RE_PRE_MARKER_FENCE_JSON = re.compile(r"^\s*```\s*json\s*$", re.IGNORECASE)
_RE_PRE_MARKER_HR_ONLY = re.compile(r"^\s*---\s*$")


def strip_pre_marker_meta_leak(text: str) -> str:
    """
    去掉规范分隔符之前误入 narrative 的尾部垃圾：如「【META JSON】」、```json 围栏开头等。
    流式切分以首个 ---META--- / META--- 为准，其前的这些内容会整段算进 narrative，须落库前卫生处理。
    """
    if not text or not text.strip():
        return text
    lines = text.split("\n")
    n = len(lines)
    cut_start: int | None = None

    for i in range(n - 1, -1, -1):
        raw = lines[i]
        if not raw.strip():
            continue
        if _RE_PRE_MARKER_META_BRACKET.match(raw) or _RE_PRE_MARKER_META_PLAIN.match(raw):
            cut_start = i
            break
        if _RE_PRE_MARKER_FENCE_JSON.match(raw):
            tail = "\n".join(lines[i + 1 :])
            if "{" in tail[:2500]:
                cut_start = i
                break

    if cut_start is None:
        return text

    j = cut_start
    while j > 0 and lines[j - 1].strip() == "":
        j -= 1
    # ```json 上方常紧跟「【META JSON】」或单独一行 META JSON，一并剥掉
    while j > 0:
        prev = lines[j - 1]
        if (
            _RE_PRE_MARKER_META_BRACKET.match(prev)
            or _RE_PRE_MARKER_META_PLAIN.match(prev)
            or _RE_PRE_MARKER_FENCE_JSON.match(prev)
        ):
            j -= 1
            while j > 0 and lines[j - 1].strip() == "":
                j -= 1
            continue
        break
    if j > 0 and _RE_PRE_MARKER_HR_ONLY.match(lines[j - 1]):
        j -= 1
        while j > 0 and lines[j - 1].strip() == "":
            j -= 1
    return "\n".join(lines[:j]).rstrip()


# 模型在 ---META--- 之前用 Markdown 伪字段列举 choices/仿协议标题 **META**（截图形态）
# 匹配 **choices:** / **choices** / **META** / **META JSON** 等整行标题；与前端 narrativeDisplay._RE_MD_FIELD_LINE 同构
_MD_FIELD_KEY = (
    r"(?:choices|choice_beats|state_update|internal_notes|meta(?:\s+json)?)"
)
_MD_FIELD_LINE = re.compile(
    rf"^\s*\*+\s*{_MD_FIELD_KEY}(?:\s*:\s*\*+|\s*\*+)\s*$",
    re.IGNORECASE,
)
# 自伪字段标题行起向上最多回溯多少行寻找单独一行 ---，避免误切远处分幕线
_MD_HR_LOOKBACK_LINES = 12


def strip_pseudo_markdown_meta_tail(text: str) -> str:
    """
    去掉叙事尾部「---」+ Markdown 伪字段（**choices:** / **META** / **META JSON** / **choice_beats:** 等）泄漏块。
    规则：自文末向上找最后一行匹配伪字段标题；若其上方 ≤12 行内有单独一行 ---，截断于该 ---；
    否则截断于伪字段标题行首。不误伤正文内非标题行的 “choices”/“meta” 字样。
    """
    if not text or not text.strip():
        return text
    lines = text.split("\n")
    n = len(lines)
    field_idx: int | None = None
    for i in range(n - 1, -1, -1):
        if _MD_FIELD_LINE.match(lines[i]):
            field_idx = i
            break
    if field_idx is None:
        return text
    cut = field_idx
    low = max(0, field_idx - _MD_HR_LOOKBACK_LINES)
    for j in range(field_idx - 1, low - 1, -1):
        if _RE_PRE_MARKER_HR_ONLY.match(lines[j]):
            cut = j
            break
    return "\n".join(lines[:cut]).rstrip()


def strip_leaking_meta_suffix(text: str) -> str:
    """
    落库/回包前：若叙事正文仍含协议分隔符，截断其后；再剥假 META 尾段与 Markdown 伪字段尾段。
    顺序：去重复 ---META--- 尾 → strip_incomplete_separator_tail → strip_pre_marker_meta_leak
    → strip_pseudo_markdown_meta_tail → strip_incomplete_separator_tail。
    """
    if META_MARKER in text:
        i = text.index(META_MARKER)
        s = text[:i].rstrip()
    else:
        s = text
    s = strip_incomplete_separator_tail(s)
    s = strip_pre_marker_meta_leak(s)
    s = strip_pseudo_markdown_meta_tail(s)
    return strip_incomplete_separator_tail(s)


def _strip_code_fence(block: str) -> str:
    """去掉 ``` / ```json 围栏，便于 json.loads。"""
    s = block.strip()
    if not s.startswith("```"):
        return s
    first_nl = s.find("\n")
    if first_nl >= 0:
        s = s[first_nl + 1 :]
    fence = s.rfind("```")
    if fence >= 0:
        s = s[:fence]
    return s.strip()


def _extract_first_json_object(s: str) -> str | None:
    """从首个「{」起做花括号平衡（尊重字符串内引号与转义），提取完整 JSON 对象子串。"""
    start = s.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(s)):
        c = s[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[start : i + 1]
    return None


@dataclass
class ParsedTurnOutput:
    """流式/整段解析结果。choices_source：model_json / narrative_regex / llm_fallback / none（engine 可更新）。"""

    narrative: str
    choices: list[str]
    state_update: dict[str, Any]
    internal_notes: str
    parse_error: str | None = None
    choices_source: str | None = None
    choice_beats: list[str] | None = None


def parse_complete_model_output(full: str) -> ParsedTurnOutput:
    """非流式整段：规范化后按规范或泄漏 marker 切分，再解析 JSON。"""
    text = normalize_model_text(full)
    sp = find_meta_split(text)
    if sp is None:
        nar = strip_incomplete_separator_tail(text.strip())
        fb = extract_choice_lines_from_narrative(nar)
        return ParsedTurnOutput(
            nar,
            fb,
            {},
            "",
            None,
            choices_source="narrative_regex" if fb else None,
            choice_beats=None,
        )
    i, mlen = sp
    narrative = text[:i].strip()
    rest = text[i + mlen :].strip()
    return _parse_meta_after_marker(narrative, rest)


def _load_meta_json_dict(meta_block: str) -> dict[str, Any]:
    """先试单行 / 整块；失败则尝试去围栏 + 花括号扫描。"""
    stripped = _strip_code_fence(meta_block)
    line = stripped.splitlines()[0].strip() if stripped else ""
    whole = stripped.strip()
    last_err: Exception | None = None
    for candidate in (line, whole):
        if not candidate:
            continue
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
            raise ValueError("meta 须为 JSON 对象")
        except (json.JSONDecodeError, ValueError) as e:
            last_err = e
            continue
    blob = _extract_first_json_object(stripped)
    if blob:
        try:
            data = json.loads(blob)
            if isinstance(data, dict):
                return data
            raise ValueError("meta 须为 JSON 对象")
        except (json.JSONDecodeError, ValueError) as e:
            last_err = e
    raise ValueError(str(last_err) if last_err else "META JSON 无法解析")


def _parse_meta_after_marker(narrative: str, meta_block: str) -> ParsedTurnOutput:
    nar_clean = strip_incomplete_separator_tail(narrative)
    if not meta_block:
        fb = extract_choice_lines_from_narrative(nar_clean)
        return ParsedTurnOutput(
            nar_clean,
            fb,
            {},
            "",
            "META 后为空" if not fb else None,
            choices_source="narrative_regex" if fb else None,
            choice_beats=None,
        )
    try:
        data = _load_meta_json_dict(meta_block)
        choices = _coerce_choice_list(data)
        beats: list[str] | None = None
        if choices:
            src = "model_json"
            beats = _coerce_choice_beats(data, choices)
        else:
            choices = extract_choice_lines_from_narrative(nar_clean)
            src = "narrative_regex" if choices else None
            beats = None
        su = _merge_state_update_from_dict(data)
        notes = data.get("internal_notes", "")
        if notes is not None and not isinstance(notes, str):
            notes = str(notes)
        return ParsedTurnOutput(
            nar_clean,
            choices,
            su,
            notes or "",
            None,
            choices_source=src,
            choice_beats=beats,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("META JSON 解析失败: %s", e)
        fb = extract_choice_lines_from_narrative(nar_clean)
        return ParsedTurnOutput(
            nar_clean,
            fb,
            {},
            "",
            str(e)[:500],
            choices_source="narrative_regex" if fb else None,
            choice_beats=None,
        )


def _resolve_meta_in_buffer(buf: str) -> tuple[int, int] | None:
    """流式缓冲内定位 marker；规范 → 泄漏 META--- → HR+完整 JSON 容错。"""
    idx = buf.find(META_MARKER)
    if idx >= 0:
        return (idx, _CANONICAL_LEN)
    alt = _find_alt_meta_leak(buf, require_brace_after=True)
    if alt is not None:
        return alt
    return _find_hr_json_split(buf)


@dataclass
class MetaStreamSplitter:
    """边收流边输出叙事片段；流结束后解析 JSON。"""

    _buffer: str = ""
    _emitted_narrative_len: int = 0
    _meta_found: bool = False
    _meta_index: int = -1
    _meta_marker_len: int = field(default=_CANONICAL_LEN, repr=False)

    def accumulated_raw(self) -> str:
        """流式结束后完整缓冲（供日志观测，可能含 ---META--- 与 JSON）。"""
        return self._buffer

    def feed(self, delta: str) -> list[str]:
        """返回本轮可立刻转发给前端的叙事文本片段（可能为空列表）。"""
        if not delta:
            return []
        self._buffer += delta
        self._buffer = normalize_model_text(self._buffer)
        if self._meta_found:
            return []

        resolved = _resolve_meta_in_buffer(self._buffer)
        if resolved is not None:
            idx, mlen = resolved
            self._meta_found = True
            self._meta_index = idx
            self._meta_marker_len = mlen
            narrative_all = self._buffer[:idx]
            chunk = narrative_all[self._emitted_narrative_len :]
            self._emitted_narrative_len = len(narrative_all)
            return [chunk] if chunk else []

        safe_end = len(self._buffer) - _HOLD_BACK
        wh = _hr_json_withhold_start(self._buffer)
        if wh is not None:
            safe_end = min(safe_end, wh)
        if safe_end <= self._emitted_narrative_len:
            return []
        chunk = self._buffer[self._emitted_narrative_len : safe_end]
        self._emitted_narrative_len = safe_end
        return [chunk] if chunk else []

    def finalize(self) -> ParsedTurnOutput:
        """流结束后调用，解析 meta（若曾出现 marker）；否则整缓冲再走 find_meta_split（含 HR+JSON）。"""
        if not self._meta_found:
            return parse_complete_model_output(self._buffer)

        narrative_all = self._buffer[: self._meta_index]
        rest = self._buffer[self._meta_index + self._meta_marker_len :].strip()
        return _parse_meta_after_marker(narrative_all.strip(), rest)
