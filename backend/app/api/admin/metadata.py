"""管理员元数据 CRUD。路径前缀在 main 中挂载为 /api/admin/stories。"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.models.content import Chapter, Scene, TextChunk
from app.models.knowledge import Entity, Relationship, RiskSegment, TimelineEvent
from app.models.story import Story, StoryVersion
from app.models.user import User
from app.services.ingestion.chunker import chunk_text
from app.services.ingestion.indexer import delete_embeddings_for_text_chunk_ids, embed_and_store_chunks
from app.schemas.metadata import (
    ChapterUpdate,
    EntityCreate,
    EntityUpdate,
    RelationshipCreate,
    RelationshipUpdate,
    RiskSegmentUpdate,
    SceneUpdate,
    TimelineCreate,
    TimelineUpdate,
)

router = APIRouter()


def _mark_vectors_dirty(version: StoryVersion) -> None:
    cfg = dict(version.ingestion_config or {})
    cfg["vectors_dirty"] = True
    version.ingestion_config = cfg


async def _get_story_and_active_version(
    db: AsyncSession, story_id: int
) -> tuple[Story, StoryVersion]:
    story = await db.get(Story, story_id)
    if story is None or story.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作品不存在")
    if story.status == "ingesting":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="入库进行中，暂不可编辑元数据",
        )
    res = await db.execute(
        select(StoryVersion).where(
            StoryVersion.story_id == story_id,
            StoryVersion.is_active.is_(True),
        )
    )
    av = res.scalar_one_or_none()
    if av is None:
        raise HTTPException(status_code=400, detail="无当前生效版本")
    return story, av


async def _chapter_belongs_to_version(db: AsyncSession, chapter_id: int, version_id: int) -> Chapter | None:
    ch = await db.get(Chapter, chapter_id)
    if ch is None or ch.story_version_id != version_id:
        return None
    return ch


async def _scene_belongs_to_version(db: AsyncSession, scene_id: int, version_id: int) -> Scene | None:
    sc = await db.get(Scene, scene_id)
    if sc is None:
        return None
    ch = await db.get(Chapter, sc.chapter_id)
    if ch is None or ch.story_version_id != version_id:
        return None
    return sc


async def _delete_chunks_for_scene(db: AsyncSession, scene_id: int) -> None:
    res = await db.execute(select(TextChunk.id).where(TextChunk.scene_id == scene_id))
    ids = [row[0] for row in res.all()]
    delete_embeddings_for_text_chunk_ids(ids)
    await db.execute(delete(TextChunk).where(TextChunk.scene_id == scene_id))
    await db.flush()


async def _renumber_scenes_in_chapter(db: AsyncSession, chapter_id: int) -> None:
    res = await db.execute(select(Scene).where(Scene.chapter_id == chapter_id).order_by(Scene.scene_number))
    scenes = list(res.scalars().all())
    for i, s in enumerate(scenes, start=1):
        s.scene_number = i
    await db.flush()


# --- entities ---


@router.get("/{story_id}/metadata/entities")
async def list_entities(
    story_id: int,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    _, av = await _get_story_and_active_version(db, story_id)
    res = await db.execute(select(Entity).where(Entity.story_version_id == av.id))
    rows = list(res.scalars().all())
    return [
        {
            "id": e.id,
            "story_version_id": e.story_version_id,
            "name": e.name,
            "canonical_name": e.canonical_name,
            "entity_type": e.entity_type,
            "description": e.description,
            "aliases": list(e.aliases or []),
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in rows
    ]


@router.post("/{story_id}/metadata/entities", status_code=status.HTTP_201_CREATED)
async def create_entity(
    story_id: int,
    body: EntityCreate,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    _, av = await _get_story_and_active_version(db, story_id)
    ent = Entity(
        story_version_id=av.id,
        name=body.name.strip(),
        canonical_name=body.canonical_name.strip(),
        entity_type=body.entity_type.strip(),
        description=body.description,
        aliases=list(body.aliases or []),
    )
    db.add(ent)
    _mark_vectors_dirty(av)
    await db.flush()
    await db.refresh(ent)
    return {"id": ent.id}


@router.put("/{story_id}/metadata/entities/{entity_id}")
async def update_entity(
    story_id: int,
    entity_id: int,
    body: EntityUpdate,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    _, av = await _get_story_and_active_version(db, story_id)
    ent = await db.get(Entity, entity_id)
    if ent is None or ent.story_version_id != av.id:
        raise HTTPException(status_code=404, detail="实体不存在")
    if body.name is not None:
        ent.name = body.name.strip()
    if body.canonical_name is not None:
        ent.canonical_name = body.canonical_name.strip()
    if body.entity_type is not None:
        ent.entity_type = body.entity_type.strip()
    if body.description is not None:
        ent.description = body.description
    if body.aliases is not None:
        ent.aliases = list(body.aliases)
    _mark_vectors_dirty(av)
    await db.flush()
    return {"ok": True}


@router.delete("/{story_id}/metadata/entities/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entity(
    story_id: int,
    entity_id: int,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    _, av = await _get_story_and_active_version(db, story_id)
    ent = await db.get(Entity, entity_id)
    if ent is None or ent.story_version_id != av.id:
        raise HTTPException(status_code=404, detail="实体不存在")
    await db.delete(ent)
    _mark_vectors_dirty(av)
    await db.flush()


# --- relationships ---


@router.get("/{story_id}/metadata/relationships")
async def list_relationships(
    story_id: int,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    _, av = await _get_story_and_active_version(db, story_id)
    res = await db.execute(select(Relationship).where(Relationship.story_version_id == av.id))
    rows = list(res.scalars().all())
    return [
        {
            "id": r.id,
            "story_version_id": r.story_version_id,
            "entity_a_id": r.entity_a_id,
            "entity_b_id": r.entity_b_id,
            "relationship_type": r.relationship_type,
            "description": r.description,
            "confidence": r.confidence,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.post("/{story_id}/metadata/relationships", status_code=status.HTTP_201_CREATED)
async def create_relationship(
    story_id: int,
    body: RelationshipCreate,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    _, av = await _get_story_and_active_version(db, story_id)
    ea = await db.get(Entity, body.entity_a_id)
    eb = await db.get(Entity, body.entity_b_id)
    if (
        ea is None
        or eb is None
        or ea.story_version_id != av.id
        or eb.story_version_id != av.id
    ):
        raise HTTPException(status_code=400, detail="实体不属于当前版本")
    rel = Relationship(
        story_version_id=av.id,
        entity_a_id=body.entity_a_id,
        entity_b_id=body.entity_b_id,
        relationship_type=body.relationship_type.strip(),
        description=body.description,
        confidence=body.confidence,
    )
    db.add(rel)
    _mark_vectors_dirty(av)
    await db.flush()
    await db.refresh(rel)
    return {"id": rel.id}


@router.put("/{story_id}/metadata/relationships/{rel_id}")
async def update_relationship(
    story_id: int,
    rel_id: int,
    body: RelationshipUpdate,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    _, av = await _get_story_and_active_version(db, story_id)
    rel = await db.get(Relationship, rel_id)
    if rel is None or rel.story_version_id != av.id:
        raise HTTPException(status_code=404, detail="关系不存在")
    if body.relationship_type is not None:
        rel.relationship_type = body.relationship_type.strip()
    if body.description is not None:
        rel.description = body.description
    if body.confidence is not None:
        rel.confidence = body.confidence
    _mark_vectors_dirty(av)
    await db.flush()
    return {"ok": True}


@router.delete("/{story_id}/metadata/relationships/{rel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_relationship(
    story_id: int,
    rel_id: int,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    _, av = await _get_story_and_active_version(db, story_id)
    rel = await db.get(Relationship, rel_id)
    if rel is None or rel.story_version_id != av.id:
        raise HTTPException(status_code=404, detail="关系不存在")
    await db.delete(rel)
    _mark_vectors_dirty(av)
    await db.flush()


# --- timeline ---


@router.get("/{story_id}/metadata/timeline")
async def list_timeline(
    story_id: int,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    _, av = await _get_story_and_active_version(db, story_id)
    res = await db.execute(
        select(TimelineEvent)
        .where(TimelineEvent.story_version_id == av.id)
        .order_by(TimelineEvent.order_index)
    )
    rows = list(res.scalars().all())
    return [
        {
            "id": ev.id,
            "story_version_id": ev.story_version_id,
            "event_description": ev.event_description,
            "chapter_id": ev.chapter_id,
            "scene_id": ev.scene_id,
            "order_index": ev.order_index,
            "participants": list(ev.participants or []),
            "created_at": ev.created_at.isoformat() if ev.created_at else None,
        }
        for ev in rows
    ]


@router.post("/{story_id}/metadata/timeline", status_code=status.HTTP_201_CREATED)
async def create_timeline_event(
    story_id: int,
    body: TimelineCreate,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    _, av = await _get_story_and_active_version(db, story_id)
    ch_id = body.chapter_id
    sc_id = body.scene_id
    if ch_id is not None:
        if await _chapter_belongs_to_version(db, ch_id, av.id) is None:
            raise HTTPException(status_code=400, detail="章节不属于当前版本")
    if sc_id is not None:
        if await _scene_belongs_to_version(db, sc_id, av.id) is None:
            raise HTTPException(status_code=400, detail="场景不属于当前版本")
    for pid in body.participants:
        ent = await db.get(Entity, pid)
        if ent is None or ent.story_version_id != av.id:
            raise HTTPException(status_code=400, detail=f"参与实体 id={pid} 无效")
    ev = TimelineEvent(
        story_version_id=av.id,
        event_description=body.event_description.strip(),
        chapter_id=ch_id,
        scene_id=sc_id,
        order_index=body.order_index,
        participants=list(body.participants),
    )
    db.add(ev)
    _mark_vectors_dirty(av)
    await db.flush()
    await db.refresh(ev)
    return {"id": ev.id}


@router.put("/{story_id}/metadata/timeline/{event_id}")
async def update_timeline_event(
    story_id: int,
    event_id: int,
    body: TimelineUpdate,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    _, av = await _get_story_and_active_version(db, story_id)
    ev = await db.get(TimelineEvent, event_id)
    if ev is None or ev.story_version_id != av.id:
        raise HTTPException(status_code=404, detail="时间线事件不存在")
    data = body.model_dump(exclude_unset=True)
    if "event_description" in data and data["event_description"] is not None:
        ev.event_description = str(data["event_description"]).strip()
    if "chapter_id" in data:
        cid = data["chapter_id"]
        if cid is not None and await _chapter_belongs_to_version(db, cid, av.id) is None:
            raise HTTPException(status_code=400, detail="章节不属于当前版本")
        ev.chapter_id = cid
    if "scene_id" in data:
        sid = data["scene_id"]
        if sid is not None and await _scene_belongs_to_version(db, sid, av.id) is None:
            raise HTTPException(status_code=400, detail="场景不属于当前版本")
        ev.scene_id = sid
    if "order_index" in data and data["order_index"] is not None:
        ev.order_index = data["order_index"]
    if "participants" in data and data["participants"] is not None:
        for pid in data["participants"]:
            ent = await db.get(Entity, pid)
            if ent is None or ent.story_version_id != av.id:
                raise HTTPException(status_code=400, detail=f"参与实体 id={pid} 无效")
        ev.participants = list(data["participants"])
    _mark_vectors_dirty(av)
    await db.flush()
    return {"ok": True}


@router.delete("/{story_id}/metadata/timeline/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_timeline_event(
    story_id: int,
    event_id: int,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    _, av = await _get_story_and_active_version(db, story_id)
    ev = await db.get(TimelineEvent, event_id)
    if ev is None or ev.story_version_id != av.id:
        raise HTTPException(status_code=404, detail="时间线事件不存在")
    await db.delete(ev)
    _mark_vectors_dirty(av)
    await db.flush()


# --- chapters & scenes ---


@router.get("/{story_id}/metadata/chapters")
async def list_chapters_and_scenes(
    story_id: int,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    _, av = await _get_story_and_active_version(db, story_id)
    cres = await db.execute(
        select(Chapter).where(Chapter.story_version_id == av.id).order_by(Chapter.chapter_number)
    )
    chapters = list(cres.scalars().all())
    out: list[dict] = []
    for ch in chapters:
        sres = await db.execute(select(Scene).where(Scene.chapter_id == ch.id).order_by(Scene.scene_number))
        scenes = list(sres.scalars().all())
        out.append(
            {
                "id": ch.id,
                "chapter_number": ch.chapter_number,
                "title": ch.title,
                "summary": ch.summary,
                "raw_text_preview": (ch.raw_text[:200] + "…") if len(ch.raw_text) > 200 else ch.raw_text,
                "scenes": [
                    {
                        "id": sc.id,
                        "scene_number": sc.scene_number,
                        "summary": sc.summary,
                        "raw_text_preview": (sc.raw_text[:200] + "…")
                        if len(sc.raw_text) > 200
                        else sc.raw_text,
                    }
                    for sc in scenes
                ],
            }
        )
    return out


@router.get("/{story_id}/metadata/scenes/{scene_id}")
async def get_scene_detail(
    story_id: int,
    scene_id: int,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    _, av = await _get_story_and_active_version(db, story_id)
    sc = await _scene_belongs_to_version(db, scene_id, av.id)
    if sc is None:
        raise HTTPException(status_code=404, detail="场景不存在")
    return {
        "id": sc.id,
        "chapter_id": sc.chapter_id,
        "scene_number": sc.scene_number,
        "raw_text": sc.raw_text,
        "summary": sc.summary,
    }


@router.put("/{story_id}/metadata/chapters/{chapter_id}")
async def update_chapter(
    story_id: int,
    chapter_id: int,
    body: ChapterUpdate,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    _, av = await _get_story_and_active_version(db, story_id)
    ch = await _chapter_belongs_to_version(db, chapter_id, av.id)
    if ch is None:
        raise HTTPException(status_code=404, detail="章节不存在")
    if body.title is not None:
        ch.title = body.title.strip() if body.title else None
    if body.summary is not None:
        ch.summary = body.summary
    _mark_vectors_dirty(av)
    await db.flush()
    return {"ok": True}


@router.put("/{story_id}/metadata/scenes/{scene_id}")
async def update_scene(
    story_id: int,
    scene_id: int,
    body: SceneUpdate,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    _, av = await _get_story_and_active_version(db, story_id)
    sc = await _scene_belongs_to_version(db, scene_id, av.id)
    if sc is None:
        raise HTTPException(status_code=404, detail="场景不存在")
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        return {"ok": True, "warnings": []}

    ch = await db.get(Chapter, sc.chapter_id)
    if ch is None:
        raise HTTPException(status_code=404, detail="章节不存在")
    sv_id = ch.story_version_id
    warnings: list[str] = []

    if "raw_text" in patch:
        raw = patch["raw_text"]
        if raw is None:
            raise HTTPException(status_code=400, detail="raw_text 不可为 null")
        text = str(raw).strip()
        if not text:
            raise HTTPException(status_code=400, detail="raw_text 不能为空")
        await _delete_chunks_for_scene(db, scene_id)
        sc.raw_text = text
        pieces = chunk_text(text, max_tokens=512, overlap=64)
        if not pieces:
            pieces = [text]
        mx = await db.scalar(
            select(func.max(TextChunk.chunk_index)).where(TextChunk.story_version_id == sv_id)
        )
        mx = int(mx or 0)
        new_rows: list[TextChunk] = []
        for piece in pieces:
            mx += 1
            tc = TextChunk(
                story_version_id=sv_id,
                chapter_id=sc.chapter_id,
                scene_id=sc.id,
                chunk_index=mx,
                content=piece,
                token_count=max(1, len(piece) // 2),
            )
            db.add(tc)
            new_rows.append(tc)
        await db.flush()
        _, emb_w = await embed_and_store_chunks(db, sv_id, new_rows)
        warnings.extend(emb_w)

    if "summary" in patch:
        s = patch["summary"]
        if s is None or (isinstance(s, str) and not str(s).strip()):
            sc.summary = None
        else:
            sc.summary = str(s).strip()

    _mark_vectors_dirty(av)
    await db.flush()
    return {"ok": True, "warnings": warnings}


@router.delete("/{story_id}/metadata/scenes/{scene_id}", status_code=status.HTTP_200_OK)
async def delete_scene(
    story_id: int,
    scene_id: int,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    _, av = await _get_story_and_active_version(db, story_id)
    sc = await _scene_belongs_to_version(db, scene_id, av.id)
    if sc is None:
        raise HTTPException(status_code=404, detail="场景不存在")
    chapter_id = sc.chapter_id
    await _delete_chunks_for_scene(db, scene_id)
    await db.delete(sc)
    await db.flush()
    await _renumber_scenes_in_chapter(db, chapter_id)
    _mark_vectors_dirty(av)
    await db.flush()
    return {"ok": True}


# --- risk segments ---


@router.get("/{story_id}/metadata/risk-segments")
async def list_risk_segments(
    story_id: int,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    _, av = await _get_story_and_active_version(db, story_id)
    res = await db.execute(select(RiskSegment).where(RiskSegment.story_version_id == av.id))
    rows = list(res.scalars().all())
    return [
        {
            "id": rs.id,
            "story_version_id": rs.story_version_id,
            "chapter_id": rs.chapter_id,
            "original_text": rs.original_text,
            "rewritten_text": rs.rewritten_text,
            "risk_level": rs.risk_level,
            "created_at": rs.created_at.isoformat() if rs.created_at else None,
        }
        for rs in rows
    ]


@router.put("/{story_id}/metadata/risk-segments/{segment_id}")
async def update_risk_segment(
    story_id: int,
    segment_id: int,
    body: RiskSegmentUpdate,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    _, av = await _get_story_and_active_version(db, story_id)
    rs = await db.get(RiskSegment, segment_id)
    if rs is None or rs.story_version_id != av.id:
        raise HTTPException(status_code=404, detail="敏感段落不存在")
    rs.rewritten_text = body.rewritten_text.strip()
    _mark_vectors_dirty(av)
    await db.flush()
    return {"ok": True}
