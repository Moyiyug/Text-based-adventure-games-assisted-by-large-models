"""采样叙事模型「开场等价」请求的完整原始输出，写入 logs/meta_samples/（目录通常已被 .gitignore 排除）。

用途：对照真实输出调整 meta_parse / 提示词；勿在生产环境对敏感会话使用。

在 RAG/backend 下执行（需 .env 中 DEEPSEEK_API_KEY）:

  Windows PowerShell:
    $env:PYTHONPATH="."
    python scripts/sample_narrative_meta_output.py --session-id 1

  仅模板 + 自定义用户句（无作品检索上下文，context 为「无」）:
    python scripts/sample_narrative_meta_output.py --fixture-user-prompt "生成本会话开场" --mode strict

本脚本不打印 API Key；输出文件可能含剧情文本，请勿提交版本库。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.database import async_session_factory  # noqa: E402
from app.models.session import Session as NarrativeSession  # noqa: E402
from app.models.session import SessionState  # noqa: E402
from app.services.llm.deepseek import deepseek_chat  # noqa: E402
from app.services.narrative.engine import OPENING_USER_PROMPT  # noqa: E402
from app.services.narrative.meta_parse import parse_complete_model_output  # noqa: E402
from app.services.narrative.prompts import build_generation_prompt, load_prompt_templates  # noqa: E402
from app.services.profile_loader import load_session_profile_bundle  # noqa: E402
from app.services.rag.context import assemble_context  # noqa: E402
from app.services.rag.dispatcher import dispatch_retrieve  # noqa: E402

_TOKEN_BUDGET = 6000


async def _latest_state_dict(db: AsyncSession, session_id: int) -> dict:
    res = await db.execute(
        select(SessionState)
        .where(SessionState.session_id == session_id)
        .order_by(SessionState.turn_number.desc(), SessionState.id.desc())
        .limit(1)
    )
    row = res.scalar_one_or_none()
    if row is None or row.state is None:
        return {}
    return dict(row.state)


async def _messages_for_session(db: AsyncSession, session_id: int) -> list[dict[str, str]]:
    res = await db.execute(
        select(NarrativeSession).where(NarrativeSession.id == session_id)
    )
    session = res.scalar_one_or_none()
    if session is None:
        raise SystemExit(f"会话不存在: session_id={session_id}")

    templates = await load_prompt_templates(db, session.mode)
    profile_bundle = await load_session_profile_bundle(
        db, session.user_id, session.story_id
    )
    retrieved = await dispatch_retrieve(
        db,
        session.opening_goal or "开场",
        session.story_version_id,
        session.rag_config_id,
    )
    context = assemble_context(
        retrieved,
        mode=session.mode,
        token_budget=_TOKEN_BUDGET,
        profile=profile_bundle,
    )
    state = await _latest_state_dict(db, session.id)
    return build_generation_prompt(
        OPENING_USER_PROMPT,
        context,
        state,
        None,
        mode=session.mode,
        style_config=dict(session.style_config or {}),
        templates=templates,
        history=[],
    )


async def _messages_fixture(user_prompt: str, mode: str) -> list[dict[str, str]]:
    async with async_session_factory() as db:
        templates = await load_prompt_templates(db, mode)
        return build_generation_prompt(
            user_prompt.strip(),
            "（无）",
            {},
            None,
            mode=mode,
            style_config={},
            templates=templates,
            history=None,
        )


async def main_async() -> None:
    parser = argparse.ArgumentParser(description="采样模型原始输出到 logs/meta_samples/")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--session-id", type=int, help="使用与该会话开场相同的 prompt 组装方式")
    group.add_argument(
        "--fixture-user-prompt",
        type=str,
        metavar="TEXT",
        help="仅加载 DB 模板，检索上下文为「无」",
    )
    parser.add_argument(
        "--mode",
        default="strict",
        choices=("strict", "creative"),
        help="与 --fixture-user-prompt 联用时的模式（默认 strict）",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.4,
        help="deepseek_chat temperature（默认 0.4）",
    )
    args = parser.parse_args()

    if args.session_id is not None:
        async with async_session_factory() as db:
            messages = await _messages_for_session(db, args.session_id)
        tag = f"sid{args.session_id}"
    else:
        messages = await _messages_fixture(args.fixture_user_prompt, args.mode)
        tag = "fixture"

    raw = await deepseek_chat(messages, temperature=args.temperature)
    probe = parse_complete_model_output(raw)

    out_dir = Path(__file__).resolve().parent.parent / "logs" / "meta_samples"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"sample_{ts}_{tag}.txt"

    footer = (
        "\n\n----------\n"
        "# parse_complete_model_output 探测（同仓库解析器）\n"
        f"# choices_len={len(probe.choices)} parse_error={probe.parse_error!r}\n"
        f"# narrative_len={len(probe.narrative)}\n"
    )
    out_path.write_text(raw + footer, encoding="utf-8")
    print(f"已写入: {out_path}")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
