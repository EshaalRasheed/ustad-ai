"""Voice features: turn the learner's speech into text, and Ustad's text into Urdu speech."""
import asyncio
import re

import edge_tts
from google.genai import errors, types

from app import config
from app.llm import QuotaExceeded, _client

# Natural Urdu voices from Microsoft (used by edge-tts):
#   ur-PK-UzmaNeural (female), ur-PK-AsadNeural (male)
DEFAULT_VOICE = "ur-PK-AsadNeural"

# Instructions for transcribing the learner's question.
# Spoken Urdu and Hindi sound almost the same, so AI models sometimes write
# Urdu speech in Hindi (Devanagari) script. We forbid that explicitly.
TRANSCRIBE_PROMPT = (
    "Transcribe exactly what the speaker says in this audio. "
    "The speaker is from Pakistan and speaks Urdu, English, or a mix of both. "
    "Write all Urdu words in Urdu script (Arabic/Nastaliq letters, e.g. سوال، ریاضی). "
    "NEVER use Hindi (Devanagari) script such as 'सवाल'. "
    "Write English words in English letters. "
    "Return only the transcription, nothing else. "
    "If the audio is silent or unclear, return an empty string."
)

# Matches any Hindi (Devanagari) character, used as a safety check
DEVANAGARI = re.compile(r"[\u0900-\u097F]")

TO_URDU_PROMPT = (
    "Rewrite the following text in Urdu script (Arabic/Nastaliq letters). "
    "Keep the meaning and words the same; keep English words in English letters. "
    "Return only the rewritten text.\n\nText: "
)


def transcribe(audio_bytes: bytes, mime_type: str = "audio/wav") -> str:
    """Speech-to-text: send the recording to Gemini and get the words back."""
    try:
        response = _client.models.generate_content(
            model=config.FAST_MODEL,  # transcribing is an easy job: use the lighter model
            contents=[
                types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),  # the audio itself
                TRANSCRIBE_PROMPT,                                             # what to do with it
            ],
            config=types.GenerateContentConfig(temperature=0),  # 0 = most literal, no creativity
        )
    except errors.ClientError as error:
        if error.code == 429:          # free quota used up
            raise QuotaExceeded() from error
        raise
    text = (response.text or "").strip()

    # Safety net: if Hindi script still slipped through, convert it to Urdu script.
    # This costs an extra AI call, but only in the rare cases where it's needed.
    if DEVANAGARI.search(text):
        text = to_urdu_script(text)
    return text


def to_urdu_script(text: str) -> str:
    """Convert text written in Hindi (Devanagari) script into Urdu script."""
    try:
        response = _client.models.generate_content(
            model=config.FAST_MODEL,
            contents=TO_URDU_PROMPT + text,
            config=types.GenerateContentConfig(temperature=0),
        )
    except errors.ClientError as error:
        if error.code == 429:
            raise QuotaExceeded() from error
        raise
    return (response.text or text).strip()


async def speak_async(text: str, voice: str = DEFAULT_VOICE, rate: str = "-10%") -> bytes:
    """Text-to-speech: turn Urdu text into MP3 audio bytes.

    rate="-10%" speaks a little slower than normal, which is easier to follow.
    """
    audio = bytearray()
    # edge-tts sends the audio in small pieces; we collect them into one file
    async for chunk in edge_tts.Communicate(text, voice, rate=rate).stream():
        if chunk["type"] == "audio":
            audio.extend(chunk["data"])
    return bytes(audio)


def speak(text: str, voice: str = DEFAULT_VOICE, rate: str = "-10%") -> bytes:
    """Same as speak_async, but usable from normal (non-async) scripts."""
    return asyncio.run(speak_async(text, voice, rate))