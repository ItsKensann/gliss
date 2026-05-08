import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.models.session import AnalysisResult, FaceMetrics
from app.services.audio_analysis import AudioAnalysisService
from app.services.feedback import get_ai_feedback, get_coherence_score
from app.services.session_store import build_report, save_report
from app.services.transcription import MIN_TRANSCRIBE_SECONDS, TranscriptionService

logger = logging.getLogger(__name__)
router = APIRouter()

ANALYSIS_INTERVAL = 5.0
_whisper_executor = ThreadPoolExecutor(max_workers=1)


FACE_METRICS_FRESHNESS_S = 10.0  # snapshots older than this are treated as no-data


async def _run_transcription_cycle(
    *,
    websocket: WebSocket,
    transcription: TranscriptionService,
    analysis: AudioAnalysisService,
    face_metrics_ref: list[FaceMetrics],  # mutable 1-element list so callers can update it
    last_face_metrics_at_ref: list,  # [datetime | None] — when face_metrics_ref was last updated
    full_transcript: str,
    chunks: list[AnalysisResult],
    loop: asyncio.AbstractEventLoop,
    with_ai: bool,
    anchor_ref: list,  # [datetime | None] — anchor for chunk offsets; first audio time
    min_seconds: float | None = None,
) -> str:
    """
    Transcribe buffered audio, run local analysis, optionally call Claude,
    append to chunks, and send to the client.
    Returns the updated full_transcript string.
    """
    transcribe = (
        transcription.transcribe_buffer
        if min_seconds is None
        else lambda: transcription.transcribe_buffer(min_seconds=min_seconds)
    )
    result = await loop.run_in_executor(_whisper_executor, transcribe)
    if not result["text"].strip():
        return full_transcript

    chunk_text = result["text"]
    full_transcript = (full_transcript + " " + chunk_text).strip()

    fillers, speed, pauses, immediate_feedback = analysis.analyze_transcript(result)
    breath_advice = analysis.suggest_breath_control(speed, pauses)

    ai_fb: str = ""
    coherence: float | None = None

    if with_ai:
        try:
            ai_fb, coherence = await asyncio.gather(
                get_ai_feedback(
                    chunk_text, len(fillers), speed.current_wpm,
                    face_metrics_ref[0].eye_contact_score,
                ),
                get_coherence_score(full_transcript[-500:]),
            )
        except Exception as e:
            logger.warning("AI feedback error (skipping for this chunk): %s", e)

    audio_duration = float(result.get("audio_duration") or 0.0)
    anchor = anchor_ref[0] or datetime.now(timezone.utc)
    end_offset = (datetime.now(timezone.utc) - anchor).total_seconds()
    start_offset = max(0.0, end_offset - audio_duration)

    # Snapshot the latest face metric, but only if it's actually fresh —
    # the frontend stops sending while no face is visible, so a stale
    # snapshot from minutes ago shouldn't pollute the chunk.
    eye_snapshot: float | None = None
    head_snapshot: float | None = None
    last_at = last_face_metrics_at_ref[0]
    if last_at is not None:
        age = (datetime.now(timezone.utc) - last_at).total_seconds()
        if age <= FACE_METRICS_FRESHNESS_S:
            eye_snapshot = round(face_metrics_ref[0].eye_contact_score, 3)
            head_snapshot = round(face_metrics_ref[0].head_stability, 3)

    output = AnalysisResult(
        transcript=chunk_text,
        filler_words=fillers,
        speed=speed,
        pauses=pauses,
        breath_advice=breath_advice,
        immediate_feedback=immediate_feedback,
        coherence_score=coherence,
        ai_feedback=ai_fb,
        start_offset_seconds=round(start_offset, 2),
        end_offset_seconds=round(end_offset, 2),
        avg_eye_contact=eye_snapshot,
        avg_head_stability=head_snapshot,
    )
    chunks.append(output)

    try:
        await websocket.send_text(output.model_dump_json())
    except Exception:
        pass  # Client already disconnected — result still saved in chunks

    return full_transcript


