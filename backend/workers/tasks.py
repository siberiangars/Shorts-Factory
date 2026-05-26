import time
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Generator

import structlog
from celery import Task
from sqlalchemy.orm import Session

from config import get_settings
from db.session import sync_session_factory
from models.channel import Channel
from models.generation_log import GenerationLog, LogStatus
from models.topic import Topic, TopicStatus
from models.video import Video, VideoStatus
from pipeline.errors import PipelineError
from workers.celery_app import celery_app

log = structlog.get_logger()
settings = get_settings()


# ── Helpers ───────────────────────────────────────────────────────────────────

@contextmanager
def db_session() -> Generator[Session, None, None]:
    session = sync_session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _set_status(session: Session, video: Video, status) -> None:
    """Update video status and commit immediately so API can see it."""
    video.status = status
    session.commit()


def _log_step(
    session: Session,
    video: Video,
    step: str,
    status: LogStatus,
    duration_ms: int | None = None,
    cost_usd: float | None = None,
    payload: dict | None = None,
) -> None:
    entry = GenerationLog(
        video_id=video.id,
        step_name=step,
        status=status,
        duration_ms=duration_ms,
        cost_usd=Decimal(str(cost_usd)) if cost_usd is not None else None,
        payload_json=payload,
    )
    session.add(entry)
    session.flush()


def _accumulate_cost(video: Video, cost: float) -> None:
    current = float(video.generation_cost_usd or 0)
    video.generation_cost_usd = Decimal(str(round(current + cost, 4)))


def _video_dir(video_id: int) -> Path:
    return Path(settings.storage_path) / str(video_id)


# ── Main pipeline task ────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="workers.tasks.process_topic",
    max_retries=2,
    default_retry_delay=300,
)
def process_topic(self: Task, topic_id: int) -> None:
    log.info("process_topic_start", topic_id=topic_id)

    with db_session() as session:
        topic: Topic | None = session.get(Topic, topic_id)
        if not topic:
            log.error("topic_not_found", topic_id=topic_id)
            return
        channel: Channel = session.get(Channel, topic.channel_id)
        if not channel:
            log.error("channel_not_found", channel_id=topic.channel_id)
            return

        # ── Get or create Video ───────────────────────────────────────────
        video: Video | None = (
            session.query(Video).filter_by(topic_id=topic_id).first()
        )
        if not video:
            video = Video(
                topic_id=topic_id,
                channel_id=topic.channel_id,
                status=VideoStatus.pending,
            )
            session.add(video)
            session.flush()

        topic.status = TopicStatus.in_progress
        topic.started_at = datetime.now(timezone.utc)
        session.flush()

    try:
        _run_pipeline(topic_id)
    except PipelineError as exc:
        log.error("pipeline_step_failed", topic_id=topic_id, step=exc.step_name, msg=exc.message)
        with db_session() as session:
            video = session.query(Video).filter_by(topic_id=topic_id).first()
            if video:
                video.status = VideoStatus.failed
                video.error_message = f"[{exc.step_name}] {exc.message}"
            topic = session.get(Topic, topic_id)
            if topic:
                topic.status = TopicStatus.failed
                topic.error_message = exc.message
                topic.retry_count = (topic.retry_count or 0) + 1
        raise self.retry(exc=exc)
    except Exception as exc:
        log.exception("pipeline_unexpected_error", topic_id=topic_id)
        with db_session() as session:
            video = session.query(Video).filter_by(topic_id=topic_id).first()
            if video:
                video.status = VideoStatus.failed
                video.error_message = str(exc)
            topic = session.get(Topic, topic_id)
            if topic:
                topic.status = TopicStatus.failed
                topic.error_message = str(exc)
        raise self.retry(exc=exc)


