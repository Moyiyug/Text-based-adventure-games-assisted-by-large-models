"""评测：用例生成、批量执行、会话抽样。参照 IMPLEMENTATION_PLAN Phase 6、BACKEND_STRUCTURE §1.7。"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import database as db_module
from app.core.config import settings
from app.models.content import TextChunk
from app.models.eval import EvalCase, EvalResult, EvalRun
from app.models.session import Session as NarrativeSession
from app.models.session import SessionMessage
from app.models.story import StoryVersion
from app.services.llm.deepseek import deepseek_chat
from app.services.narrative.meta_parse import strip_leaking_meta_suffix
from app.services.rag.base import RetrievalResult
from app.services.rag.context import assemble_context, serialize_retrieval_parts
from app.services.rag.dispatcher import dispatch_retrieve

logger = logging.getLogger(__name__)

# §1.7 case_type 标准五类 + 会话回放（实现约定）
STANDARD_CASE_TYPES = frozenset(
    {
        "fact_qa",
        "timeline_qa",
        "consistency",
        "gm_adjudication",
        "personalization",
    }
)
SESSION_TURN = "session_turn"

# 会话抽样写入 EvalCase.rubric；与 _faithfulness_note_for_case 语义一致。
_RUBRIC_SESSION_STRICT = (
    "会话回放·严谨模式：评价 GM 输出相对本回合注入的原作依据（见【检索上下文摘录】）是否捏造、是否与该依据明显矛盾；"
    "叙事是否自然。若有可点选项，须可被该依据支持。"
)
_RUBRIC_SESSION_CREATIVE = (
    "会话回放·创作模式：评价 GM 输出相对本回合叙事上下文（见【检索上下文摘录】及 evidence 中可能附带的上一段 GM 摘要）是否自洽、是否无中生有；"
    "叙事是否自然。若有可点选项，须与该上下文相符。"
)

_GEN_SYSTEM = """你是 RAG 叙事作品的测试用例设计助手。根据给定作品文本摘录，生成评测题。
只输出一个 JSON 数组（不要 markdown 代码块以外的文字）。数组中每个元素为对象，字段：
- case_type: 必须是 fact_qa | timeline_qa | consistency | gm_adjudication | personalization 之一
- question: 面向模型的具体问题（中文）
- evidence_spans: 字符串数组，每条为原文中可对照的短摘录或章节线索（可空数组）
- rubric: 评委用的简短评分要点（中文）

