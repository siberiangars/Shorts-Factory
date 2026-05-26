"""
Seedance 2.0 (ByteDance) via fal.ai — AI video generation for health/medical content.

Структура промпта для максимального качества:
[Camera movement] + [Subject] + [Style] + [Background] + [Lighting] + [Mood]

Пример:
"Slow orbital camera shot around photorealistic 3D anatomical human heart,
 pure black background, dramatic warm red lighting with subsurface scattering,
 cinematic 4K medical visualization, dark ethereal atmosphere"
"""
import time
from pathlib import Path

import requests
import structlog

from config import get_settings
from pipeline.errors import PipelineError
from utils.hashing import md5_of_string

log = structlog.get_logger()

# fal.ai endpoints — verified working
_MODEL = "bytedance/seedance-2.0/text-to-video"
_MODEL_FAST = "bytedance/seedance-2.0/text-to-video"

# Universal style suffix — гарантирует тёмный медицинский стиль
_STYLE_SUFFIX = (
    ", pure black background, cinematic 4K, professional medical visualization, "
    "dramatic studio lighting, dark dramatic atmosphere, high detail"
)

# ── Шаблоны промптов для медицинских тем ─────────────────────────────────────
# Каждый шаблон следует формату: [движение камеры] + [объект] + [стиль] + [свет]

MEDICAL_PROMPTS = {
    # Органы и анатомия
    "heart":
        "Slow orbital camera around photorealistic 3D human heart, beating gently, "
        "pure black background, dramatic warm red subsurface lighting, cinematic 4K medical visualization",

    "brain":
        "Slow push-in shot toward glowing human brain 3D render, neural synapses firing "
        "with electric blue pulses, pure black background, bioluminescent glow, scientific 4K",

    "liver":
        "Cinematic dolly shot of photorealistic 3D human liver, pure black background, "
        "warm golden-amber dramatic lighting, medical visualization 4K",

    "kidney":
        "Slow orbit around detailed 3D human kidney cross-section, pure black background, "
        "blue-white clinical lighting, medical education visualization 4K",

    "spine":
        "Slow rotation of photorealistic 3D human spine vertebrae, pure black background, "
        "cold blue-white medical lighting, dramatic shadows, clinical visualization 4K",

    "lung":
        "Macro close-up of alveoli 3D render, oxygen molecules flowing, pure black background, "
        "blue glowing light, scientific medical visualization 4K",

    "stomach":
        "Cinematic shot of 3D human digestive system glowing, pure black background, "
        "warm orange inner glow, scientific visualization, dramatic 4K",

    # Молекулы и клетки
    "cell":
        "Macro microscope view of human cells dividing, bioluminescent glow, pure black background, "
        "green-blue light, slow motion, scientific visualization 4K",

    "blood":
        "Slow motion blood cells flowing through artery, macro scale, pure black background, "
        "red glowing cells with dark plasma, cinematic medical visualization 4K",

    "dna":
        "Slow rotation of DNA double helix glowing blue-green, pure black background, "
        "luminescent molecular bonds, scientific animation 4K, dramatic depth of field",

    "molecule":
        "Slowly rotating molecular structure with glowing atomic bonds, pure black background, "
        "blue-white scientific glow, depth of field, visualization 4K",

    "neuron":
        "Neuron firing with electric pulse traveling along axon, bioluminescent blue glow, "
        "pure black background, slow motion, scientific visualization 4K",

    # Добавки и питание
    "magnesium":
        "Crystalline magnesium minerals and white capsules floating in slow motion, macro, "
        "pure black background, cool blue-white crystalline glow, depth of field, cinematic 4K",

    "vitamin":
        "Colorful vitamin capsules and supplements floating in slow motion, macro close-up, "
        "pure black background, dramatic product lighting, cinematic 4K",

    "pill":
        "White medical capsules dissolving and floating, macro extreme close-up, "
        "pure black background, clinical white-blue lighting, slow motion cinematic 4K",

    "supplement":
        "Nutritional supplement capsules and powder bursting in slow motion, macro, "
        "pure black background, golden product lighting, dramatic 4K",

    "omega":
        "Golden omega-3 fish oil capsule with liquid inside, macro extreme close-up, "
        "pure black background, warm golden dramatic backlighting, cinematic 4K",

    # Здоровье и состояния
    "sleep":
        "Peaceful person sleeping in dark bedroom, soft moonlight rays through curtains, "
        "slow dolly shot, cinematic grain, dark dreamy atmosphere, 4K",

    "stress":
        "Abstract visualization of stress and anxiety, dark swirling energy patterns, "
        "deep blue-red color palette, cinematic atmospheric 4K",

    "inflammation":
        "Abstract medical visualization of inflammation, glowing red-orange particles, "
        "pure black background, dramatic lighting, slow motion 4K",

    "cholesterol":
        "Artery cross-section with cholesterol buildup visualization, medical 3D render, "
        "pure black background, dramatic warm-cold lighting contrast, 4K",

    "sugar":
        "Blood glucose crystal structures dissolving, macro close-up, pure black background, "
        "golden-amber dramatic lighting, slow motion cinematic 4K",

    "hormone":
        "Abstract hormone molecules traveling through bloodstream, glowing particles, "
        "dark background, blue-gold scientific glow, cinematic visualization 4K",

    # Образ жизни
    "meditation":
        "Person meditating in complete darkness, glowing golden aura emanating from body, "
        "ethereal light particles, cinematic slow motion, dark atmospheric 4K",

    "exercise":
        "Muscle fiber microscope view contracting in slow motion, bioluminescent orange glow, "
        "pure black background, dramatic medical visualization 4K",

    "walking":
        "Extreme slow motion legs walking, dark moody background, dramatic side lighting, "
        "cinematic film grain, health lifestyle 4K",

    "water":
        "Crystal clear water droplet in extreme slow motion macro, pure black background, "
        "blue-white dramatic backlighting, photorealistic cinematic 4K",

    # Общие медицинские
    "doctor":
        "Elderly doctor hands carefully examining, dramatic Rembrandt lighting, dark studio, "
        "cinematic portrait, warm professional atmosphere 4K",

    "analysis":
        "Blood test tube with glowing liquid in slow rotation, macro close-up, "
        "pure black background, clinical blue-white lighting, medical visualization 4K",

    "research":
        "Scientific microscope with glowing specimen, dark laboratory background, "
        "dramatic blue-white lighting, cinematic focus pull 4K",
}

