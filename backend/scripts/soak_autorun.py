"""
供 CMD 一键跑 soak：自动注册随机账号（或沿用已设的 SOAK_*）、取第一部就绪作品，
再子进程执行 narrative_llm_roundtrip_soak.py。

在 RAG\\backend 下:
  python scripts\\soak_autorun.py --rounds 10
"""
from __future__ import annotations

import argparse
import os
import random
import subprocess
import sys
from pathlib import Path

import httpx

_BACKEND = Path(__file__).resolve().parent.parent


def _client(base: str) -> httpx.Client:
    # 禁用环境变量代理，避免本机 API 被 HTTP_PROXY 转发后得到 502（浏览器常直连）
    return httpx.Client(
        base_url=base.rstrip("/"),
        timeout=httpx.Timeout(120.0, connect=30.0),
        trust_env=False,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="自动注册/登录后跑 narrative_llm_roundtrip_soak")
    ap.add_argument("--rounds", type=int, default=10)
    ap.add_argument(
        "--base",
        default=os.environ.get("SOAK_API_BASE", "http://127.0.0.1:8000").rstrip("/"),
        help="API 根地址，默认 env SOAK_API_BASE 或 http://127.0.0.1:8000",
    )
    args = ap.parse_args()

    base = args.base
    u = (os.environ.get("SOAK_USERNAME") or "").strip()
    p = (os.environ.get("SOAK_PASSWORD") or "").strip()
    story_raw = (os.environ.get("SOAK_STORY_ID") or "").strip()

    c = _client(base)

    if u and p:
        lr = c.post("/api/auth/login", json={"username": u, "password": p})
        if lr.status_code != 200:
            print(f"login failed: {lr.status_code} {lr.text[:400]}", file=sys.stderr)
            return 1
        tok = lr.json()["access_token"]
        if not story_raw:
            st = c.get("/api/stories", headers={"Authorization": f"Bearer {tok}"}).json()
            if not st:
                print("无就绪作品，请先管理端入库。", file=sys.stderr)
                return 1
            story_raw = str(st[0]["id"])
    else:
        u = f"soak{random.randint(100000, 999999)}"
        p = "SoakTest_9"
        r = c.post(
            "/api/auth/register",
            json={"username": u, "password": p, "display_name": "Soak"},
        )
        if r.status_code not in (201, 409):
            print(f"register {r.status_code}: {r.text[:500]}", file=sys.stderr)
            return 1
        lr = c.post("/api/auth/login", json={"username": u, "password": p})
        if lr.status_code != 200:
            print(f"login after register: {lr.status_code}", file=sys.stderr)
            return 1
        tok = lr.json()["access_token"]
        st = c.get("/api/stories", headers={"Authorization": f"Bearer {tok}"}).json()
        if not st:
            print("无就绪作品，请先管理端入库。", file=sys.stderr)
            return 1
        story_raw = str(st[0]["id"])
        print(f"[soak_autorun] SOAK_USERNAME={u} SOAK_STORY_ID={story_raw}")

    env = {
        **os.environ,
        "SOAK_USERNAME": u,
        "SOAK_PASSWORD": p,
        "SOAK_STORY_ID": story_raw,
        "SOAK_API_BASE": base,
    }
    soak = _BACKEND / "scripts" / "narrative_llm_roundtrip_soak.py"
    return subprocess.run(
        [sys.executable, str(soak), "--rounds", str(args.rounds)],
        env=env,
        cwd=str(_BACKEND),
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