def _cleanup_video_files(video) -> None:
    """
    Delete local media files after successful YouTube upload.
    Keeps disk usage O(1) regardless of how many videos are generated.
    Preserves: final_video_path for preview until publish; DB records stay.
    """
    import shutil
    vid_dir = _video_dir(video.id)
    freed_mb = 0.0

    # Remove broll dir (largest: ~100 MB per video)
    broll = vid_dir / "broll"
    if broll.exists():
        freed_mb += sum(f.stat().st_size for f in broll.rglob("*") if f.is_file()) / 1024 / 1024
        shutil.rmtree(broll, ignore_errors=True)
        video.broll_dir = None

    # Remove HeyGen raw video (if exists)
    heygen_raw = vid_dir / "heygen_raw.mp4"
    if heygen_raw.exists():
        freed_mb += heygen_raw.stat().st_size / 1024 / 1024
        heygen_raw.unlink(missing_ok=True)

    # Remove voice audio (no longer needed after assembly)
    if video.voice_audio_path:
        vp = Path(video.voice_audio_path)
        if vp.exists() and vp.name not in ("final.mp4",):
            freed_mb += vp.stat().st_size / 1024 / 1024
            vp.unlink(missing_ok=True)
            video.voice_audio_path = None

    # Remove subtitles
    if video.subtitles_path:
        sp = Path(video.subtitles_path)
        if sp.exists():
            sp.unlink(missing_ok=True)
            video.subtitles_path = None

    # Keep final.mp4 for preview (small cost ~80MB, user may want to watch)
    # It will be cleaned on next cycle or can be removed manually
    log.info("cleanup_done", video_id=video.id, freed_mb=round(freed_mb, 1))


def _burn_subs_heygen(video_path: Path, subs_path: Path, output_path: Path) -> None:
    """Burn ASS subtitles into an existing HeyGen mp4 (no re-encode of video stream)."""
    import ffmpeg
    from pipeline.errors import PipelineError
    output_path.parent.mkdir(parents=True, exist_ok=True)
    subs_arg = subs_path.resolve().as_posix()
    try:
        inp = ffmpeg.input(str(video_path))
        video = inp.video.filter("subtitles", subs_arg)
        audio = inp.audio
        out = ffmpeg.output(
            video, audio, str(output_path),
            vcodec="libx264", preset="medium", crf=20, pix_fmt="yuv420p",
            acodec="aac", audio_bitrate="192k", ar=48000,
            movflags="+faststart",
        )
        ffmpeg.run(out, overwrite_output=True, quiet=True)
    except ffmpeg.Error as exc:
        stderr = exc.stderr.decode(errors="replace") if exc.stderr else str(exc)
        raise PipelineError("video_assemble", f"FFmpeg burn-subs failed: {stderr[:500]}", exc)


