"""
Image-to-Video pipeline: FLUX image generation + Ken Burns (zoom/pan) effect.

Cost: ~$0.003 per image × 7 = ~$0.021 per video — 500x cheaper than Seedance.
Quality: Custom dark medical imagery matching BioBase12 style.

Flow:
  1. Generate dark medical image via FLUX Schnell on fal.ai (~$0.003)
  2. Apply slow cinematic zoom/pan with FFmpeg (Ken Burns effect)
  3. Result: 5-second vertical video clip

FLUX prompt tips for BioBase12 style:
  - "pure black background" — key for the dark style
  - "photorealistic 3D render" — medical quality
  - "dramatic lighting" — cinematic
  - "9:16 vertical composition" — for Shorts
"""
import subprocess
import time
from pathlib import Path

import requests
import structlog

from config import get_settings
from pipeline.errors import PipelineError
from utils.hashing import md5_of_string

log = structlog.get_logger()

# fal.ai FLUX Schnell — cheapest high-quality image model
_FLUX_MODEL = "fal-ai/flux/schnell"
_FLUX_ENDPOINT = f"https://queue.fal.run/{_FLUX_MODEL}"

# Ken Burns effect variations for visual diversity
_KB_EFFECTS = [
    # zoom in slowly
    "zoompan=z='min(zoom+0.0010,1.3)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=150:s=1080x1920",
    # zoom out slowly
    "zoompan=z='if(lte(zoom,1.0),1.3,max(1.0,zoom-0.0010))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=150:s=1080x1920",
    # pan right while zoomed
    "zoompan=z='1.2':x='min(iw-iw/zoom,x+1)':y='ih/2-(ih/zoom/2)':d=150:s=1080x1920",
    # pan left while zoomed
    "zoompan=z='1.2':x='max(0,iw-iw/zoom-x+1)':y='ih/2-(ih/zoom/2)':d=150:s=1080x1920",
    # slow zoom center
    "zoompan=z='min(zoom+0.0007,1.25)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=150:s=1080x1920",
]

# Medical dark-style image prompts for FLUX
MEDICAL_IMAGE_PROMPTS = {
    "heart": "photorealistic 3D anatomical human heart, pure black background, dramatic warm red lighting, subsurface scattering, medical visualization, 9:16 vertical, ultra detailed",
    "brain": "glowing human brain neural network, pure black background, electric blue bioluminescent synapses, scientific visualization, vertical composition, ultra detailed",
    "liver": "photorealistic 3D human liver, pure black background, warm amber dramatic lighting, medical 3D render, vertical composition",
    "blood": "red blood cells flowing microscope view, pure black background, dark crimson glow, scientific macro photography, vertical composition",
    "dna": "DNA double helix glowing blue-green, pure black background, molecular bonds illuminated, scientific visualization, vertical composition",
    "cell": "human cells dividing, bioluminescent green glow, pure black background, microscope view, scientific photography, vertical composition",
    "pill": "white medical capsules floating, pure black background, clinical blue-white product lighting, macro close-up, vertical composition",
    "magnesium": "magnesium mineral crystals blue-white glow, pure black background, macro close-up, bioluminescent light, vertical composition",
    "sleep": "peaceful sleeping person, dark bedroom, soft moonlight, cinematic portrait, dark moody atmosphere, vertical composition",
    "vitamin": "colorful vitamin capsules floating, pure black background, dramatic product lighting, macro photography, vertical composition",
    "neuron": "single neuron firing electric pulse, pure black background, blue electric glow, scientific visualization, vertical composition",
    "spine": "3D human spine vertebrae, pure black background, cool blue-white medical lighting, anatomical detail, vertical composition",
    "cholesterol": "artery cross-section medical visualization, pure black background, red-orange glow, scientific cutaway, vertical composition",
    "meditation": "person meditating in darkness, golden aura glow, black background, ethereal light particles, vertical composition",
    "water": "water molecules crystalline structure, pure black background, blue-white scientific glow, vertical composition",
    "exercise": "muscle fiber microscopic view, orange-red bioluminescent glow, pure black background, scientific macro, vertical composition",
}

_FALLBACK_PROMPT = "dark medical scientific visualization, pure black background, dramatic lighting, 3D render style, vertical 9:16 composition, ultra detailed photorealistic"


def _build_flux_prompt(keyword: str) -> str:
    """Build FLUX image prompt for dark medical style."""
    kw_lower = keyword.lower()
    for key, prompt in MEDICAL_IMAGE_PROMPTS.items():
        if key in kw_lower:
            return prompt
    # If keyword is already a detailed prompt (from Claude)
    if len(keyword) > 40:
        # Extract subject and add dark style
        subject = keyword[:60]
        return f"{subject}, pure black background, dramatic lighting, 9:16 vertical, ultra detailed"
    return f"{keyword}, {_FALLBACK_PROMPT}"


