from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from models.topic import TopicStatus


class TopicCreate(BaseModel):
    channel_id: int
    title: str = Field(..., max_length=512)
    brief: str | None = None
    priority: int = Field(default=0, ge=0)
    scheduled_at: datetime | None = None


class TopicBatchCreate(BaseModel):
    topics: list[TopicCreate] = Field(..., min_length=1, max_length=100)


class TopicUpdate(BaseModel):
    title: str | None = Field(None, max_length=512)
    brief: str | None = None
    priority: int | None = Field(None, ge=0)
    scheduled_at: datetime | None = None
    status: TopicStatus | None = None


class TopicRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    channel_id: int
    title: str
    brief: str | None
    status: TopicStatus
    priority: int
    scheduled_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    retry_count: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime
