"""
B-roll via Storyblocks API — тёмные 3D медицинские анимации как у BioBase12.

Регистрация и тестовые ключи (5 бесплатных загрузок): developer.storyblocks.com
Полный доступ: ~$15/мес через стандартную подписку + API-план.

HMAC-формула (из официальной документации):
  key  = private_key + str(expires)
  msg  = resource_path  (например "/api/v2/videos/search")
  hash = HMAC-SHA256(key, msg).hexdigest()

Стратегия поиска:
  1. Для каждого broll-промпта → конвертируем в короткий keyword (первые слова)
  2. Ищем на Storyblocks с фильтром aspect_ratio=vertical (9:16)
  3. Скачиваем лучший результат
  4. Если не нашли — фолбэк на Pexels
"""
import hashlib
import hmac as hmac_lib
import time
from pathlib import Path

import requests
import structlog

from pipeline.errors import PipelineError
from utils.hashing import md5_of_string

log = structlog.get_logger()

_BASE = "https://api.storyblocks.com"
_TIMEOUT = 30


# ── HMAC auth ─────────────────────────────────────────────────────────────────

def _make_hmac(resource: str, private_key: str, expires: int) -> str:
    """HMAC-SHA256: key = private_key+expires, msg = resource_path."""
    key = (private_key + str(expires)).encode("utf-8")
    msg = resource.encode("utf-8")
    return hmac_lib.new(key, msg, hashlib.sha256).hexdigest()


def _auth(resource: str, public_key: str, private_key: str, project_id: str) -> dict:
    """Возвращает dict с параметрами аутентификации для requests."""
    expires = int(time.time()) + 3600
    return {
        "APIKEY": public_key,
        "EXPIRES": expires,
        "HMAC": _make_hmac(resource, private_key, expires),
        "project_id": project_id,
    }


# ── Keyword conversion ────────────────────────────────────────────────────────

def _prompt_to_keyword(prompt: str) -> str:
    """
    Конвертирует длинный Seedance-промпт в короткий поисковый keyword для Storyblocks.
    Пример: "Slow orbital camera around photorealistic 3D human heart, black bg, red glow"
            → "3D human heart anatomy"
    """
    # Убираем технические слова камеры, качества, освещения
    stop_words = {
        "slow", "orbital", "camera", "shot", "around", "photorealistic", "cinematic",
        "pure", "black", "background", "glow", "lighting", "bokeh", "depth", "field",
        "motion", "macro", "extreme", "close-up", "push-in", "toward", "rotating",
        "4k", "hd", "render", "animation", "visualization", "scientific", "medical",
        "dramatic", "warm", "cool", "blue", "red", "green", "amber", "bioluminescent",
        "subsurface", "clinical", "portrait", "studio", "dark", "floating", "glowing",
        "firing", "dissolving", "beating", "slowly", "gently", "detailed",
    }
    words = prompt.lower().replace(",", " ").replace("-", " ").split()
    kept = [w for w in words if w not in stop_words and len(w) > 2]
    # Берём первые 4 значимых слова
    keyword = " ".join(kept[:4])
    return keyword or "medical anatomy"


# ── Search ────────────────────────────────────────────────────────────────────

def _search(
    keyword: str,
    public_key: str,
    private_key: str,
    project_id: str,
    per_page: int = 8,
) -> list[dict]:
    resource = "/api/v2/videos/search"
    params = _auth(resource, public_key, private_key, project_id)
    params.update({
        "keywords": keyword,
        "page": 1,
        "per_page": per_page,
        "content_type": "all",          # footage + motion graphics
        "has_audio": "false",
        "aspect_ratio": "vertical",     # 9:16 — портретная ориентация для Shorts
    })
    try:
        resp = requests.get(f"{_BASE}{resource}", params=params, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", []) or data.get("videos", [])
    except Exception as exc:
        log.warning("storyblocks_search_failed", keyword=keyword, error=str(exc)[:80])
        return []


# ── Download ──────────────────────────────────────────────────────────────────

def _get_download_url(
    video_id: str,
    public_key: str,
    private_key: str,
    project_id: str,
) -> str | None:
    resource = f"/api/v2/videos/{video_id}/download"
    params = _auth(resource, public_key, private_key, project_id)
    try:
        resp = requests.get(f"{_BASE}{resource}", params=params, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        # API может вернуть разные ключи в зависимости от версии
        return (
            data.get("download_url")
            or data.get("url")
            or data.get("stock-item", {}).get("download-url")
        )
    except Exception as exc:
        log.warning("storyblocks_download_url_failed", video_id=video_id, error=str(exc)[:80])
        return None


def _download_file(url: str, dest: Path) -> None:
    resp = requests.get(url, stream=True, timeout=120)
    resp.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as fh:
        for chunk in resp.iter_content(chunk_size=65536):
            fh.write(chunk)


# ── Main function ─────────────────────────────────────────────────────────────

def fetch_broll_storyblocks(
    keywords: list[str],
    target_duration_sec: float,
    output_dir: Path,
    used_video_hashes: set[str],
    public_key: str,
    private_key: str,
    project_id: str,
) -> tuple[list[Path], list[str]]:
    """
    Скачивает b-roll клипы из Storyblocks.
    Возвращает (пути к файлам, хэши для дедупликации).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    collected_paths: list[Path] = []
    new_hashes: list[str] = []
    total_duration = 0.0
    required = target_duration_sec * 1.3
    clip_idx = 0

    # Конвертируем промпты в ключевые слова
    search_terms = [_prompt_to_keyword(kw) for kw in keywords]

    for term in search_terms:
        if total_duration >= required:
            break

        results = _search(term, public_key, private_key, project_id)

        for item in results:
            video_id = str(item.get("id", ""))
            if not video_id:
                continue

            url_hash = md5_of_string(video_id)
            if url_hash in used_video_hashes or url_hash in new_hashes:
                continue

            # Получаем URL для скачивания
            download_url = _get_download_url(video_id, public_key, private_key, project_id)
            if not download_url:
                continue

            dest = output_dir / f"broll_{clip_idx}.mp4"
            try:
                _download_file(download_url, dest)
            except Exception as exc:
                log.warning("storyblocks_download_failed",
                            video_id=video_id, error=str(exc)[:60])
                continue

            duration = float(item.get("duration") or 10.0)
            total_duration += duration
            collected_paths.append(dest)
            new_hashes.append(url_hash)
            clip_idx += 1

            log.info("storyblocks_clip_downloaded",
                     term=term, video_id=video_id,
                     duration=duration, hash=url_hash[:8])
            break  # один клип на поисковый запрос

    log.info("storyblocks_fetch_done",
             clips=len(collected_paths),
             total_sec=round(total_duration, 1))
    return collected_paths, new_hashes
