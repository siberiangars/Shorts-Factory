"""
B-roll fetching with dual source strategy (Pexels + Pixabay).

Visual target: dark/black backgrounds, medical 3D renders, macro close-ups —
similar to BioBase12 / high-quality health channel style.

Strategy:
1. Transform keywords to add dark/macro style suffixes
2. Try Pexels first (portrait orientation, HD)
3. Fall back to Pixabay for same keyword (more 3D/medical content)
4. Deduplicate via URL hash
"""
from pathlib import Path

import requests
import structlog

from config import get_settings
from pipeline.errors import PipelineError
from utils.hashing import md5_of_string

log = structlog.get_logger()

_PEXELS_VIDEOS  = "https://api.pexels.com/videos/search"
_PIXABAY_VIDEOS = "https://pixabay.com/api/videos/"

# Dark/isolated style suffixes to append to keywords for better results
_DARK_SUFFIXES = [
    "black background",
    "dark background isolated",
    "3d render",
    "macro close up",
    "medical illustration",
]


def _styled_keywords(keywords: list[str]) -> list[tuple[str, str]]:
    """
    Expand keywords: original + dark-style variants.
    Returns list of (keyword, source) where source is 'pexels' or 'pixabay'.
    """
    result = []
    for kw in keywords:
        # Try original on Pexels first
        result.append((kw, "pexels"))
        # Then dark variant on Pixabay (better for medical 3D)
        dark_kw = f"{kw} {_DARK_SUFFIXES[hash(kw) % len(_DARK_SUFFIXES)]}"
        result.append((dark_kw, "pixabay"))
        # Also try original on Pixabay as fallback
        result.append((kw, "pixabay"))
    return result


def _get_best_url_pexels(video: dict) -> str | None:
    """Pick HD/SD url from Pexels video object."""
    for quality in ("hd", "uhd", "sd"):
        for vf in video.get("video_files", []):
            if vf.get("quality") == quality and vf.get("link"):
                return vf["link"]
    return None


def _search_pexels(keyword: str, api_key: str) -> list[dict]:
    """Search Pexels for portrait videos. Returns list of {url, duration, hash}."""
    try:
        resp = requests.get(
            _PEXELS_VIDEOS,
            headers={"Authorization": api_key},
            params={"query": keyword, "orientation": "portrait", "size": "large", "per_page": 8},
            timeout=20,
        )
        resp.raise_for_status()
        results = []
        for v in resp.json().get("videos", []):
            url = _get_best_url_pexels(v)
            if url:
                results.append({
                    "url": url,
                    "duration": float(v.get("duration") or 10),
                    "hash": md5_of_string(url),
                    "source": "pexels",
                })
        return results
    except Exception as exc:
        log.warning("pexels_search_failed", keyword=keyword, error=str(exc)[:80])
        return []


def _search_pixabay(keyword: str, api_key: str) -> list[dict]:
    """Search Pixabay for portrait videos."""
    if not api_key or api_key.startswith("placeholder"):
        return []
    try:
        resp = requests.get(
            _PIXABAY_VIDEOS,
            params={
                "key": api_key,
                "q": keyword,
                "video_type": "film,animation",
                "per_page": 8,
                "safesearch": "true",
            },
            timeout=20,
        )
        resp.raise_for_status()
        results = []
        for hit in resp.json().get("hits", []):
            # Prefer tall/portrait videos
            videos = hit.get("videos", {})
            # Try medium (portrait-friendly) then small
            for size in ("medium", "large", "small"):
                v = videos.get(size, {})
                url = v.get("url")
                if url:
                    w = v.get("width", 1)
                    h = v.get("height", 1)
                    # Prefer portrait or square
                    if h >= w * 0.8:
                        results.append({
                            "url": url,
                            "duration": float(hit.get("duration") or 10),
                            "hash": md5_of_string(url),
                            "source": "pixabay",
                        })
                    break
        return results
    except Exception as exc:
        log.warning("pixabay_search_failed", keyword=keyword, error=str(exc)[:80])
        return []


def _download_clip(url: str, dest: Path) -> None:
    resp = requests.get(url, stream=True, timeout=120)
    resp.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as fh:
        for chunk in resp.iter_content(chunk_size=65536):
            fh.write(chunk)


def fetch_broll(
    keywords: list[str],
    target_duration_sec: float,
    output_dir: Path,
    used_video_hashes: set[str],
) -> tuple[list[Path], list[str]]:
    """
    Download B-roll clips with dark/medical style preference.
    Uses Pexels + Pixabay with styled keyword variants.
    """
    settings = get_settings()
    pexels_key = settings.pexels_api_key
    pixabay_key = getattr(settings, "pixabay_api_key", "")

    output_dir.mkdir(parents=True, exist_ok=True)
    collected_paths: list[Path] = []
    new_hashes: list[str] = []
    total_duration = 0.0
    required = target_duration_sec * 1.3
    clip_idx = 0

    # Build expanded search list
    search_queue = _styled_keywords(keywords)

    for keyword, source in search_queue:
        if total_duration >= required:
            break

        # Search
        if source == "pexels":
            candidates = _search_pexels(keyword, pexels_key)
        else:
            candidates = _search_pixabay(keyword, pixabay_key)

        for cand in candidates:
            url_hash = cand["hash"]
            if url_hash in used_video_hashes or url_hash in new_hashes:
                continue

            dest = output_dir / f"broll_{clip_idx}.mp4"
            try:
                _download_clip(cand["url"], dest)
            except Exception as exc:
                log.warning("broll_download_failed", error=str(exc)[:60])
                continue

            total_duration += cand["duration"]
            collected_paths.append(dest)
            new_hashes.append(url_hash)
            clip_idx += 1
            log.info("broll_downloaded",
                     keyword=keyword, source=cand["source"],
                     duration=cand["duration"], hash=url_hash[:8])
            break  # one clip per keyword attempt

    if not collected_paths:
        raise PipelineError("broll_fetch",
                            f"No B-roll clips found for keywords: {keywords[:3]}")

    return collected_paths, new_hashes
