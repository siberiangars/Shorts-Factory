"""
piapi.ai pipeline: FLUX image generation → Kling video generation.

Cost per video:
- FLUX Schnell: ~$0.01/image × 7 = ~$0.07
- Kling v1.6 std: ~$0.08-0.15/clip × 7 = ~$0.56-1.05
- Total: ~$0.63-1.12/video

Dramatically cheaper than Seedance ($10+), similar quality to BioBase12.
"""
import time
from pathlib import Path

import requests
import structlog

from config import get_settings
from pipeline.errors import PipelineError
from pipeline.seedance_gen import MEDICAL_PROMPTS as MEDICAL_IMAGE_PROMPTS, _FALLBACK_TEMPLATE
from utils.hashing import md5_of_string

log = structlog.get_logger()

BASE = "https://api.piapi.ai/api/v1/task"


def _get_headers(api_key: str) -> dict:
    return {"X-API-Key": api_key, "Content-Type": "application/json"}


def _poll_task(task_id: str, api_key: str, timeout_sec: int = 300) -> dict:
    """Poll piapi.ai task until completed or failed."""
    headers = {"X-API-Key": api_key}
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        time.sleep(5)
        try:
            r = requests.get(f"{BASE}/{task_id}", headers=headers, timeout=15)
            r.raise_for_status()
            data = r.json().get("data", {})
            status = data.get("status", "")
            if status == "completed":
                return data.get("output", {})
            elif status == "failed":
                detail = data.get("detail", "unknown")
                raise PipelineError("piapi_gen", f"Task failed: {detail}")
        except PipelineError:
            raise
        except Exception as exc:
            log.warning("piapi_poll_error", task_id=task_id, error=str(exc)[:60])
    raise PipelineError("piapi_gen", f"Task timed out after {timeout_sec}s")


def _build_image_prompt(keyword: str) -> str:
    """Build FLUX prompt optimized for dark medical visuals."""
    kw_lower = keyword.lower()
    for key, template in MEDICAL_IMAGE_PROMPTS.items():
        if key in kw_lower:
            return template
    if len(keyword) > 50:
        return keyword
    return _FALLBACK_TEMPLATE.format(keyword=keyword)


def _build_kling_prompt(keyword: str) -> str:
    """Build Kling video prompt — cinematic, medical dark style."""
    kw_lower = keyword.lower()

    # Medical cinematic templates for Kling
    kling_templates = {
        "heart": "Slow cinematic orbital shot around photorealistic 3D human heart beating gently, pure black background, dramatic warm red subsurface lighting, medical visualization 4K",
        "brain": "Slow push-in toward glowing human brain with electric blue neural synapses firing, pure black background, bioluminescent glow, scientific 4K",
        "blood": "Extreme slow motion red blood cells flowing through artery, microscope macro view, pure black background, red glowing cells, cinematic medical 4K",
        "dna": "DNA double helix slowly rotating, glowing blue-green molecular bonds, pure black background, scientific animation 4K",
        "cell": "Human cells dividing in slow motion, bioluminescent green glow, pure black background, microscope view, 4K",
        "spine": "Slow rotation of photorealistic 3D human spine, pure black background, cold blue-white medical lighting, anatomical visualization 4K",
        "pill": "White medical capsules floating in slow motion, macro close-up, pure black background, clinical lighting 4K",
        "sleep": "Peaceful person sleeping, soft moonlight through dark bedroom, slow cinematic dolly shot, dreamy atmosphere 4K",
        "meditation": "Person meditating in darkness with golden glowing aura, ethereal light particles, slow motion 4K",
        "magnesium": "Crystalline magnesium minerals and capsules floating, macro slow motion, pure black background, blue-white crystalline glow 4K",
    }
    for key, template in kling_templates.items():
        if key in kw_lower:
            return template
    if len(keyword) > 50:
        return keyword  # Already a good prompt from Claude
    return f"Cinematic slow motion {keyword}, pure black background, dramatic lighting, medical health visualization, 4K"


def generate_flux_image(prompt: str, api_key: str, width: int = 768, height: int = 1344) -> str:
    """Generate image via FLUX Schnell on piapi.ai. Returns image URL."""
    r = requests.post(BASE, headers=_get_headers(api_key), json={
        "model": "Qubico/flux1-schnell",
        "task_type": "txt2img",
        "input": {"prompt": prompt, "width": width, "height": height}
    }, timeout=15)
    r.raise_for_status()
    d = r.json()
    task_id = d.get("data", {}).get("task_id", "")
    if not task_id:
        raise PipelineError("piapi_gen", f"FLUX task not created: {str(d)[:100]}")

    output = _poll_task(task_id, api_key, timeout_sec=120)
    url = output.get("image_url", "")
    if not url:
        raise PipelineError("piapi_gen", f"No image URL in output: {str(output)[:100]}")
    return url


