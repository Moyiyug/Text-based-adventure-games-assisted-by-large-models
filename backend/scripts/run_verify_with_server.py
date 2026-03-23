"""子进程启动 uvicorn 后运行 verify_phase4_backend（避免本机 8000/8020 代理 502）。"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

BACKEND = Path(__file__).resolve().parent.parent
PORT = int(os.environ.get("VERIFY_PORT", "18099"))


def main() -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(BACKEND)
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        f"--port",
        str(PORT),
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=str(BACKEND),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    try:
        base = f"http://127.0.0.1:{PORT}"
        for _ in range(40):
            time.sleep(0.25)
            try:
                r = httpx.get(f"{base}/api/health", timeout=2.0)
                if r.status_code == 200:
                    break
            except httpx.RequestError:
                continue
        else:
            err = proc.stderr.read(4000).decode("utf-8", errors="replace") if proc.stderr else ""
            print("uvicorn 未在时限内就绪。", err)
            return 1

        os.environ["API_BASE"] = base
        # 继承 SKIP_LLM 等
        verify = BACKEND / "scripts" / "verify_phase4_backend.py"
        return subprocess.call([sys.executable, str(verify)], cwd=str(BACKEND), env=os.environ)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
