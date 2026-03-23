"""提示词拼装。模板正文由 DB seed / 管理端维护，此处只做占位符替换与 messages 组装。"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prompt_template import PromptTemplate
from app.services.profile_loader import profile_bundle_nonempty

# 环境开关 NARRATIVE_CONCISE_MODE 为真时追加到 system 末尾（与 seed META_BLOCK 互补）。
NARRATIVE_CONCISE_SYSTEM_SUFFIX = (
    "【篇幅软约束】本回合叙事以推进为主，宜 3～6 个短段、避免同轮重复铺陈；"
    "choices 每条一行、核心动作短句优先，括号补充不超过半句。此为建议非硬截断。"
)

# NARRATIVE_SPLIT_CHOICES_LLM 为真时追加到主生成 system：第一轮只写叙事+state，选项由第二次调用产出。
NARRATIVE_SPLIT_PHASE_ONE_SYSTEM_SUFFIX = (
    "【分步生成·叙事轮】选项将由系统在叙事后**另一次**请求生成。本轮要求："
    "正文只写可读的剧情与氛围收束，**禁止**在叙事中出现任何玩家可选行动列表（含「选择你的行动」、"
    "Markdown 列表 `*` / `-`、编号列表 `1.` 等）。"
    "META JSON 中 `choices` 固定输出空数组 `[]`；`choice_beats` 可省略；"
    "仍须完整输出 `state_update` 与 `internal_notes`（与常规回合相同约束）。"
)

# NARRATIVE_TWO_PHASE_ENABLED：第一轮只叙事；第二轮专出 META JSON（与 SPLIT_CHOICES 互斥由 engine 处理）。
TWO_PHASE_ROUND_ONE_SUFFIX = (
    "【双阶段·叙事轮】第一轮**只**输出玩家可读剧情正文，**禁止**输出单独一行 `---META---`、`-----`、以及任何 JSON；"
    "**禁止**在正文内列出可点选项（编号/Markdown 列表）。选项与状态将由系统**紧接着的第二轮**请求生成。"
)

TWO_PHASE_ROUND_TWO_SUFFIX = (
    "【双阶段·元数据轮】根据下列叙事与检索块，**只**输出：`---META---` 单独一行，换行后**单行** JSON，"
    "须含 choices（2～4 条）、state_update（四键齐全）、internal_notes；"
    "严谨模式 strict 还须输出与 choices 等长的 choice_beats。**禁止**输出叙事正文，禁止 Markdown 代码围栏。"
)

# 第二次调用（选项专模）追加在 system 末尾的任务说明。
CHOICES_ONLY_TASK_SUFFIX = (
    "【分步生成·选项轮】上一条 user 为检索证据，本条含已定叙事与状态。"
    "请只输出**一行**合法 JSON 对象，不要 Markdown、不要解释。"
    '键 "choices"：2～4 个字符串，每条为简短中文可执行行动，须彼此区分且与证据及叙事一致；禁止编号前缀。'
    '严谨模式 strict 下须同时输出 "choice_beats"：字符串数组，与 choices 等长；每项 1～2 句第三人称大纲，'
    "表示若玩家点该选项时下一段核心转折（非成品正文）。"
    "创意模式 creative 下可不输出 choice_beats，或输出与 choices 等长的数组。"
    "若无法给出有效分支，仍输出 choices 为两个占位性探索类短句，避免空数组。"
)


async def load_prompt_templates(db: AsyncSession, mode: str) -> dict[str, str]:
    """
    按 layer 取当前 mode 或 applicable_mode=all 的激活模板（每 layer 取 id 最大的一条）。
    返回键：system, retrieval, gm, style
    """
    if mode not in ("strict", "creative"):
        raise ValueError("mode 须为 strict 或 creative")

    res = await db.execute(
        select(PromptTemplate).where(
            PromptTemplate.is_active.is_(True),
            (
                (PromptTemplate.applicable_mode == mode)
                | (PromptTemplate.applicable_mode == "all")
            ),
        )
    )
    rows = list(res.scalars().all())
    by_layer: dict[str, PromptTemplate] = {}
    for pt in rows:
        if pt.layer not in ("system", "retrieval", "gm", "style"):
            continue
        cur = by_layer.get(pt.layer)
        if cur is None or pt.id > cur.id:
            by_layer[pt.layer] = pt
    out: dict[str, str] = {}
    for layer in ("system", "retrieval", "gm", "style"):
        p = by_layer.get(layer)
        if p is not None:
            out[layer] = p.template_text
    return out


def build_system_prompt(
    mode: str,
    style_config: dict[str, Any] | None,
    templates: dict[str, str],
) -> str:
    """合并 system + gm + style 层（不含 retrieval）。"""
    style_json = json.dumps(style_config or {}, ensure_ascii=False)
    parts: list[str] = []
    for key in ("system", "gm", "style"):
        raw = templates.get(key)
        if not raw:
            continue
        if "{style_config}" in raw:
            parts.append(raw.replace("{style_config}", style_json))
        else:
            parts.append(raw)
    return "\n\n".join(parts).strip() or "你是叙事助手。"


def build_retrieval_prompt(context: str, templates: dict[str, str]) -> str:
    """检索证据包装。"""
    raw = templates.get("retrieval") or "【检索证据】\n{context}"
    return raw.replace("{context}", context.strip() or "（无）").strip()


def build_choices_only_prompt(
    *,
    context: str,
    state: dict[str, Any] | None,
    narrative: str,
    user_input: str,
    mode: str,
    style_config: dict[str, Any] | None,
    templates: dict[str, str],
    narrative_max_chars: int = 8000,
) -> list[dict[str, str]]:
    """
    分步生成第二轮：与主生成共用检索块格式，另附状态 + 已定叙事 + 玩家输入。
    """
    system_text = build_system_prompt(mode, style_config, templates)
    system_text = f"{system_text}\n\n{CHOICES_ONLY_TASK_SUFFIX}".strip()
    retrieval_text = build_retrieval_prompt(context, templates)
    state_json = json.dumps(state or {}, ensure_ascii=False)
    nar = narrative.strip()
    if len(nar) > narrative_max_chars:
        nar = nar[-narrative_max_chars:]
    tail_chunks = [
        f"[当前会话状态 JSON]\n{state_json}",
        f"[本回合已定叙事]\n{nar or '（空）'}",
        f"[玩家本轮输入]\n{user_input.strip() or '（无）'}",
    ]
    tail = "\n\n".join(tail_chunks)
    return [
        {"role": "system", "content": system_text},
        {"role": "user", "content": f"[检索与设定证据]\n{retrieval_text}"},
        {"role": "user", "content": tail},
    ]


def build_two_phase_meta_prompt(
    *,
    context: str,
    state: dict[str, Any] | None,
    narrative: str,
    user_input: str,
    mode: str,
    style_config: dict[str, Any] | None,
    templates: dict[str, str],
    narrative_max_chars: int = 12000,
) -> list[dict[str, str]]:
    """双阶段第二轮：从已定叙事 + 检索生成完整 META JSON。"""
    system_text = build_system_prompt(mode, style_config, templates)
    system_text = f"{system_text}\n\n{TWO_PHASE_ROUND_TWO_SUFFIX}".strip()
    retrieval_text = build_retrieval_prompt(context, templates)
    state_json = json.dumps(state or {}, ensure_ascii=False)
    nar = narrative.strip()
    if len(nar) > narrative_max_chars:
        nar = nar[-narrative_max_chars:]
    tail = "\n\n".join(
        [
            f"[当前会话状态 JSON]\n{state_json}",
            f"[第一轮已定叙事]\n{nar or '（空）'}",
            f"[玩家本轮输入]\n{user_input.strip() or '（无）'}",
        ]
    )
    return [
        {"role": "system", "content": system_text},
        {"role": "user", "content": f"[检索与设定证据]\n{retrieval_text}"},
        {"role": "user", "content": tail},
    ]


def build_generation_prompt(
    user_input: str,
    context: str,
    state: dict[str, Any] | None,
    profile: dict[str, Any] | None,
    *,
    mode: str,
    style_config: dict[str, Any] | None,
    templates: dict[str, str],
    history: list[dict[str, str]] | None = None,
    turn_hints: str | None = None,
    narrative_concise_mode: bool = False,
    narrative_split_choices_phase_one: bool = False,
    narrative_two_phase_round_one: bool = False,
) -> list[dict[str, str]]:
    """
    返回 OpenAI 风格 messages：system（含 system+gm+style）→ user（检索块）→ 可选 history → user（状态+画像+可选回合提示+本轮输入）。
    narrative_concise_mode：为 True 时在 system 末尾追加篇幅软提示（与 DB 模板互补）。
    narrative_split_choices_phase_one：为 True 时追加分步生成第一轮后缀（choices 置空、正文禁止列选项）。
    narrative_two_phase_round_one：为 True 时追加双阶段第一轮后缀（只叙事、无 META）；与 split 互斥由调用方保证。
    """
    system_text = build_system_prompt(mode, style_config, templates)
    if narrative_two_phase_round_one:
        system_text = f"{system_text}\n\n{TWO_PHASE_ROUND_ONE_SUFFIX}".strip()
    if narrative_split_choices_phase_one:
        system_text = f"{system_text}\n\n{NARRATIVE_SPLIT_PHASE_ONE_SYSTEM_SUFFIX}".strip()
    if narrative_concise_mode:
        system_text = f"{system_text}\n\n{NARRATIVE_CONCISE_SYSTEM_SUFFIX}".strip()
    retrieval_text = build_retrieval_prompt(context, templates)

    state_json = json.dumps(state or {}, ensure_ascii=False)
    profile_json = json.dumps(profile or {}, ensure_ascii=False)

    messages: list[dict[str, str]] = [{"role": "system", "content": system_text}]
    messages.append(
        {
            "role": "user",
            "content": f"[检索与设定证据]\n{retrieval_text}",
        }
    )
    if history:
        for h in history:
            r = h.get("role", "user")
            c = h.get("content", "")
            if r in ("user", "assistant") and c:
                messages.append({"role": r, "content": c})
    # 画像默认经 assemble_context 注入检索块；仅当显式传入非空 profile 时保留 tail 段（兼容旧调用）
    tail_chunks = [f"[当前会话状态 JSON]\n{state_json}"]
    if profile_bundle_nonempty(profile):
        tail_chunks.append(f"[用户画像/作品覆写 JSON]\n{profile_json}")
    if turn_hints and turn_hints.strip():
        tail_chunks.append(turn_hints.strip())
    tail_chunks.append(f"[玩家本轮输入]\n{user_input.strip()}")
    tail = "\n\n".join(tail_chunks)
    messages.append({"role": "user", "content": tail})
    return messages