def generate_kling_video(
    prompt: str,
    api_key: str,
    duration: int = 5,
    version: str = "1.5",   # v1.5 ~2x cheaper than v1.6
    mode: str = "std",
) -> str:
    """Generate video via Kling on piapi.ai. Returns video URL."""
    r = requests.post(BASE, headers=_get_headers(api_key), json={
        "model": "kling",
        "task_type": "video_generation",
        "input": {
            "prompt": prompt,
            "negative_prompt": "blurry, low quality, text, watermark, logo, subtitles",
            "cfg_scale": 0.5,
            "duration": duration,
            "aspect_ratio": "9:16",
            "mode": mode,
            "version": version,
        },
        "config": {"service_mode": "public"}
    }, timeout=15)
    r.raise_for_status()
    d = r.json()
    task_id = d.get("data", {}).get("task_id", "")
    if not task_id:
        raise PipelineError("piapi_gen", f"Kling task not created: {str(d)[:100]}")

    log.info("kling_task_submitted", task_id=task_id, prompt=prompt[:50])
    output = _poll_task(task_id, api_key, timeout_sec=300)

    # Extract video URL
    video_url = output.get("video_url", "")
    if not video_url:
        works = output.get("works", [{}])
        if works:
            res = works[0].get("resource", {})
            video_url = res.get("resource", "") or res.get("url", "")
    if not video_url:
        raise PipelineError("piapi_gen", f"No video URL: {str(output)[:150]}")
    return video_url


def _download(url: str, dest: Path) -> None:
    r = requests.get(url, stream=True, timeout=120)
    r.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        for chunk in r.iter_content(chunk_size=65536):
            f.write(chunk)


def generate_broll_piapi(
    keywords: list[str],
    target_duration_sec: float,
    output_dir: Path,
    used_video_hashes: set[str],
    use_kling: bool = True,
) -> tuple[list[Path], list[str]]:
    """
    Generate B-roll via piapi.ai:
    - use_kling=True: Kling video generation (~$0.09-0.15/clip)
    - use_kling=False: FLUX image + Ken Burns (~$0.01/clip, free animation)
    """
    import concurrent.futures
    from pipeline.image_to_video import _apply_ken_burns

    settings = get_settings()
    api_key = getattr(settings, "piapi_api_key", "")
    if not api_key or api_key.startswith("placeholder"):
        raise PipelineError("piapi_gen", "PIAPI_API_KEY not configured")

    output_dir.mkdir(parents=True, exist_ok=True)
    # Max 4 Kling clips to control cost (~$0.55-0.90 total vs $3+ for 7 clips)
    max_clips = 4 if use_kling else 6
    clips_needed = min(max_clips, max(3, int(target_duration_sec / 5)))
    kws = keywords[:clips_needed]

    log.info("piapi_broll_start", clips=len(kws),
             mode="kling" if use_kling else "flux_kenburns")

    def generate_one(args):
        idx, keyword = args
        prompt_hash = md5_of_string(keyword + ("_kling" if use_kling else "_flux"))
        if prompt_hash in used_video_hashes:
            return None
        dest = output_dir / f"broll_{idx:02d}.mp4"
        try:
            if use_kling:
                kling_prompt = _build_kling_prompt(keyword)
                video_url = generate_kling_video(kling_prompt, api_key)
                _download(video_url, dest)
            else:
                # FLUX + Ken Burns fallback
                image_prompt = _build_image_prompt(keyword)
                image_url = generate_flux_image(image_prompt, api_key)
                # Download image
                img_path = output_dir / f"flux_{idx:02d}.jpg"
                _download(image_url, img_path)
                _apply_ken_burns(img_path, dest, effect_idx=idx, duration=5)
                img_path.unlink(missing_ok=True)

            log.info("piapi_clip_done", idx=idx, keyword=keyword[:30])
            return idx, dest, prompt_hash
        except Exception as exc:
            log.warning("piapi_clip_failed", idx=idx, keyword=keyword[:30], error=str(exc)[:80])
            return None

    results = []
    # Max 2 concurrent Kling (rate limit), 3 for FLUX
    max_workers = 2 if use_kling else 3
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        for r in ex.map(generate_one, enumerate(kws)):
            if r is not None:
                results.append(r)

    if not results:
        raise PipelineError("piapi_gen", f"No clips generated for: {kws[:3]}")

    results.sort(key=lambda x: x[0])
    return [r[1] for r in results], [r[2] for r in results]
