"""只读快照：入库结果统计（验收用）。不修改数据库。"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

# 相对于 backend/ 目录
DB = Path(__file__).resolve().parent.parent.parent / "data" / "app.db"


def main() -> None:
    if not DB.is_file():
        print(f"DB not found: {DB}", file=sys.stderr)
        sys.exit(1)

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    c = con.cursor()

    print("=== stories ===")
    for r in c.execute(
        "SELECT id, title, status, source_file_path, "
        "CASE WHEN deleted_at IS NULL THEN 0 ELSE 1 END AS deleted "
        "FROM stories ORDER BY id"
    ):
        print(dict(r))

    print("\n=== story_versions ===")
    for r in c.execute(
        "SELECT id, story_id, version_number, is_active, is_backup, is_archived, "
        "ingestion_config FROM story_versions ORDER BY story_id, version_number"
    ):
        row = dict(r)
        cfg = row.pop("ingestion_config", None)
        if cfg:
            try:
                row["ingestion_config"] = json.loads(cfg) if isinstance(cfg, str) else cfg
            except json.JSONDecodeError:
                row["ingestion_config"] = cfg[:80] if isinstance(cfg, str) else cfg
        print(row)

    print("\n=== ingestion_jobs (latest 5) ===")
    for r in c.execute(
        "SELECT id, story_id, story_version_id, status, progress, error_message, "
        "steps_completed, created_at FROM ingestion_jobs ORDER BY id DESC LIMIT 5"
    ):
        row = dict(r)
        sc = row.get("steps_completed")
        if isinstance(sc, str):
            try:
                row["steps_completed"] = json.loads(sc)
            except json.JSONDecodeError:
                pass
        print(row)

    print("\n=== counts (active story_version only) ===")
    for r in c.execute(
        """
        SELECT sv.id AS vid, sv.story_id,
          (SELECT COUNT(*) FROM chapters ch WHERE ch.story_version_id = sv.id) AS chapters,
          (SELECT COUNT(*) FROM scenes sc JOIN chapters ch ON sc.chapter_id = ch.id
             WHERE ch.story_version_id = sv.id) AS scenes,
          (SELECT COUNT(*) FROM text_chunks tc WHERE tc.story_version_id = sv.id) AS chunks,
          (SELECT COUNT(*) FROM entities e WHERE e.story_version_id = sv.id) AS entities,
          (SELECT COUNT(*) FROM relationships r WHERE r.story_version_id = sv.id) AS rels,
          (SELECT COUNT(*) FROM timeline_events t WHERE t.story_version_id = sv.id) AS timeline,
          (SELECT COUNT(*) FROM risk_segments rs WHERE rs.story_version_id = sv.id) AS risks
        FROM story_versions sv
        WHERE sv.is_active = 1
        ORDER BY sv.story_id
        """
    ):
        print(dict(r))

    print("\n=== sample chapters (first 3 of active version) ===")
    for r in c.execute(
        """
        SELECT ch.id, ch.chapter_number, ch.title,
               LENGTH(ch.raw_text) AS raw_len,
               LENGTH(COALESCE(ch.summary, '')) AS sum_len
        FROM chapters ch
        JOIN story_versions sv ON sv.id = ch.story_version_id AND sv.is_active = 1
        ORDER BY ch.story_version_id, ch.chapter_number
        LIMIT 3
        """
    ):
        print(dict(r))

    print("\n=== ingestion_warnings (latest job, up to 20) ===")
    row = c.execute("SELECT id FROM ingestion_jobs ORDER BY id DESC LIMIT 1").fetchone()
    if row:
        jid = row[0]
        w = c.execute(
            "SELECT warning_type, message FROM ingestion_warnings WHERE job_id = ? ORDER BY id LIMIT 20",
            (jid,),
        ).fetchall()
        if not w:
            print("(none)")
        for t in w:
            print(dict(t))
    else:
        print("(no jobs)")

    con.close()


if __name__ == "__main__":
    main()
