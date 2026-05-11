import re
import string
from collections import Counter, defaultdict
from math import ceil

import numpy as np

from app.models.session import (
    BreathAdvice,
    FillerWord,
    ImmediateFeedback,
    PaceEvent,
    Pause,
    SpeedAnalysis,
)

HESITATION_FILLERS = (
    (re.compile(r"u+m+"), "um"),
    (re.compile(r"u+h+"), "uh"),
    (re.compile(r"e+r+"), "er"),
    (re.compile(r"e+r+m+"), "erm"),
    (re.compile(r"h+m+"), "hmm"),
    (re.compile(r"m+"), "mm"),
    (re.compile(r"a+h+"), "ah"),
)
PHRASE_FILLERS = {
    ("you", "know"): "you know",
    ("sort", "of"): "sort of",
    ("kind", "of"): "kind of",
    ("i", "mean"): "i mean",
}
STARTING_FILLERS = {
    "so", "well", "basically", "literally", "actually",
    "honestly", "anyway",
}
TERMINAL_BREAK_CHARS = ",.;:!?"
BREAK_GAP_SECONDS = 0.35
SEMANTIC_SO_NEXT = {"that", "much", "many", "far", "long"}
SEMANTIC_OKAY_NEXT = {"with", "for", "to"}
SEMANTIC_PHRASE_PREV = {
    "a", "an", "the", "this", "that", "what", "which", "some", "any",
}
LIKE_SEMANTIC_PREV = {
    "feel", "feels", "felt", "look", "looks", "looked",
    "seem", "seems", "seemed", "sound", "sounds", "sounded",
}
BE_WORDS = {"am", "are", "is", "was", "were", "be", "been", "being"}

WORD_STRIP_CHARS = string.punctuation
PACE_WINDOW_SECONDS = 4.0
PACE_STEP_SECONDS = 2.0
PACE_MIN_BASELINE_WINDOWS = 3
PACE_BASELINE_WINDOWS = 5
PACE_MIN_WORDS_PER_WINDOW = 3
PACE_SPIKE_FACTOR = 1.35
PACE_MIN_FAST_WPM = 120.0


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


def localize_fillers(
    fillers: list[FillerWord],
    start_offset: float,
    end_offset: float,
) -> list[FillerWord]:
    return [
        FillerWord(
            word=filler.word,
            timestamp=round(filler.timestamp - start_offset, 2),
            count=filler.count,
        )
        for filler in fillers
        if start_offset <= filler.timestamp < end_offset
    ]


def detect_pace_events(
    segments: list[dict],
    audio_duration: float = 0.0,
) -> list[PaceEvent]:
    words = _timestamped_words(segments)
    if not words:
        return []

    duration = max(
        float(audio_duration or 0.0),
        max((word["end"] for word in words), default=0.0),
    )
    if duration < PACE_WINDOW_SECONDS:
        return []

    windows = _pace_windows(words, duration)
    baseline_candidates = [
        window for window in windows if len(window["words"]) >= PACE_MIN_WORDS_PER_WINDOW
    ][:PACE_BASELINE_WINDOWS]
    if len(baseline_candidates) < PACE_MIN_BASELINE_WINDOWS:
        return []

    baseline_wpm = sum(window["wpm"] for window in baseline_candidates) / len(baseline_candidates)
    if baseline_wpm <= 0:
        return []

    baseline_ready_at = baseline_candidates[-1]["start"]
    fast_windows = [
        window
        for window in windows
        if window["start"] > baseline_ready_at
        and window["wpm"] >= baseline_wpm * PACE_SPIKE_FACTOR
        and window["wpm"] >= PACE_MIN_FAST_WPM
    ]

    events: list[PaceEvent] = []
    group: list[dict] = []
    for window in fast_windows:
        if group and round(window["start"] - group[-1]["start"], 6) > PACE_STEP_SECONDS:
            events.append(_pace_event_from_windows(group, words, baseline_wpm, duration))
            group = []
        group.append(window)
    if group:
        events.append(_pace_event_from_windows(group, words, baseline_wpm, duration))

    return events


def _timestamped_words(segments: list[dict]) -> list[dict]:
    words: list[dict] = []
    for segment in segments:
        for item in segment.get("words", []):
            text = str(item.get("word", "")).strip()
            if not text:
                continue
            try:
                start = float(item.get("start"))
            except (TypeError, ValueError):
                continue
            try:
                end = float(item.get("end"))
            except (TypeError, ValueError):
                end = start
            if start < 0:
                continue
            words.append({
                "word": text,
                "start": start,
                "end": max(start, end),
            })
    words.sort(key=lambda word: word["start"])
    return words


def _pace_windows(words: list[dict], duration: float) -> list[dict]:
    windows: list[dict] = []
    start = 0.0
    while start < duration:
        end = start + PACE_WINDOW_SECONDS
        window_words = [word for word in words if start <= word["start"] < end]
        windows.append({
            "start": start,
            "end": end,
            "words": window_words,
            "wpm": len(window_words) / PACE_WINDOW_SECONDS * 60,
        })
        start += PACE_STEP_SECONDS
    return windows


