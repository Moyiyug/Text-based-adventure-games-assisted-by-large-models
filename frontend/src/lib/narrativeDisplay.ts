/** 与后端 meta_parse.META_MARKER 一致（RULES §5.2） */
export const NARRATIVE_META_MARKER = "---META---";

const _MAX_JUNK_LINE_LEN = 16;

/** 与后端 meta_parse._CHOICE_LINE_TAIL 一致：. 、 ．（U+FF0E）；选项正文最短 2 字与 extract 兜底对齐 */
const _NUMBERED_CHOICE_LINE =
  /^\s*\d+[.\u3001\uFF0E]\s*(.{2,200})\s*$/u;

/**
 * 流式 withhold 可能在叙事尾留下仅含 - * 的短行；与后端 strip_incomplete_separator_tail 对齐。
 */
export function stripIncompleteSeparatorTail(text: string): string {
  let s = text.replace(/\s+$/u, "");
  while (s.length > 0) {
    const lines = s.split("\n");
    const lastRaw = lines[lines.length - 1] ?? "";
    const last = lastRaw.trim();
    if (
      last.length > 0 &&
      last.length <= _MAX_JUNK_LINE_LEN &&
      /^[-* \t]+$/u.test(last) &&
      /[-*]/u.test(last)
    ) {
      s = lines.slice(0, -1).join("\n").replace(/\s+$/u, "");
      continue;
    }
    break;
  }
  return s;
}

/**
 * 去掉文末连续编号选项块（与 extract_choice_lines_from_narrative 识别规则同构），避免与底部按钮重复展示。
 * 仅当末尾连续 ≥2 行匹配编号行时删除，并去掉其前紧邻的空行。
 */
export function stripTrailingNumberedChoiceBlock(text: string): string {
  if (!text.trim()) return text;
  const lines = text.split("\n");
  let i = lines.length - 1;
  while (i >= 0 && lines[i].trim() === "") {
    i -= 1;
  }
  if (i < 0) return text;
  let k = i;
  let firstChoice = -1;
  let count = 0;
  while (k >= 0) {
    const line = lines[k];
    if (line.trim() === "") {
      break;
    }
    if (!_NUMBERED_CHOICE_LINE.test(line)) {
      break;
    }
    firstChoice = k;
    count += 1;
    k -= 1;
  }
  if (count < 2) {
    return text;
  }
  let trimStart = firstChoice;
  while (trimStart > 0 && lines[trimStart - 1].trim() === "") {
    trimStart -= 1;
  }
  return lines.slice(0, trimStart).join("\n").replace(/\s+$/u, "");
}

/**
 * 去掉模型在选项/短句中常用的成对 **、* 加粗标记（不做完整 Markdown）。
 */
export function formatPlainChoiceLabel(s: string): string {
  let t = s.trim();
  let prev = "";
  while (t !== prev) {
    prev = t;
    t = t.replace(/\*\*([^*]+)\*\*/g, "$1");
    t = t.replace(/\*([^*]+)\*/g, "$1");
  }
  return t.trim();
}

/**
 * 模型格式偏差：正文中出现 META--- 且随后较短距离内有 `{`，视为元数据泄漏起点。
 * 从该行首（或该位置）截断，避免误伤仅含字面量 META--- 且无 JSON 的正文。
 */
function stripLooseMetaLeak(text: string): string | null {
  const maxBraceDistance = 160;
  let searchFrom = 0;
  while (true) {
    const i = text.indexOf("META---", searchFrom);
    if (i < 0) return null;
    const after = text.slice(i);
    const br = after.indexOf("{");
    if (br >= 0 && br <= maxBraceDistance) {
      const lineStart = text.lastIndexOf("\n", i);
      const cut = lineStart >= 0 ? lineStart : i;
      return text.slice(0, cut).trimEnd();
    }
    searchFrom = i + 1;
  }
}

/**
 * 与后端 meta_parse.strip_pre_marker_meta_leak 同语义（样例见 tests/test_meta_parse.py
 * test_strip_pre_marker_meta_leak_*）：规范 ---META--- 之前的假标题/```json 尾段
 */