# Fallback промпт если ничего не подошло
_FALLBACK_TEMPLATE = (
    "Cinematic close-up shot of {keyword}, pure black background, "
    "dramatic studio lighting, high detail, medical health visualization, "
    "dark atmospheric, 4K cinematography"
)


def build_seedance_prompt(keyword: str) -> str:
    """
    Строит оптимальный промпт для Seedance 2.0.
    Ищет совпадение в словаре, иначе использует шаблон.
    """
    kw_lower = keyword.lower()

    # Точное совпадение ключа
    for key, prompt in MEDICAL_PROMPTS.items():
        if key in kw_lower:
            return prompt  # суффикс уже вшит в шаблоны выше

    # Если промпт уже длинный (сгенерирован Claude) — просто использовать как есть
    if len(keyword) > 50:
        return keyword

    # Fallback с кастомным ключевым словом
    return _FALLBACK_TEMPLATE.format(keyword=keyword)


def _call_fal_api(
    prompt: str,
    api_key: str,
    duration: int = 5,
) -> str:
    """
    Отправляет запрос в fal.ai и возвращает URL готового видео.
    """
    headers = {
        "Authorization": f"Key {api_key}",
        "Content-Type": "application/json",
    }

    # Try multiple possible endpoints
    endpoint = f"https://queue.fal.run/{_MODEL}"
    payload = {
        "prompt": prompt,
        "duration": str(duration),
        "resolution": "720p",
        "aspect_ratio": "9:16",
    }

    resp = requests.post(endpoint, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    job_data = resp.json()

    log.info("seedance_submitted", status=job_data.get("status"), prompt=prompt[:50])

    # Direct video result (unlikely for queue)
    if "video" in job_data and isinstance(job_data.get("video"), dict):
        return job_data["video"]["url"]

    # fal.ai returns response_url for polling
    response_url = job_data.get("response_url") or job_data.get("status_url")
    request_id = job_data.get("request_id", "")

    if not response_url and request_id:
        response_url = f"{endpoint}/requests/{request_id}"

    if not response_url:
        raise PipelineError("seedance_gen", f"No response_url: {str(job_data)[:200]}")

    for attempt in range(90):  # max 7.5 minutes
        time.sleep(5)
        try:
            st = requests.get(response_url, headers=headers, timeout=20)
            st.raise_for_status()
            st_data = st.json()
        except Exception as e:
            log.warning("seedance_poll_error", attempt=attempt, error=str(e)[:50])
            continue

        status = st_data.get("status", "")
        log.info("seedance_poll", status=status, attempt=attempt, prompt=prompt[:30])

        if status == "COMPLETED":
            output = st_data.get("output") or {}
            video = output.get("video", {})
            url = video.get("url") if isinstance(video, dict) else video
            if url:
                return url
            raise PipelineError("seedance_gen", f"No video URL in output: {str(st_data)[:200]}")

        elif status in ("FAILED", "CANCELLED"):
            raise PipelineError("seedance_gen", f"Job {status}: {st_data.get('error','?')}")

    raise PipelineError("seedance_gen", "Timeout after 7.5 minutes")


def _submit_job(keyword: str, idx: int, api_key: str) -> tuple[int, str, str, str]:
    """Отправляет один job в fal.ai, возвращает (idx, prompt, prompt_hash, response_url)."""
    prompt = build_seedance_prompt(keyword)
    prompt_hash = md5_of_string(prompt)
    headers = {"Authorization": f"Key {api_key}", "Content-Type": "application/json"}
    payload = {"prompt": prompt, "duration": "5", "resolution": "720p", "aspect_ratio": "9:16"}
    endpoint = f"https://queue.fal.run/{_MODEL}"

    r = requests.post(endpoint, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    data = r.json()

    # Direct result
    if "video" in data and isinstance(data.get("video"), dict):
        return idx, prompt, prompt_hash, data["video"]["url"]

    # Queue — use response_url
    response_url = data.get("response_url") or f"{endpoint}/requests/{data.get('request_id','')}"
    return idx, prompt, prompt_hash, response_url


def _poll_job(response_url: str, api_key: str) -> str:
    """Ждёт завершения job (polling response_url) и возвращает URL видео."""
    # If already a direct video URL — return immediately
    if response_url.endswith(".mp4") or "cdn" in response_url:
        return response_url

    headers = {"Authorization": f"Key {api_key}"}
    for _ in range(90):
        time.sleep(5)
        try:
            st = requests.get(response_url, headers=headers, timeout=20)
            st.raise_for_status()
            data = st.json()
        except Exception:
            continue

        status = data.get("status", "")
        if status == "COMPLETED":
            output = data.get("output") or {}
            video = output.get("video", {}) if isinstance(output, dict) else {}
            url = video.get("url") if isinstance(video, dict) else video
            if url:
                return url
            raise PipelineError("seedance_gen", f"No URL in output: {str(data)[:150]}")
        elif status in ("FAILED", "CANCELLED"):
            raise PipelineError("seedance_gen", f"Job {status}: {data.get('error','?')}")
    raise PipelineError("seedance_gen", "Timeout 7.5 min")


def generate_broll_seedance(
    keywords: list[str],
    target_duration_sec: float,
    output_dir: Path,
    used_video_hashes: set[str],
) -> tuple[list[Path], list[str]]:
    """
    Генерирует B-roll клипы через Seedance 2.0 ПАРАЛЛЕЛЬНО.
    7 клипов отправляются одновременно → готово за ~90 сек вместо 10 мин.
    """
    import concurrent.futures

    settings = get_settings()
    api_key = getattr(settings, "fal_api_key", "")
    if not api_key or api_key.startswith("placeholder"):
        raise PipelineError("seedance_gen", "FAL_API_KEY not set")

    output_dir.mkdir(parents=True, exist_ok=True)

    # Фильтруем уже использованные
    to_generate = []
    for idx, kw in enumerate(keywords):
        prompt = build_seedance_prompt(kw)
        ph = md5_of_string(prompt)
        if ph not in used_video_hashes:
            to_generate.append((idx, kw))

    if not to_generate:
        raise PipelineError("seedance_gen", "All keywords already used")

    log.info("seedance_parallel_start", clips=len(to_generate))
    t_start = time.monotonic()

    # ── Шаг 1: Отправить jobs БАТЧАМИ (max 3 одновременно — fal.ai rate limit) ───
    submitted: list[tuple[int, str, str, str]] = []
    MAX_CONCURRENT = 3

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as ex:
        futures = {ex.submit(_submit_job, kw, idx, api_key): (idx, kw) for idx, kw in to_generate}
        for fut in concurrent.futures.as_completed(futures):
            try:
                result = fut.result()
                submitted.append(result)
                log.info("seedance_submitted", idx=result[0], keyword=futures[fut][1][:30])
            except Exception as exc:
                log.warning("seedance_submit_failed", kw=futures[fut][1][:30], error=str(exc)[:80])
                # Retry once with delay on 403
                if "403" in str(exc):
                    import time as _t
                    _t.sleep(2)
                    try:
                        idx, kw = futures[fut]
                        result = _submit_job(kw, idx, api_key)
                        submitted.append(result)
                        log.info("seedance_retry_ok", idx=idx)
                    except Exception as exc2:
                        log.warning("seedance_retry_failed", error=str(exc2)[:60])

    if not submitted:
        raise PipelineError("seedance_gen", "Failed to submit any jobs")

    # ── Шаг 2: Ждём и скачиваем ПАРАЛЛЕЛЬНО ─────────────────────────────────
    def poll_and_download(item: tuple[int, str, str, str]) -> tuple[int, Path, str] | None:
        idx, prompt, ph, url_or_status = item
        dest = output_dir / f"seedance_{idx:02d}.mp4"
        try:
            # Если уже прямой URL
            if url_or_status.startswith("https://") and "/requests/" not in url_or_status:
                video_url = url_or_status
            else:
                video_url = _poll_job(url_or_status, api_key)
            # Скачать
            dl = requests.get(video_url, stream=True, timeout=120)
            dl.raise_for_status()
            with open(dest, "wb") as fh:
                for chunk in dl.iter_content(chunk_size=65536):
                    fh.write(chunk)
            log.info("seedance_clip_done", idx=idx, path=str(dest))
            return idx, dest, ph
        except Exception as exc:
            log.warning("seedance_poll_failed", idx=idx, error=str(exc)[:80])
            return None

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(submitted)) as ex:
        for r in ex.map(poll_and_download, submitted):
            if r is not None:
                results.append(r)

    if not results:
        raise PipelineError("seedance_gen", "No clips downloaded")

    # Сортируем по idx для правильного порядка
    results.sort(key=lambda x: x[0])
    collected_paths = [r[1] for r in results]
    new_hashes = [r[2] for r in results]
    total_sec = len(results) * 5.0
    elapsed = time.monotonic() - t_start

    log.info("seedance_broll_done", clips=len(results),
             duration=total_sec, elapsed_sec=round(elapsed))
    return collected_paths, new_hashes
