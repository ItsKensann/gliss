import logging
import struct
from threading import Lock
from typing import Callable, Optional

import numpy as np
from faster_whisper import WhisperModel

from app.core.config import settings
from app.models.session import Pause
from app.services.audio_analysis import detect_audio_pauses

ProgressCallback = Callable[[float], None]

logger = logging.getLogger(__name__)

TARGET_SR = 16_000
MIN_TRANSCRIBE_SECONDS = 3.0
FINAL_MIN_TRANSCRIBE_SECONDS = 1.0


class TranscriptionService:
    """
    Receives raw float32 PCM chunks from the browser, keeps a live buffer for
    periodic feedback, and keeps a full-session buffer for the final report.

    Wire format of each binary WebSocket message:
        bytes 0-3  : uint32 LE source sample rate
        bytes 4+   : float32 LE PCM samples (mono)
    """

    _model: WhisperModel | None = None

    @classmethod
    def _get_model(cls) -> WhisperModel:
        if cls._model is None:
            logger.info("Loading Whisper model %r (one-time)", settings.whisper_model)
            cls._model = WhisperModel(
                settings.whisper_model,
                device="cpu",
                compute_type="int8",
            )
        return cls._model

    def __init__(self):
        self.model = self._get_model()
        self._buffer = np.array([], dtype=np.float32)
        self._full_audio_chunks: list[np.ndarray] = []
        self._last_text = ""
        self._lock = Lock()

    def add_chunk(self, data: bytes) -> None:
        if len(data) <= 4 or (len(data) - 4) % 4 != 0:
            return

        src_sr = struct.unpack_from("<I", data, 0)[0]
        if src_sr <= 0:
            return

        pcm = np.frombuffer(data[4:], dtype=np.float32).copy()
        if pcm.size == 0:
            return

        pcm = np.nan_to_num(pcm, nan=0.0, posinf=0.0, neginf=0.0)
        if src_sr != TARGET_SR:
            pcm = _resample(pcm, src_sr, TARGET_SR)
        pcm = pcm.astype(np.float32, copy=False)

        with self._lock:
            self._buffer = np.concatenate([self._buffer, pcm])
            self._full_audio_chunks.append(pcm)
            buffer_duration = len(self._buffer) / TARGET_SR

        logger.debug("PCM buffer: %.2fs", buffer_duration)

    def transcribe_buffer(self, min_seconds: float = MIN_TRANSCRIBE_SECONDS) -> dict:
        with self._lock:
            if len(self._buffer) < TARGET_SR * min_seconds:
                return {"text": "", "segments": [], "audio_duration": 0.0}

            audio = self._buffer.copy()
            consumed = len(audio)
            initial_prompt = self._last_text or None

        result = self._transcribe_audio(
            audio,
            vad_filter=True,
            vad_parameters={
                "threshold": 0.45,
                "min_speech_duration_ms": 50,
                "min_silence_duration_ms": 500,
                "speech_pad_ms": 400,
            },
            initial_prompt=initial_prompt,
            condition_on_previous_text=False,
            hallucination_silence_threshold=2.0,
        )

        text = result["text"]
        if text:
            with self._lock:
                self._buffer = self._buffer[consumed:]
                self._last_text = (self._last_text + " " + text)[-500:]
            logger.info("Transcript: %r", text[:120])
        else:
            with self._lock:
                max_keep = int(TARGET_SR * 30)
                if len(self._buffer) > max_keep:
                    self._buffer = self._buffer[-max_keep:]
                buffer_duration = len(self._buffer) / TARGET_SR
            logger.info("Transcript empty; kept %.2fs buffered for retry", buffer_duration)
        return result

    def transcribe_full_session(
        self,
        min_seconds: float = FINAL_MIN_TRANSCRIBE_SECONDS,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> dict:
        with self._lock:
            if not self._full_audio_chunks:
                return {"text": "", "segments": [], "audio_duration": 0.0}
            audio = np.concatenate(self._full_audio_chunks).astype(np.float32, copy=False)

        if len(audio) < TARGET_SR * min_seconds:
            return {"text": "", "segments": [], "audio_duration": len(audio) / TARGET_SR}

        result = self._transcribe_audio(
            audio,
            vad_filter=False,
            vad_parameters=None,
            initial_prompt=None,
            condition_on_previous_text=True,
            patience=1.2,
            hallucination_silence_threshold=2.0,
            progress_callback=progress_callback,
        )
        if result["text"]:
            logger.info("Final session transcript: %r", result["text"][:120])
        else:
            logger.info("Final session transcript empty")
        return result

    def detect_full_session_pauses(self) -> list[Pause]:
        with self._lock:
            if not self._full_audio_chunks:
                return []
            audio = np.concatenate(self._full_audio_chunks).astype(np.float32, copy=False)

        return detect_audio_pauses(audio, TARGET_SR)

    def get_buffer_duration(self) -> float:
        with self._lock:
            return len(self._buffer) / TARGET_SR

    def _transcribe_audio(
        self,
        audio: np.ndarray,
        *,
        vad_filter: bool,
        vad_parameters: dict | None,
        initial_prompt: str | None,
        condition_on_previous_text: bool,
        patience: float = 1.0,
        hallucination_silence_threshold: float | None = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> dict:
        audio_duration = len(audio) / TARGET_SR
        segments_iter, _ = self.model.transcribe(
            audio,
            language="en",
            word_timestamps=True,
            beam_size=5,
            patience=patience,
            vad_filter=vad_filter,
            vad_parameters=vad_parameters,
            initial_prompt=initial_prompt,
            condition_on_previous_text=condition_on_previous_text,
            no_speech_threshold=0.6,
            compression_ratio_threshold=2.4,
            log_prob_threshold=-1.0,
            hallucination_silence_threshold=hallucination_silence_threshold,
        )

        segments: list[dict] = []
        text_parts: list[str] = []
        for seg in segments_iter:
            words = [
                {"word": w.word, "start": w.start, "end": w.end}
                for w in (seg.words or [])
            ]
            segments.append({"start": seg.start, "end": seg.end, "text": seg.text, "words": words})
            text_parts.append(seg.text)
            if progress_callback is not None and audio_duration > 0:
                try:
                    progress_callback(min(1.0, max(0.0, seg.end / audio_duration)))
                except Exception:
                    logger.exception("progress_callback raised; ignoring")

        return {
            "text": " ".join(text_parts).strip(),
            "segments": segments,
            "audio_duration": audio_duration,
        }


def _resample(pcm: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    if src_sr == dst_sr:
        return pcm
    import librosa
    return librosa.resample(pcm, orig_sr=src_sr, target_sr=dst_sr)
