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
from app.services.transcription import TranscriptionService

logger = logging.getLogger(__name__)
router = APIRouter()

ANALYSIS_INTERVAL = 5.0
_whisper_executor = ThreadPoolExecutor(max_workers=1)


async def _run_transcription_cycle(
    *,
    websocket: WebSocket,
    transcription: TranscriptionService,
    analysis: AudioAnalysisService,
    face_metrics_ref: list[FaceMetrics],  # mutable 1-element list so callers can update it
    full_transcript: str,
    chunks: list[AnalysisResult],
    loop: asyncio.AbstractEventLoop,
    with_ai: bool,
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

    output = AnalysisResult(
        transcript=chunk_text,
        filler_words=fillers,
        speed=speed,
        pauses=pauses,
        breath_advice=breath_advice,
        immediate_feedback=immediate_feedback,
        coherence_score=coherence,
        ai_feedback=ai_fb,
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
    ai_enabled_ref = [False]  # off by default during dev — client must opt in via "config" message
    full_transcript = ""
    chunks: list[AnalysisResult] = []
    started_at = datetime.now(timezone.utc)
    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    async def run_analysis():
        nonlocal full_transcript

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
            )

    analysis_task = asyncio.create_task(run_analysis())

    try:
        while True:
            data = await websocket.receive()
            if data.get("type") == "websocket.disconnect":
                break
            if "bytes" in data:
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
                    elif msg.get("type") == "config":
                        ai_enabled_ref[0] = bool(msg.get("ai_enabled", True))
                        logger.info("AI feedback %s", "enabled" if ai_enabled_ref[0] else "disabled")
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

        # Always do a final transcription to capture audio buffered since
        # the last interval fired (covers short sessions and partial intervals).
        # Use a low threshold here — we won't get another chance to capture
        # the user's last words.
        full_transcript = await _run_transcription_cycle(
            websocket=websocket,
            transcription=transcription,
            analysis=analysis,
            face_metrics_ref=face_metrics_ref,
            full_transcript=full_transcript,
            chunks=chunks,
            loop=loop,
            with_ai=False,  # Session is over; skip the Claude round-trip
            min_seconds=1.0,
        )

        ended_at = datetime.now(timezone.utc)
        if chunks:
            report = build_report(session_id, started_at, ended_at, chunks, full_transcript)
            save_report(report)
            logger.info("Session %s saved — %d chunks, %.0fs", session_id, len(chunks), report.duration_seconds)
        else:
            logger.info("Session %s ended with no transcribable audio", session_id)