def _generate_image_fal(prompt: str, api_key: str, idx: int) -> str:
    """Generate image via FLUX Schnell on fal.ai. Returns image URL."""
    headers = {"Authorization": f"Key {api_key}", "Content-Type": "application/json"}
    payload = {
        "prompt": prompt,
        "image_size": "portrait_16_9",  # ~768x1360 portrait
        "num_inference_steps": 4,        # Schnell = fast
        "num_images": 1,
        "enable_safety_checker": False,
    }
    resp = requests.post(_FLUX_ENDPOINT, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    # fal.ai may return directly or queue
    if "images" in data:
        return data["images"][0]["url"]

    # Poll queue
    response_url = data.get("response_url") or f"{_FLUX_ENDPOINT}/requests/{data.get('request_id','')}"
    for _ in range(30):
        time.sleep(3)
        st = requests.get(response_url, headers=headers, timeout=15)
        st.raise_for_status()
        st_data = st.json()
        status = st_data.get("status", "")
        if status == "COMPLETED":
            output = st_data.get("output") or {}
            images = output.get("images", [])
            if images:
                return images[0]["url"]
        elif status in ("FAILED", "CANCELLED"):
            raise PipelineError("image_gen", f"FLUX job failed: {status}")
    raise PipelineError("image_gen", "FLUX timeout")


def _apply_ken_burns(image_path: Path, output_path: Path, effect_idx: int, fps: int = 30, duration: int = 5) -> Path:
    """Apply Ken Burns zoom/pan effect to create a 5-second video clip."""
    effect = _KB_EFFECTS[effect_idx % len(_KB_EFFECTS)]
    frames = fps * duration

    # Update effect with correct frame count
    effect_with_frames = effect.replace("d=150", f"d={frames}")

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", str(image_path),
        "-vf", f"{effect_with_frames},fps={fps}",
        "-t", str(duration),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-an",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=60)
    if result.returncode != 0:
        err = result.stderr.decode(errors="replace")
        raise PipelineError("ken_burns", f"FFmpeg failed: {err[:300]}")
    return output_path


def generate_broll_flux(
    keywords: list[str],
    target_duration_sec: float,
    output_dir: Path,
    used_video_hashes: set[str],
    fps: int = 30,
) -> tuple[list[Path], list[str]]:
    """
    Generate B-roll clips via FLUX image + Ken Burns effect.
    Cost: ~$0.003/image = ~$0.021 for 7 clips.
    """
    import concurrent.futures

    settings = get_settings()
    api_key = getattr(settings, "fal_api_key", "")
    if not api_key or api_key.startswith("placeholder"):
        raise PipelineError("image_gen", "FAL_API_KEY not configured")

    output_dir.mkdir(parents=True, exist_ok=True)
    clips_needed = max(5, int(target_duration_sec / 5) + 1)
    kws_to_use = keywords[:clips_needed]

    log.info("flux_broll_start", clips=len(kws_to_use), cost_estimate=f"~${len(kws_to_use)*0.003:.3f}")

    def generate_one(args):
        idx, keyword = args
        prompt = _build_flux_prompt(keyword)
        prompt_hash = md5_of_string(prompt)
        if prompt_hash in used_video_hashes:
            return None

        img_path = output_dir / f"flux_{idx:02d}.jpg"
        vid_path = output_dir / f"broll_{idx:02d}.mp4"

        try:
            # 1. Generate image
            image_url = _generate_image_fal(prompt, api_key, idx)
            # Download image
            r = requests.get(image_url, timeout=30)
            r.raise_for_status()
            img_path.write_bytes(r.content)

            # 2. Apply Ken Burns
            _apply_ken_burns(img_path, vid_path, effect_idx=idx, fps=fps, duration=5)

            # Cleanup source image
            img_path.unlink(missing_ok=True)

            log.info("flux_clip_done", idx=idx, keyword=keyword[:30], prompt=prompt[:50])
            return idx, vid_path, prompt_hash

        except Exception as exc:
            log.warning("flux_clip_failed", idx=idx, keyword=keyword[:30], error=str(exc)[:80])
            return None

    # Generate with limited concurrency (fal.ai rate limits)
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        for r in ex.map(generate_one, enumerate(kws_to_use)):
            if r is not None:
                results.append(r)

    if not results:
        raise PipelineError("image_gen", "No clips generated via FLUX")

    results.sort(key=lambda x: x[0])
    paths = [r[1] for r in results]
    hashes = [r[2] for r in results]

    log.info("flux_broll_done", clips=len(paths), actual_cost=f"~${len(paths)*0.003:.3f}")
    return paths, hashes