要求：5～10 道题，覆盖不同类型；问题应能由检索+阅读上下文回答；不要编造摘录中不存在的情节。"""


def _extract_json_array(text: str) -> list[dict[str, Any]] | None:
    t = text.strip()
    if not t:
        return None
    try:
        data = json.loads(t)
        return data if isinstance(data, list) else None
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", t)
    if m:
        try:
            data = json.loads(m.group(1))
            return data if isinstance(data, list) else None
        except json.JSONDecodeError:
            return None
    i = t.find("[")
    j = t.rfind("]")
    if i >= 0 and j > i:
        try:
            data = json.loads(t[i : j + 1])
            return data if isinstance(data, list) else None
        except json.JSONDecodeError:
            return None
    return None


def _extract_json_object(text: str) -> dict[str, Any] | None:
    t = text.strip()
    if not t:
        return None
    try:
        data = json.loads(t)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", t)
    if m:
        try:
            data = json.loads(m.group(1))
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None
    i = t.find("{")
    j = t.rfind("}")
    if i >= 0 and j > i:
        try:
            data = json.loads(t[i : j + 1])
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _serialize_retrieval(retrieved: RetrievalResult) -> tuple[list[Any], list[Any]]:
    ch, st = serialize_retrieval_parts(retrieved)
    return ch, st


def _session_mode_from_evidence(spans: list[Any] | None) -> str | None:
    for span in spans or []:
        if isinstance(span, dict) and span.get("kind") == "session_meta":
            m = span.get("mode")
            if m in ("strict", "creative"):
                return str(m)
    return None


def _play_grounding_context_from_evidence(spans: list[Any] | None) -> str | None:
    for span in spans or []:
        if isinstance(span, dict) and span.get("kind") == "play_grounding_context":
            t = str(span.get("text") or "").strip()
            if t:
                return t
    return None


def _retrieval_snapshot_from_evidence(spans: list[Any] | None) -> dict[str, Any] | None:
    for span in spans or []:
        if not isinstance(span, dict) or span.get("kind") != "retrieval_snapshot":
            continue
        data = span.get("data")
        if isinstance(data, dict):
            return data
    return None


def _session_turn_rubric_with_fallback(
    base_rubric: str | None, *, has_play_snapshot: bool
) -> str:
    base = (base_rubric or "").strip()
    if has_play_snapshot:
        return base or _RUBRIC_SESSION_STRICT
    suffix = (
        "【注意】本用例无当轮 grounding 快照，下列摘录为评测时用玩家输入重跑的检索，"
        "与游玩当轮注入可能不一致，得分仅供参考。"
    )
    return f"{base}\n{suffix}".strip() if base else suffix


def _prior_assistant_excerpt_from_messages(
    messages: list[SessionMessage], turn_number: int
) -> str | None:
    by_turn: dict[int, dict[str, SessionMessage]] = {}
    for m in messages:
        by_turn.setdefault(m.turn_number, {})[m.role] = m
    prev = turn_number - 1
    if prev < 1:
        return None
    bucket = by_turn.get(prev)
    if not bucket:
        return None
    a = bucket.get("assistant")
    if a is None:
        return None
    t = strip_leaking_meta_suffix(a.content or "").strip()
    if not t:
        return None
    max_chars = 2400
    if len(t) > max_chars:
        return t[:max_chars] + "…"
    return t


def _gm_from_session_case(case: EvalCase) -> str:
    for span in case.evidence_spans or []:
        if isinstance(span, dict) and span.get("kind") == "gm_output":
            return str(span.get("text") or "").strip()
    return ""


def _choices_from_eval_case(case: EvalCase) -> list[str] | None:
    """会话抽样等用例在 evidence_spans 中附带 kind=session_choices 的 items。"""
    for span in case.evidence_spans or []:
        if not isinstance(span, dict) or span.get("kind") != "session_choices":
            continue
        raw = span.get("items")
        if not isinstance(raw, list):
            continue
        out = [str(x).strip() for x in raw if str(x).strip()]
        if len(out) >= 2:
            return out[:8]
    return None


async def generate_eval_cases(
    db: AsyncSession,
    story_version_id: int,
) -> list[EvalCase]:
    sv = await db.get(StoryVersion, story_version_id)
    if sv is None:
        raise ValueError("story_version 不存在")

    res = await db.execute(
        select(TextChunk)
        .where(TextChunk.story_version_id == story_version_id)
        .order_by(TextChunk.chunk_index)
        .limit(48)
    )
    chunks = list(res.scalars().all())
    if not chunks:
        raise ValueError("该版本无文本块，请先完成入库")

    corpus_parts: list[str] = []
    for ch in chunks:
        body = (ch.content or "").strip()
        if not body:
            continue
        corpus_parts.append(body[:1500])
    corpus = "\n\n---\n\n".join(corpus_parts)[:24000]

    user_msg = f"作品版本 id={story_version_id}。以下为摘录：\n\n{corpus}"
    raw = await deepseek_chat(
        [{"role": "system", "content": _GEN_SYSTEM}, {"role": "user", "content": user_msg}],
        temperature=0.35,
        timeout=settings.EVAL_GENERATE_TIMEOUT,
    )
    arr = _extract_json_array(raw)
    if not arr:
        raise ValueError("用例生成未返回有效 JSON 数组")

    created: list[EvalCase] = []
    for item in arr:
        if not isinstance(item, dict):
            continue
        ct = str(item.get("case_type") or "").strip()
        if ct not in STANDARD_CASE_TYPES:
            continue
        q = str(item.get("question") or "").strip()
        if not q:
            continue
        spans = item.get("evidence_spans")
        if not isinstance(spans, list):
            spans = []
        spans = [str(x) for x in spans if str(x).strip()][:20]
        rubric = item.get("rubric")
        rubric_s = str(rubric).strip() if rubric is not None else None
        row = EvalCase(
            story_version_id=story_version_id,
            case_type=ct,
            question=q,
            evidence_spans=spans,
            rubric=rubric_s,
        )
        db.add(row)
        created.append(row)

    if not created:
        raise ValueError("未生成任何有效用例（请检查模型输出 case_type）")

    await db.flush()
    return created


async def _answer_from_context(context: str, question: str) -> str:
    sys = (
        "你是阅读理解助手。仅根据提供的「检索上下文」回答问题；"
        "若上下文不足请明确说明无法从材料中得出答案。不要编造材料中不存在的事实。"
    )
    user = f"【检索上下文】\n{context}\n\n【问题】\n{question}"
    return (
        await deepseek_chat(
            [{"role": "system", "content": sys}, {"role": "user", "content": user}],
            temperature=0.25,
            timeout=settings.EVAL_ANSWER_TIMEOUT,
        )
    ).strip()


def _faithfulness_note_for_case(case: EvalCase) -> str:
    if case.case_type != SESSION_TURN:
        return "faithfulness：模型回答是否忠实于【检索上下文摘录】、无捏造。"
    mode = _session_mode_from_evidence(case.evidence_spans)
    if mode == "strict":
        return (
            "faithfulness（会话回放·严谨模式）：GM 输出是否忠实于【检索上下文摘录】所呈现的本回合原作依据；"
            "有无与该依据矛盾或明显编造；勿用未出现在摘录中的全书细节苛求。"
        )
    if mode == "creative":
        return (
            "faithfulness（会话回放·创作模式）：GM 输出是否忠实于【检索上下文摘录】及 evidence 中可能附带的"
            " prior_narrative_hint 所构成的当轮叙事上下文；是否在该上下文内自洽、有无无中生有。"
        )
    return (
        "faithfulness（会话回放）：以【检索上下文摘录】为参照，评 GM 输出是否与之严重矛盾或捏造；"
        "若 rubric 提示无当轮快照，则摘录可能来自评测重检索，请结合该说明判断。"
    )


_JUDGE_SYSTEM = """你是评测评委。根据「faithfulness 说明」「检索上下文摘录」「评分要点 rubric」「证据线索 evidence_spans」「模型回答」及（若有）「本回合可点选项」打分。
只输出一个 JSON 对象，不要 markdown。格式：
{"faithfulness_score":0到1的小数,"story_quality_score":0到1的小数,"choices_grounding_score":0到1的小数或null,"judge_reasoning":"简短中文理由"}
faithfulness 的含义以 user 中【faithfulness 说明】为准，勿改用其他标准。
story_quality：叙事是否连贯、有代入感（问答类也可从清晰度评）。
choices_grounding_score：仅当 user 中【本回合可点选项】为非空列表且至少 2 条时，评 0～1——各选项是否可被【检索上下文摘录】支持、无明显编造或与之矛盾；否则必须为 JSON null（不要用字符串 "null"）。"""


def _parse_grounding_score(obj: dict[str, Any], has_choice_list: bool) -> float | None:
    if not has_choice_list:
        return None
    cg = obj.get("choices_grounding_score")
    if cg is None or (isinstance(cg, str) and cg.lower() in ("null", "none", "")):
        return None
    if isinstance(cg, (int, float)):
        return max(0.0, min(1.0, float(cg)))
    return None


async def _judge(
    *,
    context_excerpt: str,
    case: EvalCase,
    generated_answer: str,
    rubric_override: str | None = None,
) -> tuple[float | None, float | None, float | None, str | None]:
    spans_json = json.dumps(case.evidence_spans or [], ensure_ascii=False)
    rubric = (
        rubric_override
        if rubric_override is not None
        else (case.rubric or "从忠实性与叙事/表达质量两方面评分。")
    )
    ff_note = _faithfulness_note_for_case(case)
    choice_items = _choices_from_eval_case(case)
    has_choices = bool(choice_items and len(choice_items) >= 2)
    if has_choices:
        choices_user = (
            "【本回合可点选项】\n"
            + json.dumps(choice_items, ensure_ascii=False)
            + "\n（须输出 choices_grounding_score，0～1）"
        )
    else:
        choices_user = "【本回合可点选项】\n无（choices_grounding_score 必须为 null）"
    user = (
        f"【faithfulness 说明】\n{ff_note}\n\n"
        f"【检索上下文摘录】\n{context_excerpt[:12000]}\n\n"
        f"【evidence_spans】\n{spans_json}\n\n"
        f"【rubric】\n{rubric}\n\n"
        f"{choices_user}\n\n"
        f"【模型回答】\n{generated_answer}"
    )
    raw = await deepseek_chat(
        [{"role": "system", "content": _JUDGE_SYSTEM}, {"role": "user", "content": user}],
        temperature=0.1,
        timeout=settings.EVAL_JUDGE_TIMEOUT,
    )
    obj = _extract_json_object(raw) or {}
    ff = obj.get("faithfulness_score")
    sq = obj.get("story_quality_score")
    reason = obj.get("judge_reasoning")
    ff_f = float(ff) if isinstance(ff, (int, float)) else None
    sq_f = float(sq) if isinstance(sq, (int, float)) else None
    if ff_f is not None:
        ff_f = max(0.0, min(1.0, ff_f))
    if sq_f is not None:
        sq_f = max(0.0, min(1.0, sq_f))
    cg_f = _parse_grounding_score(obj, has_choices)
    reason_s = str(reason).strip() if reason is not None else None
    return ff_f, sq_f, cg_f, reason_s


async def _evaluate_one_case(
    db: AsyncSession,
    *,
    eval_run_id: int,
    case: EvalCase,
    rag_config_id: int,
    story_version_id: int,
) -> EvalResult:
    query = case.question.strip()
    rubric_override: str | None = None

    if case.case_type == SESSION_TURN:
        gen = _gm_from_session_case(case) or "（未能解析 GM 输出）"
        play_ctx = _play_grounding_context_from_evidence(case.evidence_spans)
        snap = _retrieval_snapshot_from_evidence(case.evidence_spans)
        mode_ev = _session_mode_from_evidence(case.evidence_spans)
        ac_mode = mode_ev if mode_ev in ("strict", "creative") else "strict"
        if play_ctx:
            ctx_excerpt = play_ctx.strip()
            if snap:
                rc_json = list(snap.get("chunks") or [])
                sf_json = list(snap.get("structured") or [])
            else:
                rc_json, sf_json = [], []
            rubric_override = None
        else:
            retrieved = await dispatch_retrieve(db, query, story_version_id, rag_config_id)
            ctx = assemble_context(
                retrieved,
                mode=ac_mode,
                token_budget=settings.EVAL_CONTEXT_TOKEN_BUDGET,
            )
            rc_json, sf_json = _serialize_retrieval(retrieved)
            ctx_excerpt = (
                ctx if ctx.strip() else json.dumps(rc_json, ensure_ascii=False)[:8000]
            )
            rubric_override = _session_turn_rubric_with_fallback(
                case.rubric, has_play_snapshot=False
            )
    else:
        retrieved = await dispatch_retrieve(db, query, story_version_id, rag_config_id)
        ctx = assemble_context(
            retrieved,
            mode="strict",
            token_budget=settings.EVAL_CONTEXT_TOKEN_BUDGET,
        )
        rc_json, sf_json = _serialize_retrieval(retrieved)
        gen = await _answer_from_context(ctx, case.question)
        ctx_excerpt = ctx if ctx.strip() else json.dumps(rc_json, ensure_ascii=False)[:8000]

    ff, sq, cg, jr = await _judge(
        context_excerpt=ctx_excerpt,
        case=case,
        generated_answer=gen,
        rubric_override=rubric_override if case.case_type == SESSION_TURN else None,
    )

    return EvalResult(
        eval_run_id=eval_run_id,
        eval_case_id=case.id,
        generated_answer=gen,
        retrieved_context=rc_json,
        structured_facts_used=sf_json,
        faithfulness_score=ff,
        story_quality_score=sq,
        choices_grounding_score=cg,
        judge_reasoning=jr,
    )


async def _finalize_run_averages(db: AsyncSession, run_id: int) -> None:
    run = await db.get(EvalRun, run_id)
    if run is None:
        return
    res = await db.execute(
        select(
            func.avg(EvalResult.faithfulness_score),
            func.avg(EvalResult.story_quality_score),
            func.avg(EvalResult.choices_grounding_score),
            func.count(EvalResult.id),
        ).where(EvalResult.eval_run_id == run_id)
    )
    row = res.one()
    avg_ff, avg_sq, avg_cg, cnt = row[0], row[1], row[2], row[3]
    run.avg_faithfulness = float(avg_ff) if avg_ff is not None else None
    run.avg_story_quality = float(avg_sq) if avg_sq is not None else None
    run.avg_choices_grounding = float(avg_cg) if avg_cg is not None else None
    run.total_cases = int(cnt or 0)


async def run_evaluation_job(run_id: int, case_ids: list[int] | None) -> None:
    """独立 DB 会话；逐条写入 EvalResult，失败则标记 run failed。"""
    try:
        async with db_module.async_session_factory() as db:
            run = await db.get(EvalRun, run_id)
            if run is None:
                logger.warning("run_evaluation_job: run %s 不存在", run_id)
                return

            now = datetime.now(timezone.utc)
            run.status = "running"
            run.started_at = now
            run.error_message = None
            await db.commit()

            if case_ids is not None:
                if not case_ids:
                    cases = []
                else:
                    cres = await db.execute(
                        select(EvalCase).where(
                            EvalCase.id.in_(case_ids),
                            EvalCase.story_version_id == run.story_version_id,
                        )
                    )
                    cases = list(cres.scalars().all())
            else:
                cres = await db.execute(
                    select(EvalCase)
                    .where(EvalCase.story_version_id == run.story_version_id)
                    .order_by(EvalCase.id)
                )
                cases = list(cres.scalars().all())
            cap = max(1, settings.EVAL_MAX_CASES_PER_RUN)
            cases = cases[:cap]

            run = await db.get(EvalRun, run_id)
            if run is None:
                return
            run.total_cases = len(cases)
            await db.commit()

            if not cases:
                run = await db.get(EvalRun, run_id)
                if run:
                    run.status = "completed"
                    run.completed_at = datetime.now(timezone.utc)
                    await db.commit()
                return

            for case in cases:
                try:
                    er = await _evaluate_one_case(
                        db,
                        eval_run_id=run_id,
                        case=case,
                        rag_config_id=run.rag_config_id,
                        story_version_id=run.story_version_id,
                    )
                    db.add(er)
                    await db.commit()
                except Exception as e:  # noqa: BLE001
                    logger.exception("eval case %s failed", case.id)
                    run = await db.get(EvalRun, run_id)
                    if run:
                        run.status = "failed"
                        run.error_message = str(e)[:2000]
                        run.completed_at = datetime.now(timezone.utc)
                        await db.commit()
                    return

            run = await db.get(EvalRun, run_id)
            if run:
                await _finalize_run_averages(db, run_id)
                run.status = "completed"
                run.completed_at = datetime.now(timezone.utc)
                await db.commit()
    except Exception as e:  # noqa: BLE001
        logger.exception("run_evaluation_job run_id=%s", run_id)
        try:
            async with db_module.async_session_factory() as db2:
                run = await db2.get(EvalRun, run_id)
                if run and run.status == "running":
                    run.status = "failed"
                    run.error_message = str(e)[:2000]
                    run.completed_at = datetime.now(timezone.utc)
                    await db2.commit()
        except Exception:  # noqa: BLE001
            logger.exception("run_evaluation_job failed to persist error run_id=%s", run_id)


def _collect_user_assistant_pairs(
    messages: list[SessionMessage],
) -> list[tuple[int, str, str, dict[str, Any]]]:
    """按 turn_number 聚合；仅保留同时含 user 与 assistant 的回合；附带 assistant 的 metadata（用于选项列表）。"""
    by_turn: dict[int, dict[str, SessionMessage]] = {}
    for m in messages:
        by_turn.setdefault(m.turn_number, {})[m.role] = m
    pairs: list[tuple[int, str, str, dict[str, Any]]] = []
    for tn in sorted(by_turn.keys()):
        bucket = by_turn[tn]
        u = bucket.get("user")
        a = bucket.get("assistant")
        if u is None or a is None:
            continue
        meta_d: dict[str, Any] = {}
        raw_m = a.metadata_
        if isinstance(raw_m, dict):
            meta_d = raw_m
        pairs.append(
            (
                tn,
                (u.content or "").strip(),
                strip_leaking_meta_suffix(a.content or ""),
                meta_d,
            )
        )
    return pairs


async def create_sample_session_eval_run(
    db: AsyncSession,
    session_id: int,
    max_turns: int,
) -> tuple[int, list[int]]:
    """
    创建 EvalRun + session_turn 用例并返回 (run_id, case_ids)。
    关键轮次：每隔一轮取样（pairs[::2]），最多 max_turns 条，优先较新的回合。
    """
    sess = await db.get(NarrativeSession, session_id)
    if sess is None:
        raise ValueError("会话不存在")

    mres = await db.execute(
        select(SessionMessage)
        .where(SessionMessage.session_id == session_id)
        .order_by(SessionMessage.id.asc())
    )
    messages = list(mres.scalars().all())
    pairs = _collect_user_assistant_pairs(messages)
    stepped = pairs[::2]
    cap = max(1, min(max_turns, settings.EVAL_MAX_CASES_PER_RUN))
    selected = stepped[-cap:] if len(stepped) > cap else stepped

    if not selected:
        raise ValueError("会话中无同时含玩家与 GM 的完整回合，无法抽样评测")

    case_ids: list[int] = []
    for tn, user_txt, gm_txt, asst_meta in selected:
        if not user_txt:
            continue
        mode_s = (sess.mode or "strict").strip()
        if mode_s == "creative":
            rubric_s = _RUBRIC_SESSION_CREATIVE
        else:
            rubric_s = _RUBRIC_SESSION_STRICT
            mode_s = "strict"

        spans: list[Any] = [{"kind": "session_meta", "mode": mode_s}]
        egc = asst_meta.get("eval_grounding_context")
        if isinstance(egc, str) and egc.strip():
            cap = settings.EVAL_SNAPSHOT_CONTEXT_MAX_CHARS
            spans.append({"kind": "play_grounding_context", "text": egc.strip()[:cap]})
        ers = asst_meta.get("eval_retrieval_snapshot")
        if isinstance(ers, dict) and ers:
            spans.append({"kind": "retrieval_snapshot", "data": ers})
        spans.append({"kind": "gm_output", "text": gm_txt})
        chs = asst_meta.get("choices")
        if isinstance(chs, list):
            items = [str(c).strip() for c in chs if str(c).strip()]
            if len(items) >= 2:
                spans.append({"kind": "session_choices", "items": items[:8]})
        if mode_s == "creative":
            prior = _prior_assistant_excerpt_from_messages(messages, tn)
            if prior:
                spans.append({"kind": "prior_narrative_hint", "text": prior})
        row = EvalCase(
            story_version_id=sess.story_version_id,
            case_type=SESSION_TURN,
            question=user_txt,
            evidence_spans=spans,
            rubric=rubric_s,
        )
        db.add(row)
        await db.flush()
        case_ids.append(row.id)

    if not case_ids:
        raise ValueError("未能构建任何评测用例")

    run = EvalRun(
        rag_config_id=sess.rag_config_id,
        story_version_id=sess.story_version_id,
        status="pending",
        total_cases=len(case_ids),
    )
    db.add(run)
    await db.flush()
    rid = run.id
    await db.commit()
    return rid, case_ids