@router.websocket("/session")
async def session_websocket(
    websocket: WebSocket,
    session_id: str = Query(...),
):
    await websocket.accept()
    logger.info("Session started: %s", session_id)

    transcription = TranscriptionService()
    analysis = AudioAnalysisService()
    # Wrap in a list so the nested async function can mutate it without nonlocal
    face_metrics_ref = [FaceMetrics(eye_contact_score=1.0, head_stability=1.0, timestamp=0)]
    # When the latest face metric was received. None until the first one arrives;
    # _run_transcription_cycle uses this to decide whether the snapshot is fresh
    # enough to attach to the chunk (vs. leaving the field null = no data).
    last_face_metrics_at_ref: list[datetime | None] = [None]
    ai_enabled_ref = [False]  # off by default during dev — client must opt in via "config" message
    prompt_ref: list[str | None] = [None]
    target_duration_ref: list[float | None] = [None]
    # Stamped on first audio frame received and on the user's "stop" control
    # message. These — not the WS accept/disconnect times — are what define the
    # session's actual recording window for the report.
    first_audio_at_ref: list[datetime | None] = [None]
    recording_end_at_ref: list[datetime | None] = [None]
    full_transcript = ""
    chunks: list[AnalysisResult] = []
    started_at = datetime.now(timezone.utc)
    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    async def run_analysis():
        nonlocal full_transcript

        # First cycle: poll the buffer so transcription fires as soon as we have
        # enough audio, instead of waiting a flat ANALYSIS_INTERVAL. Without this,
        # the user sees a ~7s gap between countdown end and first feedback.
        while transcription.get_buffer_duration() < MIN_TRANSCRIBE_SECONDS:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=0.25)
                return
            except asyncio.TimeoutError:
                pass

        full_transcript = await _run_transcription_cycle(
            websocket=websocket,
            transcription=transcription,
            analysis=analysis,
            face_metrics_ref=face_metrics_ref,
            last_face_metrics_at_ref=last_face_metrics_at_ref,
            full_transcript=full_transcript,
            chunks=chunks,
            loop=loop,
            with_ai=ai_enabled_ref[0],
            anchor_ref=first_audio_at_ref,
        )

        while True:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=ANALYSIS_INTERVAL)
                break
            except asyncio.TimeoutError:
                pass

            full_transcript = await _run_transcription_cycle(
                websocket=websocket,
                transcription=transcription,
                analysis=analysis,
                face_metrics_ref=face_metrics_ref,
                full_transcript=full_transcript,
                chunks=chunks,
                loop=loop,
                with_ai=ai_enabled_ref[0],
                anchor_ref=first_audio_at_ref,
            )

    analysis_task = asyncio.create_task(run_analysis())

    try:
        while True:
            data = await websocket.receive()
            if data.get("type") == "websocket.disconnect":
                break
            if "bytes" in data:
                if first_audio_at_ref[0] is None:
                    first_audio_at_ref[0] = datetime.now(timezone.utc)
                transcription.add_chunk(data["bytes"])
            elif "text" in data:
                try:
                    msg = json.loads(data["text"])
                    if msg.get("type") == "metrics":
                        face_metrics_ref[0] = FaceMetrics(
                            eye_contact_score=msg.get("eye_contact_score", 1.0),
                            head_stability=msg.get("head_stability", 1.0),
                            timestamp=msg.get("timestamp", 0),
                        )
                        last_face_metrics_at_ref[0] = datetime.now(timezone.utc)
                    elif msg.get("type") == "config":
                        if "ai_enabled" in msg:
                            ai_enabled_ref[0] = bool(msg["ai_enabled"])
                            logger.info("AI feedback %s", "enabled" if ai_enabled_ref[0] else "disabled")
                        if "prompt" in msg:
                            prompt_ref[0] = msg["prompt"] or None
                        if "target_duration_seconds" in msg:
                            tds = msg["target_duration_seconds"]
                            target_duration_ref[0] = float(tds) if tds is not None else None
                    elif msg.get("type") == "control" and msg.get("action") == "stop":
                        # User signaled session end (timer hit 0 or End clicked).
                        # Stamp the recording end NOW — any audio that arrives during
                        # the client's wrap-up buffer is captured into the transcript
                        # but doesn't extend the reported session duration.
                        if recording_end_at_ref[0] is None:
                            recording_end_at_ref[0] = datetime.now(timezone.utc)
                            logger.info("Recording end signaled by client")
                except json.JSONDecodeError:
                    pass
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        # Signal the analysis loop and wait for it to finish its current work.
        # This avoids cancelling an in-flight Whisper call.
        stop_event.set()
        try:
            await asyncio.wait_for(analysis_task, timeout=30.0)
        except (asyncio.TimeoutError, Exception):
            analysis_task.cancel()

        # Report timestamps describe the *recording window* — not the WS lifetime.
        # started_at: first audio frame received (falls back to WS accept time
        #   if no audio ever arrived, e.g. an immediate cancel).
        # ended_at: time the client signaled stop (falls back to now if the WS
        #   was killed without a control message — older clients or crashes).
        report_started_at = first_audio_at_ref[0] or started_at
        report_ended_at = recording_end_at_ref[0] or datetime.now(timezone.utc)

        def _save(is_finalized: bool) -> None:
            report = build_report(
                session_id,
                report_started_at,
                report_ended_at,
                chunks,
                full_transcript,
                prompt=prompt_ref[0],
                target_duration_seconds=target_duration_ref[0],
                is_finalized=is_finalized,
            )
            save_report(report)

        # Save what we have NOW so the frontend stops polling 404s and can render
        # immediately. The final transcription cycle below picks up trailing
        # audio that arrived during the in-flight Whisper run plus the wrap-up
        # buffer; we re-save when it's done, and the frontend re-fetches because
        # is_finalized=False.
        _save(is_finalized=False)
        logger.info(
            "Session %s preliminary save — %d chunks (running final cycle)",
            session_id, len(chunks),
        )

        try:
            full_transcript = await _run_transcription_cycle(
                websocket=websocket,
                transcription=transcription,
                analysis=analysis,
                face_metrics_ref=face_metrics_ref,
                last_face_metrics_at_ref=last_face_metrics_at_ref,
                full_transcript=full_transcript,
                chunks=chunks,
                loop=loop,
                with_ai=False,  # Session is over; skip the Claude round-trip
                anchor_ref=first_audio_at_ref,
                min_seconds=1.0,
            )
        except Exception:
            logger.exception("Final transcription cycle failed; saving as-is")

        _save(is_finalized=True)
        logger.info(
            "Session %s finalized — %d chunks, %.0fs",
            session_id, len(chunks),
            (report_ended_at - report_started_at).total_seconds(),
        )
