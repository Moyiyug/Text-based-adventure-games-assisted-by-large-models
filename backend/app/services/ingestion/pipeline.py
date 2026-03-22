"""入库管线编排。参照 BACKEND_STRUCTURE §4.1、IMPLEMENTATION_PLAN 2.9。"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.content import Chapter, Scene, TextChunk
from app.models.ingestion import IngestionJob, IngestionWarning
from app.models.knowledge import Entity, Relationship, RiskSegment, TimelineEvent
from app.models.story import Story, StoryVersion
from app.services.ingestion.chunker import chunk_text, detect_chapters, detect_scenes
from app.services.ingestion.extractor import (
    extract_entities,
    extract_relationships,
    extract_timeline,
    merge_entities,
)
from app.services.ingestion.indexer import delete_embeddings_for_story_version, embed_and_store_chunks
from app.services.rag.bm25_index import invalidate_bm25_cache
from app.services.ingestion.parser import parse_docx, parse_json, parse_pdf, parse_txt
from app.services.ingestion.safety import detect_risk_segments, rewrite_segment
from app.services.ingestion.summarizer import (
    MIN_SCENE_TEXT_CHARS_FOR_LLM,
    summarize_chapter,
    summarize_scene,
)

logger = logging.getLogger(__name__)


def _parse_by_suffix(path: Path) -> tuple[str, list[str]]:
    suf = path.suffix.lower()
    if suf in (".txt", ".md"):
        return parse_txt(path)
    if suf == ".pdf":
        return parse_pdf(path)
    if suf == ".docx":
        return parse_docx(path)
    if suf == ".json":
        data, w = parse_json(path)
        try:
            text = json.dumps(data, ensure_ascii=False)
        except TypeError:
            text = str(data)
        return text, w
    return "", [f"不支持的文件类型: {suf}"]


async def _append_step(db: AsyncSession, job: IngestionJob, step: str, progress: float) -> None:
    job.progress = progress
    job.steps_completed = [*list(job.steps_completed or []), step]
    await db.flush()


async def _warn(
    db: AsyncSession,
    job_id: int,
    message: str,
    warning_type: str = "parse_error",
) -> None:
    db.add(IngestionWarning(job_id=job_id, warning_type=warning_type, message=message[:2000]))
    await db.flush()


async def prepare_story_version_for_ingest(
    db: AsyncSession,
    story_id: int,
) -> StoryVersion:
    res = await db.execute(
        select(StoryVersion)
        .where(StoryVersion.story_id == story_id)
        .order_by(StoryVersion.version_number.desc())
    )
    versions = list(res.scalars().all())
    if not versions:
        raise ValueError("作品无版本记录")
    active = next((v for v in versions if v.is_active), versions[0])
    cnt = await db.scalar(
        select(func.count()).select_from(Chapter).where(Chapter.story_version_id == active.id)
    )
    if (cnt or 0) == 0:
        delete_embeddings_for_story_version(active.id)
        return active

    for v in versions:
        if v.is_backup:
            v.is_backup = False
            v.is_archived = True
    active.is_active = False
    active.is_backup = True
    max_num = max(v.version_number for v in versions)
    new_v = StoryVersion(
        story_id=story_id,
        version_number=max_num + 1,
        is_active=True,
        is_backup=False,
        is_archived=False,
    )
    db.add(new_v)
    await db.flush()
    return new_v


async def run_ingestion(db: AsyncSession, story_id: int, job_id: int) -> None:
    job = await db.get(IngestionJob, job_id)
    story = await db.get(Story, story_id)
    if not job or not story or story.deleted_at is not None:
        return

    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    await db.flush()

    try:
        story.status = "ingesting"
        await db.flush()

        version = await prepare_story_version_for_ingest(db, story_id)

        if not story.source_file_path:
            raise ValueError("未找到源文件路径")

        full_path = settings.upload_dir_path / story.source_file_path
        if not full_path.is_file():
            raise ValueError(f"源文件不存在: {full_path}")

        raw_text, pw = await asyncio.to_thread(_parse_by_suffix, full_path)
        for w in pw:
            await _warn(db, job_id, w, "parse_error")
        await _append_step(db, job, "parse", 0.12)

        if not raw_text.strip():
            raise ValueError("解析结果为空")

        chapter_blocks = detect_chapters(raw_text)
        await _append_step(db, job, "split_chapters", 0.22)

        chapter_orms: list[Chapter] = []
        chunk_index = 0

        for cb in chapter_blocks:
            ch = Chapter(
                story_version_id=version.id,
                chapter_number=cb.chapter_number,
                title=cb.title,
                raw_text=cb.text,
            )
            db.add(ch)
            await db.flush()
            chapter_orms.append(ch)

            scene_blocks = detect_scenes(cb.text)
            for sb in scene_blocks:
                sc = Scene(
                    chapter_id=ch.id,
                    scene_number=sb.scene_number,
                    raw_text=sb.text,
                )
                db.add(sc)
                await db.flush()
                for piece in chunk_text(sb.text, max_tokens=512, overlap=64):
                    chunk_index += 1
                    tc = TextChunk(
                        story_version_id=version.id,
                        chapter_id=ch.id,
                        scene_id=sc.id,
                        chunk_index=chunk_index,
                        content=piece,
                        token_count=max(1, len(piece) // 2),
                    )
                    db.add(tc)
            await db.flush()

        await _append_step(db, job, "persist_chunks", 0.4)

        name_to_entity: dict[str, Entity] = {}

        for ch in chapter_orms:
            try:
                raw_entities, ew = await extract_entities(ch.raw_text)
                for w in ew:
                    await _warn(db, job_id, w, "entity_conflict")
                merged = merge_entities(
                    [
                        {
                            "name": e["name"],
                            "canonical_name": e["canonical_name"],
                            "entity_type": e["entity_type"],
                            "description": e.get("description"),
                            "aliases": e.get("aliases") or [],
                        }
                        for e in raw_entities
                    ]
                )
                for ed in merged:
                    key = str(ed["canonical_name"]).strip().lower()
                    if not key or key in name_to_entity:
                        continue
                    ent = Entity(
                        story_version_id=version.id,
                        name=str(ed["name"]),
                        canonical_name=str(ed["canonical_name"]),
                        entity_type=str(ed["entity_type"]),
                        description=ed.get("description"),
                        aliases=list(ed.get("aliases") or []),
                    )
                    db.add(ent)
                    await db.flush()
                    name_to_entity[key] = ent
            except RuntimeError as e:
                await _warn(db, job_id, f"实体抽取跳过: {e}", "parse_error")

            try:
                ent_dicts = [
                    {
                        "canonical_name": e.canonical_name,
                        "name": e.name,
                        "entity_type": e.entity_type,
                    }
                    for e in sorted(name_to_entity.values(), key=lambda x: x.id)
                ]
                rels, rw = await extract_relationships(ent_dicts, ch.raw_text)
                for w in rw:
                    await _warn(db, job_id, w, "entity_conflict")
                for r in rels:
                    na = str(r["entity_a_name"]).strip().lower()
                    nb = str(r["entity_b_name"]).strip().lower()
                    ea = name_to_entity.get(na)
                    eb = name_to_entity.get(nb)
                    if not ea or not eb or ea.id == eb.id:
                        continue
                    db.add(
                        Relationship(
                            story_version_id=version.id,
                            entity_a_id=ea.id,
                            entity_b_id=eb.id,
                            relationship_type=str(r["relationship_type"]),
                            description=r.get("description"),
                            confidence=float(r.get("confidence", 1.0)),
                        )
                    )
                await db.flush()
            except RuntimeError as e:
                await _warn(db, job_id, f"关系抽取跳过: {e}", "parse_error")

            try:
                events, tw = await extract_timeline(ch.raw_text)
                for w in tw:
                    await _warn(db, job_id, w, "scene_boundary_uncertain")
                base_order = ch.chapter_number * 1000
                for ie, ev in enumerate(events):
                    pids: list[int] = []
                    for pname in ev.get("participants", []):
                        lk = str(pname).strip().lower()
                        ent = name_to_entity.get(lk)
                        if ent:
                            pids.append(ent.id)
                    db.add(
                        TimelineEvent(
                            story_version_id=version.id,
                            event_description=str(ev["event_description"]),
                            chapter_id=ch.id,
                            scene_id=None,
                            order_index=base_order + ie,
                            participants=pids,
                        )
                    )
                await db.flush()
            except RuntimeError as e:
                await _warn(db, job_id, f"时间线抽取跳过: {e}", "parse_error")

            try:
                ch_sum = await summarize_chapter(ch.raw_text)
                if (ch_sum or "").strip():
                    ch.summary = ch_sum
                else:
                    ch.summary = None
                    await _warn(
                        db,
                        job_id,
                        f"章节 chapter_number={ch.chapter_number} 摘要为空（模型未返回有效内容或套话已丢弃）",
                        "llm_error",
                    )
            except RuntimeError as e:
                # 与抽取步骤一致：写入 IngestionWarning，避免任务显示 completed 却无摘要且无痕迹
                await _warn(db, job_id, f"章节摘要跳过: {e}", "llm_error")
            await db.flush()

        await _append_step(db, job, "extract_summarize", 0.65)

        for ch in chapter_orms:
            sres = await db.execute(select(Scene).where(Scene.chapter_id == ch.id))
            scene_summary_err: str | None = None
            short_nums: list[int] = []
            junk_nums: list[int] = []
            for sc in sres.scalars().all():
                try:
                    if len(sc.raw_text.strip()) < MIN_SCENE_TEXT_CHARS_FOR_LLM:
                        short_nums.append(sc.scene_number)
                        sc.summary = None
                        continue
                    s = await summarize_scene(sc.raw_text)
                    if (s or "").strip():
                        sc.summary = s
                    else:
                        sc.summary = None
                        junk_nums.append(sc.scene_number)
                except RuntimeError as e:
                    if scene_summary_err is None:
                        scene_summary_err = str(e)[:800]
            if short_nums:
                await _warn(
                    db,
                    job_id,
                    f"章节 chapter_number={ch.chapter_number} 下列场景正文过短已跳过摘要: {short_nums}",
                    "llm_error",
                )
            if junk_nums:
                await _warn(
                    db,
                    job_id,
                    f"章节 chapter_number={ch.chapter_number} 下列场景摘要已丢弃（疑似套话）: {junk_nums}",
                    "llm_error",
                )
            if scene_summary_err:
                await _warn(
                    db,
                    job_id,
                    f"章节 chapter_number={ch.chapter_number} 场景摘要 API 失败: {scene_summary_err}",
                    "llm_error",
                )
            await db.flush()

        await _append_step(db, job, "scene_summaries", 0.72)

        for ch in chapter_orms:
            segs, sw = await detect_risk_segments(ch.raw_text)
            for w in sw:
                await _warn(db, job_id, w, "parse_error")
            for seg in segs:
                try:
                    rw, _ = await rewrite_segment(seg["original_text"], seg["risk_level"])
                    db.add(
                        RiskSegment(
                            story_version_id=version.id,
                            chapter_id=ch.id,
                            original_text=seg["original_text"],
                            rewritten_text=rw,
                            risk_level=seg["risk_level"],
                        )
                    )
                except Exception as e:  # noqa: BLE001
                    await _warn(db, job_id, f"敏感段落改写失败: {e}", "parse_error")
            await db.flush()

        await _append_step(db, job, "safety", 0.82)

        await db.flush()
        cres = await db.execute(
            select(TextChunk)
            .where(TextChunk.story_version_id == version.id)
            .order_by(TextChunk.chunk_index)
        )
        chunks_with_ids = list(cres.scalars().all())
        _, iw = await embed_and_store_chunks(db, version.id, chunks_with_ids)
        for w in iw:
            await _warn(db, job_id, w, "parse_error")
        invalidate_bm25_cache(version.id)

        await _append_step(db, job, "index", 1.0)

        job.story_version_id = version.id
        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        story.status = "ready"
        ver_cfg = dict(version.ingestion_config or {})
        ver_cfg["vectors_dirty"] = False
        version.ingestion_config = ver_cfg
        await db.flush()

    except Exception as e:  # noqa: BLE001
        logger.exception("ingestion failed story_id=%s job_id=%s", story_id, job_id)
        job.status = "failed"
        job.error_message = str(e)[:4000]
        job.completed_at = datetime.now(timezone.utc)
        story.status = "failed"
        await db.flush()


async def run_ingestion_background(story_id: int, job_id: int) -> None:
    async with async_session_factory() as db:
        await run_ingestion(db, story_id, job_id)
        await db.commit()