def _run_pipeline(topic_id: int) -> None:
    """Execute each pipeline step idempotently, checking existing artifacts."""
    from pipeline.broll_fetch import fetch_broll
    from pipeline.script_gen import generate_script
    from pipeline.subtitles import generate_ass_subtitles, transcribe_with_timestamps
    from pipeline.video_assemble import assemble_short
    from pipeline.voice_gen import generate_voice
    from models.channel import AvatarMode

    with db_session() as session:
        topic: Topic = session.get(Topic, topic_id)
        channel: Channel = session.get(Channel, topic.channel_id)
        video: Video = session.query(Video).filter_by(topic_id=topic_id).first()
        vid_dir = _video_dir(video.id)
        use_heygen = channel.avatar_mode == AvatarMode.heygen

        # ── 1. Script generation ──────────────────────────────────────────
        if not video.script_text:
            _set_status(session, video, VideoStatus.generating_script)
            _log_step(session, video, "script_gen", LogStatus.start)
            t0 = time.monotonic()
            try:
                result = generate_script(topic, channel)
            except PipelineError:
                _log_step(session, video, "script_gen", LogStatus.failed)
                raise
            cost = result.pop("_cost_usd", 0.0)
            video.script_text = result.get("full_text", "")
            video.script_title = result.get("title", "")
            video.script_tags = result.get("tags", [])
            video.script_description = result.get("description", "")
            video.broll_keywords = result.get("broll_keywords", [])
            video.duration_sec = result.get("estimated_duration_sec")
            _accumulate_cost(video, cost)
            _log_step(session, video, "script_gen", LogStatus.success,
                      duration_ms=int((time.monotonic() - t0) * 1000),
                      cost_usd=cost, payload={"title": video.script_title})
            session.flush()

        if use_heygen:
            # ══ HeyGen branch ═════════════════════════════════════════════
            # Steps: heygen_gen → transcribe → (optional burn-in subs) → done

            # ── 2h. HeyGen avatar video ───────────────────────────────────
            heygen_path = vid_dir / "heygen_raw.mp4"
            if not (video.voice_audio_path and Path(video.voice_audio_path).exists()):
                # We reuse voice_audio_path to store the HeyGen raw video path
                # (it contains audio) — keeps idempotency check consistent
                from pipeline.heygen_gen import generate_avatar_video
                if not channel.heygen_avatar_id or not channel.heygen_voice_id:
                    raise PipelineError(
                        "heygen_gen",
                        "heygen_avatar_id and heygen_voice_id must be set on the channel",
                    )
                _set_status(session, video, VideoStatus.generating_voice)
                _log_step(session, video, "heygen_gen", LogStatus.start)
                t0 = time.monotonic()
                try:
                    _, duration = generate_avatar_video(
                        script=video.script_text,
                        avatar_id=channel.heygen_avatar_id,
                        heygen_voice_id=channel.heygen_voice_id,
                        output_path=heygen_path,
                        resolution=(settings.video_width, settings.video_height),
                        background_color=channel.heygen_background or "#f8f5f0",
                    )
                except PipelineError:
                    _log_step(session, video, "heygen_gen", LogStatus.failed)
                    raise
                video.voice_audio_path = str(heygen_path)
                if duration:
                    video.duration_sec = duration
                _log_step(session, video, "heygen_gen", LogStatus.success,
                          duration_ms=int((time.monotonic() - t0) * 1000),
                          payload={"duration": duration})
                session.flush()

            # ── 3h. Transcribe HeyGen video audio → subtitles ─────────────
            subs_path = vid_dir / "subtitles.ass"
            if not (video.subtitles_path and Path(video.subtitles_path).exists()):
                _set_status(session, video, VideoStatus.transcribing)
                _log_step(session, video, "transcribe", LogStatus.start)
                t0 = time.monotonic()
                try:
                    segments = transcribe_with_timestamps(
                        Path(video.voice_audio_path), language=channel.language
                    )
                    generate_ass_subtitles(segments, subs_path)
                except PipelineError:
                    _log_step(session, video, "transcribe", LogStatus.failed)
                    raise
                video.subtitles_path = str(subs_path)
                _log_step(session, video, "transcribe", LogStatus.success,
                          duration_ms=int((time.monotonic() - t0) * 1000))
                session.flush()

            # ── 4h. Burn subtitles into HeyGen video ─────────────────────
            final_path = vid_dir / "final.mp4"
            if not (video.final_video_path and Path(video.final_video_path).exists()):
                _set_status(session, video, VideoStatus.assembling)
                _log_step(session, video, "video_assemble", LogStatus.start)
                t0 = time.monotonic()
                try:
                    _burn_subs_heygen(
                        video_path=Path(video.voice_audio_path),
                        subs_path=Path(video.subtitles_path),
                        output_path=final_path,
                    )
                except PipelineError:
                    _log_step(session, video, "video_assemble", LogStatus.failed)
                    raise
                video.final_video_path = str(final_path)
                _log_step(session, video, "video_assemble", LogStatus.success,
                          duration_ms=int((time.monotonic() - t0) * 1000))
                session.flush()

        else:
            # ══ B-roll branch (original pipeline) ═════════════════════════

            # ── 2b. Voice synthesis ───────────────────────────────────────
            voice_path = vid_dir / "voice.mp3"
            if not (video.voice_audio_path and Path(video.voice_audio_path).exists()):
                _set_status(session, video, VideoStatus.generating_voice)
                _log_step(session, video, "voice_gen", LogStatus.start)
                t0 = time.monotonic()
                try:
                    generate_voice(
                        text=video.script_text,
                        voice_id=channel.voice_id,
                        voice_settings=channel.voice_settings_json or {},
                        output_path=voice_path,
                    )
                except PipelineError:
                    _log_step(session, video, "voice_gen", LogStatus.failed)
                    raise
                from utils.cost import elevenlabs_cost_usd
                cost = elevenlabs_cost_usd(len(video.script_text))
                video.voice_audio_path = str(voice_path)
                _accumulate_cost(video, cost)
                _log_step(session, video, "voice_gen", LogStatus.success,
                          duration_ms=int((time.monotonic() - t0) * 1000), cost_usd=cost)
                session.flush()

            # ── 3b. B-roll fetch (Storyblocks → Pexels фолбэк) ──────────
            broll_dir = vid_dir / "broll"
            if not (video.broll_dir and list(Path(video.broll_dir).glob("*.mp4"))):
                _set_status(session, video, VideoStatus.fetching_broll)
                _log_step(session, video, "broll_fetch", LogStatus.start)
                t0 = time.monotonic()

                sb_pub = getattr(settings, "storyblocks_public_key", "")
                sb_prv = getattr(settings, "storyblocks_private_key", "")
                sb_pid = getattr(settings, "storyblocks_project_id", "")
                use_storyblocks = (
                    sb_pub and not sb_pub.startswith("placeholder")
                    and sb_prv and not sb_prv.startswith("placeholder")
                )
                broll_source = "pexels"

                try:
                    if use_storyblocks:
                        from pipeline.storyblocks_fetch import fetch_broll_storyblocks
                        log.info("broll_using_storyblocks", video_id=video.id)
                        try:
                            broll_paths, new_hashes = fetch_broll_storyblocks(
                                keywords=video.broll_keywords or ["medical anatomy dark"],
                                target_duration_sec=video.duration_sec or 75.0,
                                output_dir=broll_dir,
                                used_video_hashes=set(video.broll_video_hashes or []),
                                public_key=sb_pub,
                                private_key=sb_prv,
                                project_id=sb_pid,
                            )
                            broll_source = "storyblocks"
                        except Exception as sb_exc:
                            log.warning("storyblocks_fallback_pexels",
                                        reason=str(sb_exc)[:100])
                            broll_paths, new_hashes = fetch_broll(
                                keywords=video.broll_keywords or ["health lifestyle"],
                                target_duration_sec=video.duration_sec or 75.0,
                                output_dir=broll_dir,
                                used_video_hashes=set(video.broll_video_hashes or []),
                            )
                    else:
                        log.info("broll_using_pexels", video_id=video.id)
                        broll_paths, new_hashes = fetch_broll(
                            keywords=video.broll_keywords or ["health lifestyle"],
                            target_duration_sec=video.duration_sec or 75.0,
                            output_dir=broll_dir,
                            used_video_hashes=set(video.broll_video_hashes or []),
                        )
                except PipelineError:
                    _log_step(session, video, "broll_fetch", LogStatus.failed)
                    raise

                video.broll_dir = str(broll_dir)
                video.broll_video_hashes = list(
                    set(video.broll_video_hashes or []) | set(new_hashes)
                )
                _log_step(session, video, "broll_fetch", LogStatus.success,
                          duration_ms=int((time.monotonic() - t0) * 1000),
                          payload={"clips": len(broll_paths), "source": broll_source})
                session.flush()

            # ── 4b. Transcription + subtitles ─────────────────────────────
            subs_path = vid_dir / "subtitles.ass"
            if not (video.subtitles_path and Path(video.subtitles_path).exists()):
                _set_status(session, video, VideoStatus.transcribing)
                _log_step(session, video, "transcribe", LogStatus.start)
                t0 = time.monotonic()
                try:
                    segments = transcribe_with_timestamps(
                        Path(video.voice_audio_path), language=channel.language
                    )
                    generate_ass_subtitles(segments, subs_path)
                except PipelineError:
                    _log_step(session, video, "transcribe", LogStatus.failed)
                    raise
                video.subtitles_path = str(subs_path)
                _log_step(session, video, "transcribe", LogStatus.success,
                          duration_ms=int((time.monotonic() - t0) * 1000))
                session.flush()

            # ── 5b. Video assembly ────────────────────────────────────────
            final_path = vid_dir / "final.mp4"
            if not (video.final_video_path and Path(video.final_video_path).exists()):
                _set_status(session, video, VideoStatus.assembling)
                _log_step(session, video, "video_assemble", LogStatus.start)
                t0 = time.monotonic()
                broll_paths = sorted(Path(video.broll_dir).glob("*.mp4"))
                try:
                    assemble_short(
                        voice_path=Path(video.voice_audio_path),
                        broll_paths=broll_paths,
                        subtitles_path=Path(video.subtitles_path),
                        music_path=None,
                        output_path=final_path,
                        resolution=(settings.video_width, settings.video_height),
                        fps=settings.default_video_fps,
                        title_text=video.script_title or "",
                    )
                except PipelineError:
                    _log_step(session, video, "video_assemble", LogStatus.failed)
                    raise
                video.final_video_path = str(final_path)
                _log_step(session, video, "video_assemble", LogStatus.success,
                          duration_ms=int((time.monotonic() - t0) * 1000))
                session.flush()

        # ── Finalize ──────────────────────────────────────────────────────
        video.status = VideoStatus.done
        topic.status = TopicStatus.done
        topic.finished_at = datetime.now(timezone.utc)
        log.info("pipeline_done", topic_id=topic_id, video_id=video.id,
                 cost_usd=str(video.generation_cost_usd))


