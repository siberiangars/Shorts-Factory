"""
HeyGen Avatar Studio API.

Endpoints:
  GET  /api/heygen/avatars           — список готовых аватаров
  GET  /api/heygen/voices            — список голосов
  GET  /api/heygen/talking-photos    — список Talking Photo аватаров

  POST /api/heygen/upload-asset      — загрузить фото/видео/аудио в HeyGen
  POST /api/heygen/talking-photo     — создать аватар из загруженного фото
  POST /api/heygen/generate-avatar   — сгенерировать AI аватар по промпту
  POST /api/heygen/voice-clone       — клонировать голос из аудио
  DELETE /api/heygen/talking-photo/{id} — удалить talking photo
"""
import io
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from api.deps import AuthToken
from config import get_settings

router = APIRouter()

HEYGEN_BASE = "https://api.heygen.com"


def _hdr(api_key: str) -> dict:
    return {"X-Api-Key": api_key, "Accept": "application/json"}


def _check_key(settings) -> str:
    key = settings.heygen_api_key
    if not key or key.startswith("placeholder"):
        raise HTTPException(status_code=400, detail="HEYGEN_API_KEY не настроен")
    return key


# ── Listing ───────────────────────────────────────────────────────────────────

@router.get("/avatars")
async def list_heygen_avatars(_: AuthToken) -> list[dict]:
    """Список HeyGen аватаров (video avatars + instant avatars)."""
    settings = get_settings()
    api_key = _check_key(settings)
    from pipeline.heygen_gen import list_avatars
    try:
        return list_avatars(api_key)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"HeyGen: {exc}")


@router.get("/voices")
async def list_heygen_voices(_: AuthToken) -> list[dict]:
    """Список голосов HeyGen."""
    settings = get_settings()
    api_key = _check_key(settings)
    from pipeline.heygen_gen import list_voices
    try:
        return list_voices(api_key)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"HeyGen: {exc}")


@router.get("/talking-photos")
async def list_talking_photos(_: AuthToken) -> list[dict]:
    """Список Photo Avatar (Talking Photos) — загруженные пользователем фото."""
    import requests as req
    settings = get_settings()
    api_key = _check_key(settings)
    try:
        r = req.get(f"{HEYGEN_BASE}/v1/talking_photo.list",
                    headers=_hdr(api_key), timeout=20)
        r.raise_for_status()
        data = r.json()
        return data.get("data", {}).get("talking_photos", []) or []
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"HeyGen: {exc}")


# ── Asset upload ──────────────────────────────────────────────────────────────

@router.post("/upload-asset")
async def upload_asset(
    file: UploadFile = File(...),
    _: AuthToken = None,
) -> dict:
    """
    Загружает фото/видео/аудио в HeyGen и возвращает asset key.
    Используется перед созданием talking photo или клонированием голоса.
    """
    import requests as req
    settings = get_settings()
    api_key = _check_key(settings)

    content = await file.read()
    mime = file.content_type or "application/octet-stream"

    try:
        r = req.post(
            f"{HEYGEN_BASE}/v1/asset",
            headers={**_hdr(api_key), "Content-Type": mime},
            data=content,
            timeout=120,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Upload failed: {exc}")

    if data.get("error"):
        raise HTTPException(status_code=400, detail=str(data["error"]))

    asset_data = data.get("data", {})
    return {
        "asset_id": asset_data.get("id") or asset_data.get("asset_id"),
        "image_key": asset_data.get("image_key") or asset_data.get("id"),
        "url": asset_data.get("url"),
    }


# ── Create talking photo ──────────────────────────────────────────────────────

class TalkingPhotoCreate(BaseModel):
    name:      str
    image_key: str   # returned from upload-asset


@router.post("/talking-photo")
async def create_talking_photo(body: TalkingPhotoCreate, _: AuthToken) -> dict:
    """Создаёт Talking Photo аватар из загруженного изображения."""
    import requests as req
    settings = get_settings()
    api_key = _check_key(settings)

    try:
        r = req.post(
            f"{HEYGEN_BASE}/v1/talking_photo",
            json={"image_key": body.image_key, "name": body.name},
            headers=_hdr(api_key),
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"HeyGen: {exc}")

    if data.get("error"):
        raise HTTPException(status_code=400, detail=str(data["error"]))

    return data.get("data", data)


@router.delete("/talking-photo/{photo_id}", status_code=204)
async def delete_talking_photo(photo_id: str, _: AuthToken) -> None:
    import requests as req
    settings = get_settings()
    api_key = _check_key(settings)
    req.delete(f"{HEYGEN_BASE}/v2/talking_photo/{photo_id}",
               headers=_hdr(api_key), timeout=20)


# ── Generate AI avatar from prompt ────────────────────────────────────────────

class GenerateAvatarBody(BaseModel):
    name:        str
    prompt:      str
    # Точные значения HeyGen API (проверено):
    gender:      str = "Man"           # Man | Woman | Unspecified
    age:         str = "Early Middle Age"  # Young Adult | Early Middle Age | Late Middle Age | Senior
    ethnicity:   str = "White"         # White | Black | East Asian | South Asian | Hispanic | Middle Eastern
    orientation: str = "vertical"      # vertical | horizontal | square
    style:       str = "Cinematic"     # Realistic | Cinematic | Pixar
    pose:        str = "half_body"     # half_body | close_up | full_body
    appearance:  str = "casual"        # casual | formal | smart_casual | ...


@router.post("/generate-avatar")
async def generate_ai_avatar(body: GenerateAvatarBody, _: AuthToken) -> dict:
    """Генерирует AI фото-аватар по текстовому описанию (HeyGen Photo Avatar)."""
    import requests as req
    settings = get_settings()
    api_key = _check_key(settings)

    payload = {
        "name":        body.name,
        "prompt":      body.prompt,
        "gender":      body.gender,
        "age":         body.age,
        "ethnicity":   body.ethnicity,
        "orientation": body.orientation,
        "style":       body.style,
        "pose":        body.pose,
        "appearance":  body.appearance,
    }

    try:
        r = req.post(
            f"{HEYGEN_BASE}/v2/photo_avatar/photo/generate",
            json=payload,
            headers=_hdr(api_key),
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"HeyGen: {exc}")

    if data.get("error"):
        raise HTTPException(status_code=400, detail=str(data["error"]))

    return data.get("data", data)


# ── Voice cloning ─────────────────────────────────────────────────────────────

@router.post("/voice-clone")
async def clone_voice(
    name: str = Form(...),
    file: UploadFile = File(...),
    _: AuthToken = None,
) -> dict:
    """
    Клонирует голос из аудио-записи (mp3 / wav / m4a, мин. 30 сек).
    Возвращает voice_id для использования в генерации видео.
    """
    import requests as req
    settings = get_settings()
    api_key = _check_key(settings)

    audio_bytes = await file.read()
    filename = file.filename or "voice.mp3"
    mime = file.content_type or "audio/mpeg"

    try:
        r = req.post(
            f"{HEYGEN_BASE}/v2/voice_clone",
            headers=_hdr(api_key),
            files={"audio": (filename, io.BytesIO(audio_bytes), mime)},
            data={"name": name},
            timeout=120,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Voice clone failed: {exc}")

    if data.get("error"):
        raise HTTPException(status_code=400, detail=str(data["error"]))

    return data.get("data", data)
