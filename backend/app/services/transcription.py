import logging
import struct

import numpy as np
from faster_whisper import WhisperModel

from app.core.config import settings

logger = logging.getLogger(__name__)

TARGET_SR = 16_000  # Whisper expects 16 kHz
MIN_TRANSCRIBE_SECONDS = 3.0  # Whisper degrades sharply on shorter clips — wait for context


class TranscriptionService:
    """
    Receives raw float32 PCM chunks from the browser (via Web Audio API),
    accumulates them into a buffer, and transcribes with faster-whisper.

    Wire format of each binary WebSocket message:
        bytes 0-3  : uint32 LE — original sample rate from the browser
        bytes 4+   : float32 LE PCM samples (mono)
    """

    # Model weights are large (small ≈ 500 MB) and immutable. Load once and
    # share across all sessions; per-session state stays on the instance.
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
        self._last_text = ""  # carried into next chunk as initial_prompt for context continuity

    def add_chunk(self, data: bytes) -> None:
        if len(data) < 5:
            return
        src_sr = struct.unpack_from("<I", data, 0)[0]
        pcm = np.frombuffer(data[4:], dtype=np.float32).copy()

        if src_sr != TARGET_SR:
            pcm = _resample(pcm, src_sr, TARGET_SR)

        self._buffer = np.concatenate([self._buffer, pcm])
        logger.debug("PCM buffer: %.2fs", len(self._buffer) / TARGET_SR)

    def transcribe_buffer(self, min_seconds: float = MIN_TRANSCRIBE_SECONDS) -> dict:
        if len(self._buffer) < TARGET_SR * min_seconds:
            return {"text": "", "segments": [], "audio_duration": 0.0}

        audio = self._buffer.copy()
        audio_duration = len(audio) / TARGET_SR
        self._buffer = np.array([], dtype=np.float32)  # reset for next chunk

        segments_iter, _ = self.model.transcribe(
            audio,
            language="en",
            word_timestamps=True,
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            # No directive seed prompt on the first cycle — a strong prompt biases
            # Whisper to fabricate coaching-style text on near-silence.
            initial_prompt=self._last_text or None,
            condition_on_previous_text=True,
            # Standard anti-hallucination thresholds: drop low-confidence segments
            # and segments with hallucination-typical compression signatures.
            no_speech_threshold=0.6,
            compression_ratio_threshold=2.4,
            log_prob_threshold=-1.0,
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

        text = " ".join(text_parts).strip()
        if text:
            # Whisper's initial_prompt accepts ~224 tokens; a few hundred chars is safely under that.
            self._last_text = (self._last_text + " " + text)[-500:]
        logger.info("Transcript: %r", text[:120])
        return {"text": text, "segments": segments, "audio_duration": audio_duration}

    def get_buffer_duration(self) -> float:
        return len(self._buffer) / TARGET_SR


def _resample(pcm: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    if src_sr == dst_sr:
        return pcm
    import librosa
    return librosa.resample(pcm, orig_sr=src_sr, target_sr=dst_sr)
