import logging
import struct

import numpy as np
from faster_whisper import WhisperModel

from app.core.config import settings

logger = logging.getLogger(__name__)

TARGET_SR = 16_000  # Whisper expects 16 kHz


class TranscriptionService:
    """
    Receives raw float32 PCM chunks from the browser (via Web Audio API),
    accumulates them into a buffer, and transcribes with faster-whisper.

    Wire format of each binary WebSocket message:
        bytes 0-3  : uint32 LE — original sample rate from the browser
        bytes 4+   : float32 LE PCM samples (mono)
    """

    def __init__(self):
        self.model = WhisperModel(
            settings.whisper_model,
            device="cpu",
            compute_type="int8",
        )
        self._buffer = np.array([], dtype=np.float32)

    def add_chunk(self, data: bytes) -> None:
        if len(data) < 5:
            return
        src_sr = struct.unpack_from("<I", data, 0)[0]
        pcm = np.frombuffer(data[4:], dtype=np.float32).copy()

        if src_sr != TARGET_SR:
            pcm = _resample(pcm, src_sr, TARGET_SR)

        self._buffer = np.concatenate([self._buffer, pcm])
        logger.debug("PCM buffer: %.2fs", len(self._buffer) / TARGET_SR)

    def transcribe_buffer(self) -> dict:
        if len(self._buffer) < TARGET_SR:          # need ≥ 1 second
            return {"text": "", "segments": []}

        audio = self._buffer.copy()
        self._buffer = np.array([], dtype=np.float32)  # reset for next chunk

        segments_iter, _ = self.model.transcribe(
            audio,
            language="en",
            word_timestamps=True,
            beam_size=5,
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
        logger.info("Transcript: %r", text[:120])
        return {"text": text, "segments": segments}

    def get_buffer_duration(self) -> float:
        return len(self._buffer) / TARGET_SR


def _resample(pcm: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    if src_sr == dst_sr:
        return pcm
    import librosa
    return librosa.resample(pcm, orig_sr=src_sr, target_sr=dst_sr)
