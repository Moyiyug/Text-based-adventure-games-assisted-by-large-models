#!/usr/bin/env python3
"""
Phase 4 后端简易验收：健康检查、玩家会话 CRUD、管理端 prompts/sessions、
可选调用开场与流式回合（需 DEEPSEEK_API_KEY 与就绪作品）。

在 RAG/backend 下执行:
  Windows PowerShell:
    $env:PYTHONPATH="."
    python scripts/verify_phase4_backend.py

  跳过耗额度/耗时的 LLM 调用:
    $env:SKIP_LLM="1"
    python scripts/verify_phase4_backend.py

环境变量:
  API_BASE     默认 http://127.0.0.1:8000
  PLAYER_USER / PLAYER_PASS  玩家账号（不存在则尝试注册）
  ADMIN_USER / ADMIN_PASS    管理员（测 /api/admin/*）
  SKIP_LLM     设为 1 则跳过 POST opening 与 POST messages

SSE 手工验收（将 <TOKEN> <SID> 换成实际值；Windows 用 curl.exe）:

  curl.exe -N -X POST ^
    -H "Authorization: Bearer <TOKEN>" ^
    -H "Content-Type: application/json" ^
    -H "Accept: text/event-stream" ^
    -d "{\\"content\\":\\"继续故事\\"}" ^
    http://127.0.0.1:8000/api/sessions/<SID>/messages

子进程起服务再验收（避免本机 8000 被占用）: python scripts/run_verify_with_server.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000").rstrip("/")
PLAYER_USER = os.environ.get("PLAYER_USER", "phase4_player")
PLAYER_PASS = os.environ.get("PLAYER_PASS", "Phase4_test_pass")
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "admin123")
SKIP_LLM = os.environ.get("SKIP_LLM", "").strip() in ("1", "true", "yes", "on")


def _ok(msg: str) -> None:
    print(f"  [OK] {msg}")


def _skip(msg: str) -> None:
    print(f"  [SKIP] {msg}")


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def _section(title: str) -> None:
    print()
    print(f"=== {title} ===")


def main() -> int:
    print(f"API_BASE={BASE}  SKIP_LLM={SKIP_LLM}")
    client = httpx.Client(base_url=BASE, timeout=30.0)

    # --- 健康检查 ---
    _section("健康检查")
    try:
        r = client.get("/api/health")
        r.raise_for_status()
        _ok(f"GET /api/health -> {r.json()}")
    except Exception as e:  # noqa: BLE001
        _fail(f"无法连接后端: {e}")
        print("请先启动: cd RAG/backend && uvicorn app.main:app --reload")
        return 1

    # --- 玩家：注册或登录 ---
    _section("玩家 JWT")
    token_player: str | None = None
    try:
        lr = client.post(
            "/api/auth/login",
            json={"username": PLAYER_USER, "password": PLAYER_PASS},
        )
        if lr.status_code == 200:
            token_player = lr.json()["access_token"]
            _ok(f"登录玩家 {PLAYER_USER}")
        else:
            rr = client.post(
                "/api/auth/register",
                json={
                    "username": PLAYER_USER,
                    "password": PLAYER_PASS,
                    "display_name": "Phase4验收",
                },
            )
            if rr.status_code == 201:
                token_player = client.post(
                    "/api/auth/login",
                    json={"username": PLAYER_USER, "password": PLAYER_PASS},
                ).json()["access_token"]
                _ok(f"注册并登录 {PLAYER_USER}")
            else:
                _fail(f"注册失败 {rr.status_code}: {rr.text[:300]}")
    except Exception as e:  # noqa: BLE001
        _fail(str(e))

    headers_p = {"Authorization": f"Bearer {token_player}"} if token_player else {}

    # --- 就绪作品列表 ---
    _section("玩家会话（需 status=ready 的作品）")
    story_id: int | None = None
    if token_player:
        try:
            sr = client.get("/api/stories", headers=headers_p)
            sr.raise_for_status()
            stories = sr.json()
            if stories:
                story_id = int(stories[0]["id"])
                _ok(f"选用作品 story_id={story_id} ({stories[0].get('title', '')})")
            else:
                _skip("无就绪作品：请在管理端入库一部作品后再跑会话测试")
        except Exception as e:  # noqa: BLE001
            _fail(str(e))

    session_id: int | None = None
    if token_player and story_id:
        try:
            cr = client.post(
                "/api/sessions",
                headers=headers_p,
                json={
                    "story_id": story_id,
                    "mode": "strict",
                    "opening_goal": "验收用：探索开场与一轮对话。",
                },
            )
            cr.raise_for_status()
            session_id = int(cr.json()["id"])
            _ok(f"POST /api/sessions -> session_id={session_id}")

            gr = client.get(f"/api/sessions/{session_id}", headers=headers_p)
            gr.raise_for_status()
            _ok("GET /api/sessions/{id} 含 latest_state")

            mr = client.get(f"/api/sessions/{session_id}/messages", headers=headers_p)
            mr.raise_for_status()
            _ok(f"GET messages 条数={len(mr.json())}")

            st = client.get(f"/api/sessions/{session_id}/state", headers=headers_p)
            st.raise_for_status()
            _ok("GET state")

            ar = client.post(f"/api/sessions/{session_id}/archive", headers=headers_p)
            ar.raise_for_status()
            _ok("POST archive")

            client.delete(f"/api/sessions/{session_id}", headers=headers_p).raise_for_status()
            _ok("DELETE 硬删除")
            session_id = None
        except Exception as e:  # noqa: BLE001
            _fail(str(e))

    # 为 LLM 测试再建一个会话（未归档）
    session_for_llm: int | None = None
    if token_player and story_id and not SKIP_LLM:
        try:
            cr = client.post(
                "/api/sessions",
                headers=headers_p,
                json={
                    "story_id": story_id,
                    "mode": "strict",
                    "opening_goal": "简短开场验收。",
                },
            )
            cr.raise_for_status()
            session_for_llm = int(cr.json()["id"])
            _ok(f"为 LLM 测试新建 session_id={session_for_llm}")
        except Exception as e:  # noqa: BLE001
            _fail(str(e))

    # --- 可选：开场 + 流式回合 ---
    _section("LLM：开场与流式 messages（SKIP_LLM=1 或未建会话则跳过）")
    if SKIP_LLM:
        _skip("SKIP_LLM=1")
    elif not session_for_llm or not token_player:
        _skip("无 session 或 token")
    else:
        try:
            client_long = httpx.Client(base_url=BASE, timeout=180.0)
            or_ = client_long.post(
                f"/api/sessions/{session_for_llm}/opening",
                headers=headers_p,
            )
            if or_.status_code != 200:
                _fail(f"opening {or_.status_code}: {or_.text[:500]}")
            else:
                body = or_.json()
                _ok(f"opening narrative 长度={len(body.get('narrative', ''))} choices={body.get('choices')}")

            # SSE
            with client_long.stream(
                "POST",
                f"/api/sessions/{session_for_llm}/messages",
                headers={**headers_p, "Accept": "text/event-stream"},
                json={"content": "继续：我观察周围。"},
                timeout=180.0,
            ) as resp:
                resp.raise_for_status()
                n_token = 0
                saw_done = False
                for line in resp.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    try:
                        ev = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    t = ev.get("type")
                    if t == "token":
                        n_token += 1
                    if t == "done":
                        saw_done = True
                if saw_done:
                    _ok(f"SSE 收到流结束 (token 事件约 {n_token} 条)")
                else:
                    _fail("未收到 type=done 的 SSE 事件")

            # 清理 LLM 测试会话
            client.delete(f"/api/sessions/{session_for_llm}", headers=headers_p).raise_for_status()
            _ok("已删除 LLM 测试会话")
        except Exception as e:  # noqa: BLE001
            _fail(str(e))

    # --- 管理员 ---
    _section("管理员 /api/admin/prompts + /api/admin/sessions")
    token_admin: str | None = None
    try:
        lr = client.post(
            "/api/auth/login",
            json={"username": ADMIN_USER, "password": ADMIN_PASS},
        )
        if lr.status_code == 200:
            token_admin = lr.json()["access_token"]
            _ok(f"登录管理员 {ADMIN_USER}")
        else:
            _skip(f"管理员登录失败 {lr.status_code}（可运行 scripts/seed_admin.py）")
    except Exception as e:  # noqa: BLE001
        _fail(str(e))

    headers_a = {"Authorization": f"Bearer {token_admin}"} if token_admin else {}
    if token_admin:
        try:
            pr = client.get("/api/admin/prompts", headers=headers_a)
            pr.raise_for_status()
            layers = pr.json().get("layers", [])
            _ok(f"GET /api/admin/prompts layers={len(layers)}")

            ar = client.get("/api/admin/sessions?limit=5", headers=headers_a)
            ar.raise_for_status()
            total = ar.json().get("total", 0)
            _ok(f"GET /api/admin/sessions total={total}")

            if total > 0:
                sid = ar.json()["items"][0]["id"]
                tr = client.get(f"/api/admin/sessions/{sid}/transcript", headers=headers_a)
                tr.raise_for_status()
                _ok(f"GET transcript session_id={sid} messages={len(tr.json().get('messages', []))}")
                fr = client.get(f"/api/admin/sessions/{sid}/feedback", headers=headers_a)
                fr.raise_for_status()
                _ok(f"GET feedback count={len(fr.json().get('items', []))}")
            else:
                _skip("尚无会话，跳过 transcript/feedback")
        except Exception as e:  # noqa: BLE001
            _fail(str(e))

    print()
    print("验收脚本结束。若存在 [FAIL]，请根据提示检查服务、账号、作品与 .env。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
