import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

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
async def test_health_check(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_create_channel(client):
    resp = await client.post(
        "/api/channels",
        json={
            "name": "Health Channel",
            "niche": "биохакинг",
            "language": "ru",
            "voice_id": "eleven-voice-id",
        },
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Health Channel"
    assert data["has_oauth"] is False
    assert data["daily_upload_count"] == 0


@pytest.mark.asyncio
async def test_unauthorized_request(client):
    resp = await client.get("/api/channels")
    assert resp.status_code == 403  # HTTPBearer returns 403 when no token


@pytest.mark.asyncio
async def test_update_channel(client):
    create_resp = await client.post(
        "/api/channels",
        json={"name": "Old Name", "niche": "health", "language": "ru", "voice_id": "v1"},
        headers={"Authorization": "Bearer test-token"},
    )
    channel_id = create_resp.json()["id"]

    update_resp = await client.patch(
        f"/api/channels/{channel_id}",
        json={"name": "New Name"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "New Name"


@pytest.mark.asyncio
async def test_delete_channel(client):
    create_resp = await client.post(
        "/api/channels",
        json={"name": "To Delete", "niche": "health", "language": "ru", "voice_id": "v1"},
        headers={"Authorization": "Bearer test-token"},
    )
    channel_id = create_resp.json()["id"]

    del_resp = await client.delete(
        f"/api/channels/{channel_id}",
        headers={"Authorization": "Bearer test-token"},
    )
    assert del_resp.status_code == 204

    get_resp = await client.get(
        f"/api/channels/{channel_id}",
        headers={"Authorization": "Bearer test-token"},
    )
    assert get_resp.status_code == 404
