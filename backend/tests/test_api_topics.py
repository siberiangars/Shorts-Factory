import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from unittest.mock import patch

from models.base import Base


@pytest.fixture(scope="function")
async def async_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    return factory


@pytest.fixture
async def client(async_db):
    from api.main import app
    from api.deps import get_db

    async def override_db():
        async with async_db() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_topic_requires_channel(client):
    # Create a channel first
    ch_resp = await client.post(
        "/api/channels",
        json={"name": "Test", "niche": "health", "voice_id": "v1", "language": "ru"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert ch_resp.status_code == 201
    channel_id = ch_resp.json()["id"]

    # Create topic
    resp = await client.post(
        "/api/topics",
        json={"title": "Польза магния", "channel_id": channel_id},
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert isinstance(data, list)
    assert data[0]["title"] == "Польза магния"
    assert data[0]["status"] == "pending"


@pytest.mark.asyncio
async def test_list_topics_filter_by_status(client):
    ch_resp = await client.post(
        "/api/channels",
        json={"name": "Test", "niche": "health", "voice_id": "v1", "language": "ru"},
        headers={"Authorization": "Bearer test-token"},
    )
    channel_id = ch_resp.json()["id"]

    for title in ["Topic A", "Topic B"]:
        await client.post(
            "/api/topics",
            json={"title": title, "channel_id": channel_id},
            headers={"Authorization": "Bearer test-token"},
        )

    resp = await client.get(
        "/api/topics?status=pending",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


@pytest.mark.asyncio
async def test_delete_topic(client):
    ch_resp = await client.post(
        "/api/channels",
        json={"name": "Test", "niche": "health", "voice_id": "v1", "language": "ru"},
        headers={"Authorization": "Bearer test-token"},
    )
    channel_id = ch_resp.json()["id"]

    t_resp = await client.post(
        "/api/topics",
        json={"title": "To Delete", "channel_id": channel_id},
        headers={"Authorization": "Bearer test-token"},
    )
    topic_id = t_resp.json()[0]["id"]

    del_resp = await client.delete(
        f"/api/topics/{topic_id}",
        headers={"Authorization": "Bearer test-token"},
    )
    assert del_resp.status_code == 204

    get_resp = await client.get(
        f"/api/topics/{topic_id}",
        headers={"Authorization": "Bearer test-token"},
    )
    assert get_resp.status_code == 404