const _RE_PRE_MARKER_META_BRACKET = /^\s*【\s*META\s*(?:JSON)?\s*】\s*$/iu;
const _RE_PRE_MARKER_META_PLAIN = /^\s*META\s*JSON\s*$/iu;
const _RE_PRE_MARKER_FENCE_JSON = /^\s*```\s*json\s*$/iu;
const _RE_PRE_MARKER_HR_ONLY = /^\s*---\s*$/;

export function stripPreMarkerMetaLeak(text: string): string {
  const s = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  if (!s.trim()) return text;
  const lines = s.split("\n");
  const n = lines.length;
  let cutStart: number | null = null;
  for (let i = n - 1; i >= 0; i--) {
    const raw = lines[i];
    if (!raw.trim()) continue;
    if (_RE_PRE_MARKER_META_BRACKET.test(raw) || _RE_PRE_MARKER_META_PLAIN.test(raw)) {
      cutStart = i;
      break;
    }
    if (_RE_PRE_MARKER_FENCE_JSON.test(raw)) {
      const tail = lines.slice(i + 1).join("\n");
      if (tail.slice(0, 2500).includes("{")) {
        cutStart = i;
        break;
      }
    }
  }
  if (cutStart === null) return text;
  let j = cutStart;
  while (j > 0 && lines[j - 1].trim() === "") j -= 1;
  while (j > 0) {
    const prev = lines[j - 1];
    if (
      _RE_PRE_MARKER_META_BRACKET.test(prev) ||
      _RE_PRE_MARKER_META_PLAIN.test(prev) ||
      _RE_PRE_MARKER_FENCE_JSON.test(prev)
    ) {
      j -= 1;
      while (j > 0 && lines[j - 1].trim() === "") j -= 1;
      continue;
    }
    break;
  }
  if (j > 0 && _RE_PRE_MARKER_HR_ONLY.test(lines[j - 1])) {
    j -= 1;
    while (j > 0 && lines[j - 1].trim() === "") j -= 1;
  }
  return lines.slice(0, j).join("\n").replace(/\s+$/u, "");
}

/** 与后端 meta_parse._MD_FIELD_LINE 同语义（见 tests/test_meta_parse.py） */
const _RE_MD_FIELD_KEY =
  /(?:choices|choice_beats|state_update|internal_notes|meta(?:\s+json)?)/iu;
const _RE_MD_FIELD_LINE = new RegExp(
  String.raw`^\s*\*+\s*${_RE_MD_FIELD_KEY.source}(?:\s*:\s*\*+|\s*\*+)\s*$`,
  "iu"
);
const _MD_HR_LOOKBACK_LINES = 12;

/** 与 meta_parse._extract_first_json_object 同构（展示层兜底） */
function extractFirstJsonObject(s: string): string | null {
  const start = s.indexOf("{");
  if (start < 0) return null;
  let depth = 0;
  let inStr = false;
  let esc = false;
  for (let i = start; i < s.length; i++) {
    const c = s[i]!;
    if (inStr) {
      if (esc) esc = false;
      else if (c === "\\") esc = true;
      else if (c === '"') inStr = false;
      continue;
    }
    if (c === '"') {
      inStr = true;
      continue;
    }
    if (c === "{") depth += 1;
    else if (c === "}") {
      depth -= 1;
      if (depth === 0) return s.slice(start, i + 1);
    }
  }
  return null;
}

function isMetaLikeDict(data: Record<string, unknown>): boolean {
  if (Array.isArray(data["choices"])) return true;
  const opts = data["options"];
  if (Array.isArray(opts) && opts.length > 0) return true;
  const su = data["state_update"];
  if (su && typeof su === "object" && Object.keys(su as object).length > 0)
    return true;
  const flat = [
    "current_location",
    "active_goal",
    "important_items",
    "npc_relations",
  ] as const;
  return flat.some((k) => k in data);
}

/**
 * 与 meta_parse._find_hr_json_split 同语义：文末 `---` / `-----+` 后裸露 JSON 尾段从展示中去掉。
 */
export function stripHrJsonTailForDisplay(text: string): string {
  const s = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  if (!s.trim()) return text;
  const lines = s.split("\n");
  const reThree = /^---\s*$/u;
  const reFive = /^-{5,}\s*$/u;
  const isHr = (ln: string) => reThree.test(ln) || reFive.test(ln);
  const offsets: number[] = [];
  let o = 0;
  for (let i = 0; i < lines.length; i++) {
    offsets.push(o);
    if (i < lines.length - 1) o += lines[i]!.length + 1;
    else o += lines[i]!.length;
  }
  const tailPos = (idx: number) => {
    const st = offsets[idx]!;
    if (idx < lines.length - 1) return st + lines[idx]!.length + 1;
    return st + lines[idx]!.length;
  };
  for (let idx = lines.length - 1; idx >= 0; idx--) {
    if (!isHr(lines[idx]!)) continue;
    const tp = tailPos(idx);
    const tail = s.slice(tp);
    const stripped = tail.replace(/^[\n\r\t ]+/u, "");
    if (!stripped.startsWith("{")) continue;
    const braceAbs = tp + (tail.length - stripped.length);
    const blob = extractFirstJsonObject(s.slice(braceAbs));
    if (!blob) continue;
    try {
      const data = JSON.parse(blob) as Record<string, unknown>;
      if (!isMetaLikeDict(data)) continue;
    } catch {
      continue;
    }
    return s.slice(0, offsets[idx]!).replace(/\s+$/u, "");
  }
  return text;
}

export function stripPseudoMarkdownMetaTail(text: string): string {
  const s = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  if (!s.trim()) return text;
  const lines = s.split("\n");
  const n = lines.length;
  let fieldIdx: number | null = null;
  for (let i = n - 1; i >= 0; i--) {
    if (_RE_MD_FIELD_LINE.test(lines[i])) {
      fieldIdx = i;
      break;
    }
  }
  if (fieldIdx === null) return text;
  let cut = fieldIdx;
  const low = Math.max(0, fieldIdx - _MD_HR_LOOKBACK_LINES);
  for (let j = fieldIdx - 1; j >= low; j--) {
    if (_RE_PRE_MARKER_HR_ONLY.test(lines[j])) {
      cut = j;
      break;
    }
  }
  return lines.slice(0, cut).join("\n").replace(/\s+$/u, "");
}

/** 流式阶段：伪字段整行或行尾未完成 `**choices:` / `**META` 等 */
const _RE_MD_FIELD_LINE_RELAXED = new RegExp(
  String.raw`^\s*\*{2,}\s*${_RE_MD_FIELD_KEY.source}(?:\s*:\s*\*+|\s*\*+|\s*:\s*$)`,
  "iu"
);

const _META_FIELD_KEYS = [
  "choices:",
  "choice_beats:",
  "state_update:",
  "internal_notes:",
  "meta",
  "meta json",
] as const;

/**
 * 最后一行是否为「正在输入中的」`**choices:` / `**choice_beats:` 等（须以至少 `**` 开头，降低 `* 旁白` 误伤）。
 */
function _lastLineCouldBeMetaFieldPrefix(line: string): boolean {
  const t = line.replace(/\r\n/g, "\n");
  if (!/^\s*\*{2,}/u.test(t)) return false;
  let rest = t.replace(/^\s*\*+\s*/u, "").toLowerCase();
  rest = rest.replace(/\*+$/u, "");
  if (!rest) return true;
  return _META_FIELD_KEYS.some((k) =>
    rest.length <= k.length ? k.startsWith(rest) : rest.startsWith(k)
  );
}

/**
 * 流式 token 阶段专用：在整行匹配尚未成立前遮蔽 `**cho…`、`**choices:**` 与后续列表，避免闪现在气泡内。
 * 非流式勿用（由 stripMetaSuffixForDisplay 的 streaming 开关控制）。
 */
export function stripInflightChoiceMarkdownDisplay(text: string): string {
  const s = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  if (!s.trim()) return text;
  const lines = s.split("\n");
  let cutFrom = lines.length;
  for (let i = 0; i < lines.length; i++) {
    if (_RE_MD_FIELD_LINE_RELAXED.test(lines[i])) {
      cutFrom = i;
      break;
    }
  }
  if (cutFrom === lines.length) {
    const last = lines[lines.length - 1] ?? "";
    if (last.trim() && _lastLineCouldBeMetaFieldPrefix(last)) {
      cutFrom = lines.length - 1;
    }
  }
  if (cutFrom < lines.length) {
    const low = Math.max(0, cutFrom - 13);
    for (let j = cutFrom - 1; j >= low; j--) {
      if (_RE_PRE_MARKER_HR_ONLY.test(lines[j])) {
        cutFrom = j;
        break;
      }
    }
    return lines.slice(0, cutFrom).join("\n").replace(/\s+$/u, "");
  }
  return text;
}

export interface StripMetaSuffixOptions {
  /**
   * 是否去掉文末连续编号选项块（与底部按钮去重）。
   * 默认 true；当结构化 metadata 尚无有效 choices 时应为 false，避免「按钮空 + 正文编号也被剥掉」。
   */
  stripNumberedTail?: boolean;
  /** 为 true 时先对流式泄漏尾段做 in-flight 遮蔽（RULES §5.1 不改变 SSE，仅展示层） */
  streaming?: boolean;
}

/**
 * 气泡展示用：去掉误落入正文的协议尾段，不解析 JSON。
 * 状态仍以 API / SSE state_update 为准。
 */
export function stripMetaSuffixForDisplay(
  text: string,
  options?: StripMetaSuffixOptions
): string {
  const stripNumberedTail = options?.stripNumberedTail !== false;
  let raw = text;
  if (options?.streaming) {
    raw = stripInflightChoiceMarkdownDisplay(raw);
  }
  let base: string;
  const std = raw.indexOf(NARRATIVE_META_MARKER);
  if (std >= 0) {
    base = raw.slice(0, std).trimEnd();
  } else {
    const loose = stripLooseMetaLeak(raw);
    base = loose !== null ? loose : raw;
  }
  base = stripPreMarkerMetaLeak(base);
  base = stripPseudoMarkdownMetaTail(base);
  base = stripHrJsonTailForDisplay(base);
  const cleaned = stripIncompleteSeparatorTail(base);
  return stripNumberedTail
    ? stripTrailingNumberedChoiceBlock(cleaned)
    : cleaned;
}