# ── Manual YouTube upload task ────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="workers.tasks.upload_video_to_youtube",
    max_retries=2,
    default_retry_delay=60,
)
def upload_video_to_youtube(self: Task, video_id: int) -> None:
    from pipeline.youtube_upload import upload_short

    with db_session() as session:
        video: Video | None = session.get(Video, video_id)
        if not video:
            log.error("video_not_found", video_id=video_id)
            return
        if video.youtube_video_id:
            log.info("already_on_youtube", video_id=video_id)
            return
        if not video.final_video_path or not Path(video.final_video_path).exists():
            log.error("video_file_missing", video_id=video_id)
            video.status = VideoStatus.failed
            video.error_message = "Файл видео не найден — пересоздайте видео"
            return

        channel: Channel = session.get(Channel, video.channel_id)
        if not channel:
            log.error("channel_not_found", channel_id=video.channel_id)
            return

        topic = session.get(Topic, video.topic_id)
        title = video.script_title or (topic.title if topic else f"Video {video_id}")

        _set_status(session, video, VideoStatus.uploading)
        _log_step(session, video, "youtube_upload", LogStatus.start)
        t0 = time.monotonic()

        privacy = "public" if channel.auto_publish_public else "unlisted"
        try:
            result = upload_short(
                channel=channel,
                video_path=Path(video.final_video_path),
                title=title,
                description=video.script_description or "",
                tags=list(video.script_tags or []) + list(channel.default_tags or []),
                privacy=privacy,
            )
        except PipelineError as exc:
            _log_step(session, video, "youtube_upload", LogStatus.failed,
                      payload={"error": exc.message})
            video.status = VideoStatus.done
            video.error_message = f"[youtube_upload] {exc.message}"
            log.error("youtube_upload_failed", video_id=video_id, error=exc.message)
            raise self.retry(exc=exc)

        video.youtube_video_id = result["youtube_video_id"]
        video.youtube_url = result["youtube_url"]
        video.published_at = datetime.now(timezone.utc)
        video.error_message = None
        channel.daily_upload_count = (channel.daily_upload_count or 0) + 1
        channel.daily_upload_count_reset_at = datetime.now(timezone.utc)
        _log_step(session, video, "youtube_upload", LogStatus.success,
                  duration_ms=int((time.monotonic() - t0) * 1000),
                  payload={"video_id": video.youtube_video_id, "quota": result.get("quota_used")})

        _cleanup_video_files(video)

        video.status = VideoStatus.done
        log.info("youtube_upload_done", video_id=video_id, url=video.youtube_url)


