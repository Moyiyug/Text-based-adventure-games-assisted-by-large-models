"""一次性取证：assistant 行 metadata 为空 / {} 的占比。计划执行后可删或保留供运维。"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

_DB = Path(__file__).resolve().parent.parent.parent / "data" / "app.db"


def _is_empty_meta(raw: str | None) -> bool:
    if raw is None or raw.strip() == "":
        return True
    t = raw.strip()
    if t in ("{}", "null"):
        return True
    try:
        obj = json.loads(t)
    except json.JSONDecodeError:
        return False
    return isinstance(obj, dict) and len(obj) == 0


def main() -> int:
    if not _DB.is_file():
        print(f"no db at {_DB}", file=sys.stderr)
        return 1
    c = sqlite3.connect(str(_DB))
    total = c.execute(
        "SELECT COUNT(*) FROM session_messages WHERE role = 'assistant'"
    ).fetchone()[0]
    rows = c.execute(
        "SELECT id, metadata, created_at FROM session_messages WHERE role = 'assistant'"
    ).fetchall()
    empty = sum(1 for _id, meta, _ca in rows if _is_empty_meta(meta))
    print(f"assistant_messages_total={total}")
    print(f"assistant_empty_metadata_count={empty}")
    if total:
        print(f"assistant_empty_metadata_ratio={empty / total:.4f}")
    # 抽样 id
    sample = [r[0] for r in rows if _is_empty_meta(r[1])][:5]
    if sample:
        print(f"sample_empty_message_ids={sample}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
