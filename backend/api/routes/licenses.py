"""
License management API.

Endpoints:
  GET  /api/licenses           — список всех (admin)
  POST /api/licenses           — создать новый ключ (admin)
  DELETE /api/licenses/{id}    — отозвать (admin)
  GET  /api/licenses/verify    — проверить email (вызывается из Next.js JWT callback)
  POST /api/licenses/activate  — активировать ключ пользователем
"""
import secrets
import string
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from api.deps import AuthToken, DbSession
from api.schemas.license import (
    LicenseActivate, LicenseCreate, LicenseRead, LicenseVerifyResult,
)
from config import get_settings
from models.license import License

router = APIRouter()


def _generate_key() -> str:
    """SF-XXXX-XXXX-XXXX"""
    chars = string.ascii_uppercase + string.digits
    parts = ["".join(secrets.choice(chars) for _ in range(4)) for _ in range(3)]
    return "SF-" + "-".join(parts)


def _is_admin_email(email: str) -> bool:
    settings = get_settings()
    allowed = [e.strip() for e in (settings.allowed_emails or "").split(",") if e.strip()]
    return email in allowed


# ── Admin endpoints ───────────────────────────────────────────────────────────

@router.get("", response_model=list[LicenseRead])
async def list_licenses(db: DbSession, _: AuthToken):
    result = await db.execute(select(License).order_by(License.created_at.desc()))
    return result.scalars().all()


@router.post("", response_model=LicenseRead, status_code=status.HTTP_201_CREATED)
async def create_license(body: LicenseCreate, db: DbSession, _: AuthToken):
    lic = License(key=_generate_key(), note=body.note, expires_at=body.expires_at)
    db.add(lic)
    await db.flush()
    await db.refresh(lic)
    return lic


@router.delete("/{license_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_license(license_id: int, db: DbSession, _: AuthToken):
    lic = await db.get(License, license_id)
    if not lic:
        raise HTTPException(status_code=404, detail="License not found")
    lic.is_active = False
    await db.flush()


# ── User endpoints ────────────────────────────────────────────────────────────

@router.get("/verify", response_model=LicenseVerifyResult)
async def verify_license(
    email: str = Query(...),
    db: DbSession = None,
    _: AuthToken = None,
):
    """
    Вызывается из Next.js JWT callback при каждом входе.
    Admin email всегда валиден.
    """
    if _is_admin_email(email):
        return LicenseVerifyResult(valid=True, message="admin")

    result = await db.execute(
        select(License)
        .where(License.activated_by_email == email)
        .where(License.is_active == True)
        .limit(1)
    )
    lic = result.scalar_one_or_none()

    if lic and lic.is_valid:
        return LicenseVerifyResult(valid=True, message="ok")

    return LicenseVerifyResult(valid=False, message="no_license")


@router.post("/activate", response_model=LicenseVerifyResult)
async def activate_license(body: LicenseActivate, db: DbSession, _: AuthToken):
    """Пользователь вводит ключ → привязываем к его email."""
    # Нормализуем ключ
    key = body.key.strip().upper()

    result = await db.execute(select(License).where(License.key == key))
    lic = result.scalar_one_or_none()

    if not lic:
        raise HTTPException(status_code=400, detail="Неверный ключ лицензии")
    if not lic.is_active:
        raise HTTPException(status_code=400, detail="Лицензия отозвана")
    if lic.expires_at and lic.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Лицензия истекла")
    if lic.activated_by_email and lic.activated_by_email != body.email:
        raise HTTPException(status_code=400, detail="Ключ уже используется другим пользователем")

    # Активируем (или подтверждаем повторно для того же email)
    lic.activated_by_email = body.email
    lic.activated_by_name  = body.name
    lic.activated_at       = datetime.now(timezone.utc)
    await db.flush()

    return LicenseVerifyResult(valid=True, message="activated")