# ── Scheduler tasks ───────────────────────────────────────────────────────────

@celery_app.task(name="workers.tasks.check_scheduled_topics")
def check_scheduled_topics() -> None:
    from sqlalchemy import and_

    log.info("check_scheduled_topics")
    with db_session() as session:
        now = datetime.now(timezone.utc)
        ready = (
            session.query(Topic)
            .filter(
                and_(
                    Topic.status == TopicStatus.pending,
                    Topic.scheduled_at <= now,
                )
            )
            .order_by(Topic.priority.desc(), Topic.scheduled_at.asc())
            .limit(20)
            .all()
        )
        for topic in ready:
            channel: Channel = session.get(Channel, topic.channel_id)
            if not channel:
                continue
            if channel.daily_upload_count >= settings.daily_upload_quota_per_project:
                from datetime import timedelta
                topic.scheduled_at = now + timedelta(days=1)
                log.info("quota_exceeded_reschedule", topic_id=topic.id, channel_id=channel.id)
                continue
            topic.status = TopicStatus.in_progress
            session.flush()
            process_topic.delay(topic.id)
            log.info("topic_queued", topic_id=topic.id)


@celery_app.task(name="workers.tasks.reset_daily_quotas")
def reset_daily_quotas() -> None:
    log.info("reset_daily_quotas")
    with db_session() as session:
        session.query(Channel).update(
            {"daily_upload_count": 0, "daily_upload_count_reset_at": datetime.now(timezone.utc)}
        )
    log.info("daily_quotas_reset")