def _pace_event_from_windows(
    windows: list[dict],
    words: list[dict],
    baseline_wpm: float,
    duration: float,
) -> PaceEvent:
    start = float(windows[0]["start"])
    end = min(duration, float(windows[-1]["end"]))
    peak_wpm = max(float(window["wpm"]) for window in windows)
    event_words = [word["word"] for word in words if start <= word["start"] < end]
    excerpt_words = event_words[:16]
    excerpt = " ".join(excerpt_words).strip()
    if len(event_words) > len(excerpt_words):
        excerpt = f"{excerpt}..."

    return PaceEvent(
        start_seconds=round(start, 2),
        end_seconds=round(end, 2),
        wpm=round(peak_wpm, 1),
        baseline_wpm=round(baseline_wpm, 1),
        spike_factor=round(peak_wpm / baseline_wpm, 2),
        excerpt=excerpt,
    )


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

    def detect_fillers(self, segments: list) -> list[FillerWord]:
        return self._detect_fillers(segments)

    def _collect_words(self, segments: list) -> list[dict]:
        words_data: list[dict] = []
        for seg in segments:
            words_data.extend(seg.get("words", []))
        return words_data

    def _normalize_word(self, word: str) -> str:
        normalized = word.strip().lower().strip(WORD_STRIP_CHARS)
        return "okay" if normalized == "ok" else normalized

    def _float_or_none(self, value: object) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _word_start(self, word_data: dict) -> float:
        return self._float_or_none(word_data.get("start")) or 0.0

    def _raw_word(self, word_data: dict) -> str:
        return str(word_data.get("word", ""))

    def _has_trailing_break(self, word_data: dict) -> bool:
        return self._raw_word(word_data).strip().endswith(tuple(TERMINAL_BREAK_CHARS))

    def _word_at(self, words_data: list[dict], index: int) -> str:
        if index < 0 or index >= len(words_data):
            return ""
        return self._normalize_word(self._raw_word(words_data[index]))

    def _gap_before(self, words_data: list[dict], index: int) -> float | None:
        if index <= 0:
            return None
        start = self._float_or_none(words_data[index].get("start"))
        previous_end = self._float_or_none(words_data[index - 1].get("end"))
        if start is None or previous_end is None:
            return None
        return start - previous_end

    def _gap_after(self, words_data: list[dict], index: int) -> float | None:
        if index >= len(words_data) - 1:
            return None
        end = self._float_or_none(words_data[index].get("end"))
        next_start = self._float_or_none(words_data[index + 1].get("start"))
        if end is None or next_start is None:
            return None
        return next_start - end

    def _is_boundary_before(self, words_data: list[dict], index: int) -> bool:
        if index == 0:
            return True
        gap = self._gap_before(words_data, index)
        return self._has_trailing_break(words_data[index - 1]) or (
            gap is not None and gap >= BREAK_GAP_SECONDS
        )

    def _has_break_after(self, words_data: list[dict], index: int) -> bool:
        gap = self._gap_after(words_data, index)
        return self._has_trailing_break(words_data[index]) or (
            gap is not None and gap >= BREAK_GAP_SECONDS
        )

    def _canonical_hesitation(self, word: str) -> str | None:
        for pattern, canonical in HESITATION_FILLERS:
            if pattern.fullmatch(word):
                return canonical
        return None

    def _canonical_phrase_filler(
        self,
        words_data: list[dict],
        index: int,
        phrase: str,
    ) -> str | None:
        previous_word = self._word_at(words_data, index - 1)

        if phrase in {"i mean", "you know"}:
            if self._is_boundary_before(words_data, index) and self._has_break_after(
                words_data,
                index + 1,
            ):
                return phrase
            return None

        if phrase in {"sort of", "kind of"} and previous_word in SEMANTIC_PHRASE_PREV:
            return None

        return phrase

    def _canonical_contextual_filler(
        self,
        words_data: list[dict],
        index: int,
        word: str,
    ) -> str | None:
        previous_word = self._word_at(words_data, index - 1)
        next_word = self._word_at(words_data, index + 1)
        boundary_before = self._is_boundary_before(words_data, index)

        if word in STARTING_FILLERS:
            if not boundary_before:
                return None
            if word == "so" and next_word in SEMANTIC_SO_NEXT:
                return None
            return word

        if word == "okay":
            if boundary_before and next_word not in SEMANTIC_OKAY_NEXT:
                return word
            return None

        if word == "right":
            return word if boundary_before else None

        if word == "like":
            if previous_word in LIKE_SEMANTIC_PREV:
                return None
            if previous_word in BE_WORDS:
                return word
            if boundary_before or self._has_break_after(words_data, index):
                return word

        return None

    def _append_filler(
        self,
        found: list[FillerWord],
        word: str,
        timestamp: float,
    ) -> None:
        self._session_filler_counts[word] += 1
        found.append(FillerWord(
            word=word,
            timestamp=timestamp,
            count=self._session_filler_counts[word],
        ))

    def _detect_fillers(self, segments: list) -> list[FillerWord]:
        found: list[FillerWord] = []
        words_data = self._collect_words(segments)

        for i, w in enumerate(words_data):
            word = self._word_at(words_data, i)
            if not word:
                continue

            if i < len(words_data) - 1:
                next_word = self._word_at(words_data, i + 1)
                phrase = PHRASE_FILLERS.get((word, next_word))
                if phrase:
                    contextual_phrase = self._canonical_phrase_filler(words_data, i, phrase)
                    if contextual_phrase:
                        self._append_filler(found, contextual_phrase, self._word_start(w))

            hesitation = self._canonical_hesitation(word)
            if hesitation:
                self._append_filler(found, hesitation, self._word_start(w))
                continue

            contextual = self._canonical_contextual_filler(words_data, i, word)
            if contextual:
                self._append_filler(found, contextual, self._word_start(w))

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
            filler_word = Counter(f.word for f in fillers).most_common(1)[0][0]
            feedback.append(ImmediateFeedback(
                message=f"Watch the '{filler_word}' — try pausing instead",
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
