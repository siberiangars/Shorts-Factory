from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import and_, select

from api.deps import AuthToken, DbSession
from api.schemas.topic import TopicBatchCreate, TopicCreate, TopicRead, TopicUpdate
from models.topic import Topic, TopicStatus

router = APIRouter()


@router.post("", response_model=list[TopicRead], status_code=status.HTTP_201_CREATED)
async def create_topics(body: TopicCreate | TopicBatchCreate, db: DbSession, _: AuthToken):
    items: list[TopicCreate] = (
        body.topics if isinstance(body, TopicBatchCreate) else [body]
    )
    created = []
    for item in items:
        t = Topic(**item.model_dump())
        db.add(t)
        created.append(t)
    await db.flush()
    for t in created:
        await db.refresh(t)
    return [TopicRead.model_validate(t) for t in created]


@router.get("", response_model=list[TopicRead])
async def list_topics(
    db: DbSession,
    _: AuthToken,
    channel_id: int | None = Query(None),
    status: TopicStatus | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    stmt = select(Topic)
    filters = []
    if channel_id:
        filters.append(Topic.channel_id == channel_id)
    if status:
        filters.append(Topic.status == status)
    if filters:
        stmt = stmt.where(and_(*filters))
    stmt = stmt.order_by(Topic.priority.desc(), Topic.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return [TopicRead.model_validate(t) for t in result.scalars().all()]


@router.get("/{topic_id}", response_model=TopicRead)
async def get_topic(topic_id: int, db: DbSession, _: AuthToken):
    t = await db.get(Topic, topic_id)
    if not t:
        raise HTTPException(status_code=404, detail="Topic not found")
    return TopicRead.model_validate(t)


@router.patch("/{topic_id}", response_model=TopicRead)
async def update_topic(topic_id: int, body: TopicUpdate, db: DbSession, _: AuthToken):
    t = await db.get(Topic, topic_id)
    if not t:
        raise HTTPException(status_code=404, detail="Topic not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(t, field, value)
    await db.flush()
    await db.refresh(t)
    return TopicRead.model_validate(t)


@router.delete("/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_topic(topic_id: int, db: DbSession, _: AuthToken):
    t = await db.get(Topic, topic_id)
    if not t:
        raise HTTPException(status_code=404, detail="Topic not found")
    await db.delete(t)


@router.post("/{topic_id}/run", response_model=TopicRead)
async def run_topic(topic_id: int, db: DbSession, _: AuthToken):
    t = await db.get(Topic, topic_id)
    if not t:
        raise HTTPException(status_code=404, detail="Topic not found")
    if t.status == TopicStatus.in_progress:
        raise HTTPException(status_code=409, detail="Topic already in progress")
    t.status = TopicStatus.in_progress
    await db.flush()
    await db.refresh(t)
    from workers.tasks import process_topic
    process_topic.delay(topic_id)
    return TopicRead.model_validate(t)
