"""
多轮真实 LLM 回合测试（经 HTTP API，消耗 DeepSeek token）。

与 RULES.md §5.1 一致：浏览器游玩页须 fetch+ReadableStream；本脚本作为**服务端侧客户端**使用
httpx 对 POST /messages 做 **流式读取响应体**并逐行解析 `data: {...}`，**不使用** EventSource。

前置：
  - 本地已启动 uvicorn（默认 http://127.0.0.1:8000）
  - RAG/.env 已配置 DEEPSEEK_API_KEY 等
  - 库中至少一部 status=ready 的作品

环境变量（必填）：
  SOAK_USERNAME   玩家账号
  SOAK_PASSWORD   密码
  SOAK_STORY_ID   作品 id（整数）

可选：
  SOAK_API_BASE       默认 http://127.0.0.1:8000
  SOAK_HTTP_TIMEOUT   非流式请求读超时秒数（含 POST /opening，要等 LLM），默认 300
  SOAK_OPENING_GOAL   开场目标，默认「多轮 soak 测试冒险」
  SOAK_MODE           strict 或 creative，默认 strict
  SOAK_ROUNDS         回合数（每轮 = 1 次用户输入 + 流式 GM），默认 10

命令行：
  python scripts/narrative_llm_roundtrip_soak.py --rounds 20

用法（在 RAG/backend 下）:
  $env:SOAK_USERNAME='...'; $env:SOAK_PASSWORD='...'; $env:SOAK_STORY_ID='1'
  python scripts/narrative_llm_roundtrip_soak.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

# 脚本可从任意 cwd 执行：把 backend 加入 path 以便与仓库其它脚本一致（本脚本仅 httpx，无 app 导入）
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


def _env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name, "").strip()
    return v if v else default


def _narrative_looks_clean_for_player(content: str) -> tuple[bool, str]:
    """启发式：落库正文不应含明显 JSON/META 泄漏（与产品期望一致）。"""
    c = content.strip()
    if not c:
        return False, "empty narrative"
    if c.startswith("{"):
        return False, "starts with JSON brace"
    if '"choices"' in c or "'choices'" in c:
        return False, 'contains literal "choices" key'
    if '"state_update"' in c:
        return False, 'contains literal "state_update"'
    if "\n---META---\n" in c or c.strip().startswith("---META---"):
        return False, "contains protocol marker in body"
    return True, ""


def _parse_sse_lines(response: httpx.Response) -> list[dict]:
    out: list[dict] = []
    for line in response.iter_lines():
        if not line:
            continue
        if line.startswith("data: "):
            try:
                out.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                continue
    return out


def _stream_turn(
    client: httpx.Client,
    token: str,
    session_id: int,
    user_content: str,
) -> tuple[str, list[str], str | None]:
    """POST /messages，返回 (拼接的 token 叙事片段, choices, 首条 error 文案)。"""
    narrative_parts: list[str] = []
    choices_out: list[str] = []
    err: str | None = None
    with client.stream(
        "POST",
        f"/api/sessions/{session_id}/messages",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"content": user_content},
        timeout=httpx.Timeout(300.0, connect=30.0),
    ) as r:
        r.raise_for_status()
        for payload in _parse_sse_lines(r):
            t = payload.get("type")
            if t == "token":
                narrative_parts.append(str(payload.get("content") or ""))
            elif t == "choices":
                raw = payload.get("choices")
                if isinstance(raw, list):
                    choices_out = [str(x) for x in raw if str(x).strip()]
            elif t == "error" and payload.get("message"):
                err = err or str(payload.get("message"))
    return "".join(narrative_parts), choices_out, err


def main() -> int:
    ap = argparse.ArgumentParser(description="多轮真实 LLM API soak（httpx 流式 SSE）")
    ap.add_argument(
        "--rounds",
        type=int,
        default=int(_env("SOAK_ROUNDS", "10") or "10"),
        help="流式回合数（默认 env SOAK_ROUNDS 或 10）",
    )
    args = ap.parse_args()
    rounds = max(1, min(args.rounds, 50))

    base = (_env("SOAK_API_BASE", "http://127.0.0.1:8000") or "").rstrip("/")
    user = _env("SOAK_USERNAME")
    password = _env("SOAK_PASSWORD")
    story_raw = _env("SOAK_STORY_ID")
    goal = _env("SOAK_OPENING_GOAL", "多轮 soak 测试冒险，请保持每轮有分支。") or ""
    mode = _env("SOAK_MODE", "strict") or "strict"

    if not user or not password or not story_raw:
        print(
            "缺少 SOAK_USERNAME / SOAK_PASSWORD / SOAK_STORY_ID，参见脚本顶部说明。",
            file=sys.stderr,
        )
        return 2
    try:
        story_id = int(story_raw)
    except ValueError:
        print("SOAK_STORY_ID 须为整数", file=sys.stderr)
        return 2
    if mode not in ("strict", "creative"):
        print("SOAK_MODE 须为 strict 或 creative", file=sys.stderr)
        return 2

    try:
        http_timeout = float(_env("SOAK_HTTP_TIMEOUT", "300") or "300")
    except ValueError:
        http_timeout = 300.0
    http_timeout = max(30.0, min(http_timeout, 3600.0))
    # POST /opening 同步等 LLM，不能用 httpx 默认 ~5s 读超时
    client_timeout = httpx.Timeout(http_timeout, connect=30.0)

    with httpx.Client(
        base_url=base,
        follow_redirects=True,
        trust_env=False,  # 本机 API 勿走 HTTP_PROXY，否则常见 502
        timeout=client_timeout,
    ) as client:
        lr = client.post(
            "/api/auth/login",
            json={"username": user, "password": password},
        )
        if lr.status_code != 200:
            print(f"login failed: {lr.status_code} {lr.text[:500]}", file=sys.stderr)
            return 1
        token = lr.json().get("access_token")
        if not token:
            print("login: no access_token", file=sys.stderr)
            return 1
        headers = {"Authorization": f"Bearer {token}"}

        cr = client.post(
            "/api/sessions",
            headers=headers,
            json={
                "story_id": story_id,
                "mode": mode,
                "opening_goal": goal[:8000],
            },
        )
        if cr.status_code != 201:
            print(f"create session failed: {cr.status_code} {cr.text[:800]}", file=sys.stderr)
            return 1
        session_id = cr.json()["id"]

        op = client.post(
            f"/api/sessions/{session_id}/opening",
            headers=headers,
        )
        if op.status_code not in (200, 409):
            print(f"opening failed: {op.status_code} {op.text[:800]}", file=sys.stderr)
            return 1
        if op.status_code == 200:
            body = op.json()
            nar = body.get("narrative") or ""
            ok, reason = _narrative_looks_clean_for_player(nar)
            if not ok:
                print(f"opening narrative heuristic FAIL: {reason}", file=sys.stderr)
                return 1
            ch = body.get("choices") or []
            if len(ch) < 2:
                print(f"opening choices too few: {ch!r}", file=sys.stderr)
                return 1
            print(f"opening ok: choices={len(ch)}, parse_error={body.get('parse_error')!r}")
        else:
            mr0 = client.get(
                f"/api/sessions/{session_id}/messages",
                headers=headers,
            )
            mr0.raise_for_status()
            a0 = next(
                (m for m in reversed(mr0.json()) if m.get("role") == "assistant"),
                None,
            )
            if not a0:
                print("opening 409 but no assistant message", file=sys.stderr)
                return 1
            nar = a0.get("content") or ""
            ok, reason = _narrative_looks_clean_for_player(nar)
            if not ok:
                print(f"opening (409) narrative heuristic FAIL: {reason}", file=sys.stderr)
                return 1
            meta0 = a0.get("metadata") or {}
            ch0 = meta0.get("choices") or []
            if not isinstance(ch0, list) or len([x for x in ch0 if str(x).strip()]) < 2:
                print(f"opening (409) choices too few: {ch0!r}", file=sys.stderr)
                return 1
            print("opening skipped (409): existing assistant ok")

        for i in range(rounds):
            mr = client.get(
                f"/api/sessions/{session_id}/messages",
                headers=headers,
            )
            mr.raise_for_status()
            messages = mr.json()
            last_as: dict | None = None
            for m in reversed(messages):
                if m.get("role") == "assistant":
                    last_as = m
                    break
            if last_as is None:
                print(f"round {i + 1}: no assistant message", file=sys.stderr)
                return 1
            meta = last_as.get("metadata") or {}
            choices_prev = meta.get("choices") or meta.get("options") or []
            if not isinstance(choices_prev, list):
                choices_prev = []
            choices_prev = [str(x).strip() for x in choices_prev if str(x).strip()]
            user_line = (
                choices_prev[0]
                if len(choices_prev) >= 1
                else "继续当前场景，给出一组新的可执行分支。"
            )
            if len(user_line) > 8000:
                user_line = user_line[:8000]

            print(f"round {i + 1}/{rounds}: user -> {user_line[:80]!r}...")
            stream_nar, sse_choices, stream_err = _stream_turn(
                client, token, session_id, user_line
            )
            if stream_err:
                print(f"  sse error: {stream_err[:200]!r}")
            if len(sse_choices) < 2:
                mr2 = client.get(
                    f"/api/sessions/{session_id}/messages",
                    headers=headers,
                )
                mr2.raise_for_status()
                messages2 = mr2.json()
                last2 = next(
                    (m for m in reversed(messages2) if m.get("role") == "assistant"),
                    None,
                )
                db_ch = (
                    (last2 or {}).get("metadata") or {}
                ).get("choices") or []
                if isinstance(db_ch, list) and len([x for x in db_ch if str(x).strip()]) >= 2:
                    print(f"  choices from DB metadata ok (sse empty): {len(db_ch)}")
                else:
                    print(
                        f"round {i + 1}: expected >=2 choices, sse={sse_choices!r} db={db_ch!r}",
                        file=sys.stderr,
                    )
                    return 1
            else:
                print(f"  sse choices: {len(sse_choices)}")

            mr3 = client.get(
                f"/api/sessions/{session_id}/messages",
                headers=headers,
            )
            mr3.raise_for_status()
            last3 = next(
                (m for m in reversed(mr3.json()) if m.get("role") == "assistant"),
                None,
            )
            content = (last3 or {}).get("content") or ""
            ok, reason = _narrative_looks_clean_for_player(content)
            if not ok:
                print(
                    f"round {i + 1}: stored narrative heuristic FAIL: {reason}\n"
                    f"--- excerpt ---\n{content[:400]}...",
                    file=sys.stderr,
                )
                return 1
            if stream_nar and (('"choices"' in stream_nar) or stream_nar.strip().startswith("{")):
                print(
                    f"round {i + 1}: streamed token buffer looks like JSON leak",
                    file=sys.stderr,
                )
                return 1

        print(
            f"narrative_llm_roundtrip_soak: ok ({rounds} round(s), session_id={session_id})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
