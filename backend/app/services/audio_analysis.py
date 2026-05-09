import string
from collections import defaultdict
from math import ceil

import numpy as np

from app.models.session import (
    BreathAdvice,
    FillerWord,
    ImmediateFeedback,
    Pause,
    SpeedAnalysis,
)

FILLER_WORDS = {
    "um", "uh", "like", "so", "basically", "literally", "actually",
    "right", "okay", "er", "hmm", "well", "anyway", "you know",
    "sort of", "kind of", "i mean", "honestly", "clearly",
}

WORD_STRIP_CHARS = string.punctuation


def detect_audio_pauses(
    pcm: np.ndarray,
    sample_rate: int,
    *,
    min_pause_seconds: float = 0.8,
    frame_ms: int = 50,
    max_speech_blip_ms: int = 200,
    silence_threshold: float | None = None,
) -> list[Pause]:
    if sample_rate <= 0 or pcm.size == 0:
        return []

    audio = np.nan_to_num(np.asarray(pcm, dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    frame_size = max(1, int(sample_rate * frame_ms / 1000))
    frame_count = int(ceil(len(audio) / frame_size))
    rms = np.zeros(frame_count, dtype=np.float32)

    for frame_index in range(frame_count):
        start = frame_index * frame_size
        end = min(len(audio), start + frame_size)
        frame = audio[start:end]
        if frame.size:
            rms[frame_index] = float(np.sqrt(np.mean(frame * frame)))

    if silence_threshold is None:
        peak_level = float(np.max(rms))
        speech_level = max(float(np.percentile(rms, 90)), peak_level * 0.5)
        noise_floor = float(np.percentile(rms, 20))
        threshold = speech_level * 0.12
        if speech_level > 0 and noise_floor <= speech_level * 0.4:
            threshold = max(threshold, noise_floor * 2.5)
        silence_threshold = max(0.002, min(0.03, threshold))

    silent = rms <= silence_threshold
    speech_frames = np.flatnonzero(~silent)
    if speech_frames.size < 2:
        return []

    first_speech = int(speech_frames[0])
    last_speech = int(speech_frames[-1])
    max_blip_frames = max(1, int(ceil(max_speech_blip_ms / frame_ms)))

    index = first_speech
    while index <= last_speech:
        if silent[index]:
            index += 1
            continue

        run_start = index
        while index <= last_speech and not silent[index]:
            index += 1
        run_end = index
        surrounded_by_silence = (
            run_start > first_speech
            and run_end <= last_speech
            and silent[run_start - 1]
            and silent[run_end]
        )
        if surrounded_by_silence and run_end - run_start <= max_blip_frames:
            silent[run_start:run_end] = True

    min_pause_frames = int(ceil(min_pause_seconds * sample_rate / frame_size))
    pauses: list[Pause] = []
    index = first_speech
    while index <= last_speech:
        if not silent[index]:
            index += 1
            continue

        run_start = index
        while index <= last_speech and silent[index]:
            index += 1
        run_end = index

        if run_end - run_start >= min_pause_frames:
            start = run_start * frame_size / sample_rate
            end = min(len(audio), run_end * frame_size) / sample_rate
            duration = end - start
            if duration >= min_pause_seconds:
                pauses.append(Pause(
                    start=round(start, 2),
                    end=round(end, 2),
                    duration=round(duration, 2),
                ))

    return pauses


def localize_pauses(
    pauses: list[Pause],
    start_offset: float,
    end_offset: float,
) -> list[Pause]:
    return [
        Pause(
            start=round(pause.start - start_offset, 2),
            end=round(pause.end - start_offset, 2),
            duration=round(pause.duration, 2),
        )
        for pause in pauses
        if start_offset <= pause.start < end_offset
    ]


class AudioAnalysisService:
    def __init__(self):
        self._wpm_history: list[float] = []
        self._baseline_wpm: float = 0.0
        self._session_filler_counts: dict[str, int] = defaultdict(int)

    def analyze_transcript(
        self, whisper_result: dict
    ) -> tuple[list[FillerWord], SpeedAnalysis, list[Pause], list[ImmediateFeedback]]:
        segments = whisper_result.get("segments", [])
        text = whisper_result.get("text", "").lower().strip()
        audio_duration = whisper_result.get("audio_duration", 0.0)

        filler_words = self._detect_fillers(segments)
        speed = self._analyze_speed(text, audio_duration)
        pauses = self._detect_pauses(segments)
        feedback = self._generate_immediate_feedback(filler_words, speed, pauses)

        return filler_words, speed, pauses, feedback

    def _collect_words(self, segments: list) -> list[dict]:
        words_data: list[dict] = []
        for seg in segments:
            words_data.extend(seg.get("words", []))
        return words_data

    def _normalize_word(self, word: str) -> str:
        return word.strip().lower().strip(WORD_STRIP_CHARS)

    def _detect_fillers(self, segments: list) -> list[FillerWord]:
        found: list[FillerWord] = []
        words_data = self._collect_words(segments)

        for i, w in enumerate(words_data):
            word = self._normalize_word(w.get("word", ""))

            if word in FILLER_WORDS:
                self._session_filler_counts[word] += 1
                found.append(FillerWord(
                    word=word,
                    timestamp=w.get("start", 0.0),
                    count=self._session_filler_counts[word],
                ))

            if i < len(words_data) - 1:
                next_word = self._normalize_word(words_data[i + 1].get("word", ""))
                bigram = f"{word} {next_word}"
                if bigram in FILLER_WORDS:
                    self._session_filler_counts[bigram] += 1
                    found.append(FillerWord(
                        word=bigram,
                        timestamp=w.get("start", 0.0),
                        count=self._session_filler_counts[bigram],
                    ))

        return found

    def _analyze_speed(self, text: str, audio_duration: float) -> SpeedAnalysis:
        # WPM is over the actual audio window (including pauses), not the
        # span of Whisper's segment timestamps — VAD compresses those and
        # produced absurd values like 1200+ WPM on short bursts.
        if audio_duration < 1.0 or not text:
            return SpeedAnalysis(
                current_wpm=0,
                baseline_wpm=self._baseline_wpm,
                is_spike=False,
                spike_factor=1.0,
            )

        total_words = len(text.split())
        current_wpm = total_words / audio_duration * 60

        self._wpm_history.append(current_wpm)

        if len(self._wpm_history) >= 3 and self._baseline_wpm == 0:
            self._baseline_wpm = sum(self._wpm_history[:3]) / 3

        baseline = self._baseline_wpm or current_wpm
        spike_factor = current_wpm / baseline if baseline > 0 else 1.0
        is_spike = spike_factor > 1.35 and current_wpm > 120

        return SpeedAnalysis(
            current_wpm=round(current_wpm, 1),
            baseline_wpm=round(baseline, 1),
            is_spike=is_spike,
            spike_factor=round(spike_factor, 2),
        )

    def _detect_pauses(self, segments: list) -> list[Pause]:
        pauses: list[Pause] = []

        words_data = self._collect_words(segments)
        if len(words_data) >= 2:
            for prev, current in zip(words_data, words_data[1:]):
                gap_start = float(prev.get("end", 0.0) or 0.0)
                gap_end = float(current.get("start", 0.0) or 0.0)
                duration = gap_end - gap_start
                if duration >= 0.8:
                    pauses.append(Pause(
                        start=round(gap_start, 2),
                        end=round(gap_end, 2),
                        duration=round(duration, 2),
                    ))
            return pauses

        for i in range(len(segments) - 1):
            gap_start = segments[i].get("end", 0)
            gap_end = segments[i + 1].get("start", 0)
            duration = gap_end - gap_start
            if duration >= 0.8:
                pauses.append(Pause(
                    start=gap_start,
                    end=gap_end,
                    duration=round(duration, 2),
                ))
        return pauses

    def _generate_immediate_feedback(
        self,
        fillers: list[FillerWord],
        speed: SpeedAnalysis,
        pauses: list[Pause],
    ) -> list[ImmediateFeedback]:
        feedback: list[ImmediateFeedback] = []

        if speed.is_spike:
            pct = int((speed.spike_factor - 1) * 100)
            feedback.append(ImmediateFeedback(
                message=f"You're speaking {pct}% faster than your baseline — take a breath",
                type="speed",
                severity="warning",
            ))

        if len(fillers) >= 2:
            unique = list({f.word for f in fillers})
            feedback.append(ImmediateFeedback(
                message=f"Watch the '{unique[0]}' — try pausing instead",
                type="filler",
                severity="info",
            ))

        long_pauses = [p for p in pauses if p.duration >= 2.0]
        if long_pauses:
            feedback.append(ImmediateFeedback(
                message="Good use of pausing — that builds gravitas",
                type="breath",
                severity="info",
            ))

        return feedback

    def suggest_breath_control(
        self, speed: SpeedAnalysis, pauses: list[Pause]
    ) -> BreathAdvice:
        if speed.is_spike and not pauses:
            return BreathAdvice(
                should_pause=True,
                suggested_pause_location="at the next comma or period",
                reason="You're rushing — a 1-2 second pause lets your audience absorb what you said",
            )
        return BreathAdvice(should_pause=False)
