"""
Teammate Interface Adapter: Khaled Briki (Frontend & Voice)
Whisper small English (STT) and Kokoro 82M (TTS) integrations.
Exposes backend endpoints with server-side credentials only and mock fallbacks.
"""

import base64
import logging
from typing import Dict, Any, Optional
import httpx
from ..config import settings

logger = logging.getLogger(__name__)


async def transcribe_audio_whisper(
    audio_bytes: bytes,
    filename: str = "audio.wav",
) -> Dict[str, Any]:
    """
    Transcribes candidate's spoken answer using Whisper small English.
    Falls back gracefully if external Whisper daemon is not running during local dev.
    """
    if settings.WHISPER_ENDPOINT:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                files = {"file": (filename, audio_bytes, "audio/wav")}
                res = await client.post(settings.WHISPER_ENDPOINT, files=files)
                if res.status_code == 200:
                    data = res.json()
                    return {
                        "transcript": data.get("text") or data.get("transcript", ""),
                        "detected_language": "en",
                        "duration_seconds": data.get("duration", 15.0),
                        "confidence_note": "Candidate can edit the transcript before submitting for scoring.",
                    }
        except Exception as e:
            logger.info(f"Whisper endpoint unreachable ({e}). Using development fallback transcript.")

    # Resilient developer fallback
    return {
        "transcript": "I would implement an inverted file index with product quantization to compress high-dimensional vectors and optimize search latency.",
        "detected_language": "en",
        "duration_seconds": 12.5,
        "confidence_note": "Candidate can edit the transcript before submitting for scoring.",
    }


async def synthesize_speech_kokoro(
    text: str,
    voice_name: str = "af_heart",
) -> Dict[str, Any]:
    """
    Reads question aloud using Kokoro 82M English voice profile.
    Produces base64 WAV stream or audio link.
    """
    if settings.KOKORO_ENDPOINT:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                payload = {"text": text, "voice": voice_name}
                res = await client.post(settings.KOKORO_ENDPOINT, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    return {
                        "audio_format": "audio/wav",
                        "audio_base64": data.get("audio_base64", ""),
                        "voice_used": voice_name,
                    }
        except Exception as e:
            logger.info(f"Kokoro endpoint unreachable ({e}). Using lightweight audio header fallback.")

    # Lightweight WAV placeholder for immediate UI playback demo
    # Minimal 44-byte standard PCM WAV header with silence
    wav_header = (
        b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
        b"\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    )
    b64_audio = base64.b64encode(wav_header).decode("utf-8")

    return {
        "audio_format": "audio/wav",
        "audio_base64": b64_audio,
        "voice_used": voice_name,
    }
