import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.models.session import AnalysisResult, FaceMetrics, Pause
from app.services.audio_analysis import AudioAnalysisService, localize_pauses
from app.services.feedback import get_ai_feedback, get_coherence_score
from app.services.session_store import build_report, save_report
from app.services.transcription import MIN_TRANSCRIBE_SECONDS, TranscriptionService

logger = logging.getLogger(__name__)
router = APIRouter()

ANALYSIS_INTERVAL = 5.0
FINAL_REPORT_WINDOW_SECONDS = 10.0
_whisper_executor = ThreadPoolExecutor(max_workers=1)


def _clamp_metric(value: object, default: float = 1.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _float_value(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _average_face_metrics(
    samples: list[tuple[datetime, FaceMetrics]],
    start_at: datetime,
    end_at: datetime,
) -> tuple[float | None, float | None]:
    window = [metric for received_at, metric in samples if start_at <= received_at <= end_at]
    if not window:
        return None, None

    eye_values = [m.eye_contact_score if m.face_visible else 0.0 for m in window]
    head_values = [m.head_stability if m.face_visible else 0.0 for m in window]
    return (
        round(sum(eye_values) / len(eye_values), 3),
        round(sum(head_values) / len(head_values), 3),
    )


def _final_words(segments: list[dict]) -> list[dict]:
    words: list[dict] = []
    for segment in segments:
        for word in segment.get("words", []):
            text = str(word.get("word", "")).strip()
            if not text:
                continue
            start = _float_value(word.get("start"), 0.0)
            end = _float_value(word.get("end"), start)
            if end < start:
                end = start
            words.append({"word": text, "start": start, "end": end})
    words.sort(key=lambda w: w["start"])
    return words


def _final_word_pauses(words: list[dict]) -> list[Pause]:
    pauses: list[Pause] = []
    for previous, current in zip(words, words[1:]):
        gap_start = float(previous["end"])
        gap_end = float(current["start"])
        duration = gap_end - gap_start
        if duration >= 0.8:
            pauses.append(Pause(
                start=round(gap_start, 2),
                end=round(gap_end, 2),
                duration=round(duration, 2),
            ))
    return pauses


def _final_chunk_text(words: list[dict]) -> str:
    return " ".join(word["word"].strip() for word in words).strip()


def _build_final_report_chunks(
    final_result: dict,
    face_metric_samples: list[tuple[datetime, FaceMetrics]],
    report_started_at: datetime,
    audio_pauses: list[Pause] | None = None,
) -> list[AnalysisResult]:
    words = _final_words(final_result.get("segments", []))
    if not words:
        return []

    analysis = AudioAnalysisService()
    audio_duration = float(final_result.get("audio_duration") or 0.0)
    word_pauses = _final_word_pauses(words)
    audio_pause_list = audio_pauses or []
    global_pauses = audio_pause_list or word_pauses
    logger.debug("Final word pause candidates: %s", [p.model_dump() for p in word_pauses])
    logger.debug("Final audio pause candidates: %s", [p.model_dump() for p in audio_pause_list])
    grouped_words: dict[int, list[dict]] = {}
    for word in words:
        window_index = int(max(0.0, float(word["start"])) // FINAL_REPORT_WINDOW_SECONDS)
        grouped_words.setdefault(window_index, []).append(word)

    chunks: list[AnalysisResult] = []
    for window_index in sorted(grouped_words):
        group = grouped_words[window_index]
        start_offset = window_index * FINAL_REPORT_WINDOW_SECONDS
        natural_end = start_offset + FINAL_REPORT_WINDOW_SECONDS
        end_offset = min(natural_end, audio_duration) if audio_duration else natural_end
        end_offset = max(end_offset, float(group[-1]["end"]))
        chunk_duration = max(0.1, end_offset - start_offset)
        transcript = _final_chunk_text(group)

        local_words = [
            {
                "word": word["word"],
                "start": round(max(0.0, float(word["start"]) - start_offset), 2),
                "end": round(max(0.0, float(word["end"]) - start_offset), 2),
            }
            for word in group
        ]
        segment = {
            "start": local_words[0]["start"],
            "end": local_words[-1]["end"],
            "text": transcript,
            "words": local_words,
        }
        chunk_result = {
            "text": transcript,
            "segments": [segment],
            "audio_duration": chunk_duration,
        }

        fillers, speed, detected_pauses, _ = analysis.analyze_transcript(chunk_result)
        pauses = localize_pauses(global_pauses, start_offset, end_offset)
        if not audio_pause_list and not pauses:
            pauses = detected_pauses
        immediate_feedback = analysis._generate_immediate_feedback(fillers, speed, pauses)
        breath_advice = analysis.suggest_breath_control(speed, pauses)
        logger.debug(
            "Final chunk %.2f-%.2f pause assignments: %s",
            start_offset,
            end_offset,
            [p.model_dump() for p in pauses],
        )

        eye_snapshot, head_snapshot = _average_face_metrics(
            face_metric_samples,
            report_started_at + timedelta(seconds=start_offset),
            report_started_at + timedelta(seconds=end_offset),
        )

        chunks.append(AnalysisResult(
            transcript=transcript,
            filler_words=fillers,
            speed=speed,
            pauses=pauses,
            breath_advice=breath_advice,
            immediate_feedback=immediate_feedback,
            coherence_score=None,
            ai_feedback="",
            start_offset_seconds=round(start_offset, 2),
            end_offset_seconds=round(end_offset, 2),
            avg_eye_contact=eye_snapshot,
            avg_head_stability=head_snapshot,
        ))

    return chunks


async def _run_transcription_cycle(
    *,
    websocket: WebSocket,
    transcription: TranscriptionService,
    analysis: AudioAnalysisService,
    face_metric_samples: list[tuple[datetime, FaceMetrics]],
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
    cycle_started_at = datetime.now(timezone.utc)
    result = await loop.run_in_executor(_whisper_executor, transcribe)
    if not result["text"].strip():
        return full_transcript

    chunk_text = result["text"]
    full_transcript = (full_transcript + " " + chunk_text).strip()

    fillers, speed, pauses, immediate_feedback = analysis.analyze_transcript(result)
    breath_advice = analysis.suggest_breath_control(speed, pauses)

    ai_fb: str = ""
    coherence: float | None = None

    audio_duration = float(result.get("audio_duration") or 0.0)
    anchor = anchor_ref[0] or cycle_started_at
    end_offset = (cycle_started_at - anchor).total_seconds()
    start_offset = max(0.0, end_offset - audio_duration)
    chunk_started_at = anchor + timedelta(seconds=start_offset)
    chunk_ended_at = anchor + timedelta(seconds=end_offset)
    eye_snapshot, head_snapshot = _average_face_metrics(
        face_metric_samples,
        chunk_started_at,
        chunk_ended_at,
    )

    if with_ai:
        try:
            ai_fb, coherence = await asyncio.gather(
                get_ai_feedback(
                    chunk_text, len(fillers), speed.current_wpm,
                    eye_snapshot,
                ),
                get_coherence_score(full_transcript[-500:]),
            )
        except Exception as e:
            logger.warning("AI feedback error (skipping for this chunk): %s", e)

    # Store the average face metrics for the same window as this transcript chunk.
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
    face_metric_samples: list[tuple[datetime, FaceMetrics]] = []
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
            face_metric_samples=face_metric_samples,
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
                face_metric_samples=face_metric_samples,
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
                        received_at = datetime.now(timezone.utc)
                        face_metrics = FaceMetrics(
                            eye_contact_score=_clamp_metric(msg.get("eye_contact_score"), 1.0),
                            head_stability=_clamp_metric(msg.get("head_stability"), 1.0),
                            face_visible=bool(msg.get("face_visible", True)),
                            timestamp=_float_value(msg.get("timestamp"), 0.0),
                        )
                        face_metric_samples.append((received_at, face_metrics))
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
                face_metric_samples=face_metric_samples,
                full_transcript=full_transcript,
                chunks=chunks,
                loop=loop,
                with_ai=False,  # Session is over; skip the Claude round-trip
                anchor_ref=first_audio_at_ref,
                min_seconds=1.0,
            )
        except Exception:
            logger.exception("Final transcription cycle failed; saving as-is")

        try:
            final_result = await loop.run_in_executor(
                _whisper_executor,
                transcription.transcribe_full_session,
            )
            final_text = final_result["text"].strip()
            if final_text:
                audio_pauses = transcription.detect_full_session_pauses()
                logger.info(
                    "Session %s audio pause detection found %d pauses",
                    session_id,
                    len(audio_pauses),
                )
                logger.debug(
                    "Session %s audio pause details: %s",
                    session_id,
                    [p.model_dump() for p in audio_pauses],
                )
                live_ai_feedback = [chunk.ai_feedback for chunk in chunks if chunk.ai_feedback]
                live_coherence_scores = [
                    chunk.coherence_score
                    for chunk in chunks
                    if chunk.coherence_score is not None
                ]
                final_chunks = _build_final_report_chunks(
                    final_result,
                    face_metric_samples,
                    report_started_at,
                    audio_pauses,
                )
                for final_chunk, note in zip(final_chunks, live_ai_feedback):
                    final_chunk.ai_feedback = note
                for final_chunk, score in zip(final_chunks, live_coherence_scores):
                    final_chunk.coherence_score = score
                full_transcript = final_text
                if final_chunks:
                    chunks = final_chunks
                logger.info(
                    "Session %s final full-pass transcript applied (%d chunks)",
                    session_id, len(final_chunks),
                )
        except Exception:
            logger.exception("Full-session transcription failed; keeping live chunks")

        _save(is_finalized=True)
        logger.info(
            "Session %s finalized — %d chunks, %.0fs",
            session_id, len(chunks),
            (report_ended_at - report_started_at).total_seconds(),
        )
