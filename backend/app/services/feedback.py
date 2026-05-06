import anthropic
from app.core.config import settings

_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

_COACH_SYSTEM = """\
You are a professional speech coach analyzing a speaker's transcript in real-time.
Give brief, actionable, encouraging feedback. Be direct but kind.
Max 2 sentences per response.\
"""


async def get_ai_feedback(
    transcript: str,
    filler_count: int,
    avg_wpm: float,
    eye_contact_score: float,
) -> str:
    if not transcript.strip() or len(transcript.split()) < 20:
        return ""

    prompt = (
        f'Transcript chunk: "{transcript}"\n\n'
        f"Metrics:\n"
        f"- Filler words: {filler_count}\n"
        f"- Pace: {avg_wpm:.0f} WPM\n"
        f"- Eye contact: {eye_contact_score:.0%}\n\n"
        "Give one short coaching note (1-2 sentences) on the most impactful thing to improve."
    )

    message = await _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=150,
        system=_COACH_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


async def get_coherence_score(transcript: str) -> float:
    if len(transcript.split()) < 30:
        return 1.0

    prompt = (
        "Rate the coherence of this speech from 0.0 to 1.0.\n"
        "1.0 = clear, on-topic, logical flow. 0.0 = rambling, no clear point.\n\n"
        f'"{transcript}"\n\n'
        "Reply with ONLY a number between 0.0 and 1.0."
    )

    message = await _client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=10,
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        return float(message.content[0].text.strip())
    except ValueError:
        return 0.8
