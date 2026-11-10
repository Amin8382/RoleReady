"""On-demand English Whisper transcription and Kokoro question speech.

Optional dependencies are lazy-loaded. These functions load model weights on first
use and may download from Hugging Face. No audio is saved automatically.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

WHISPER_ID = "small.en"
KOKORO_ID = "hexgrad/Kokoro-82M"
MAX_AUDIO_BYTES = 25 * 1024 * 1024
VALID_AUDIO = {".wav", ".mp3", ".m4a", ".flac", ".ogg"}


@dataclass(frozen=True)
class Transcript:
    text: str
    language: str
    model_id: str


def transcribe_english(
    path: Path,
    *,
    model: object | None = None,
    device: str = "cpu",
    compute_type: str = "int8",
) -> Transcript:
    if not path.is_file() or path.suffix.lower() not in VALID_AUDIO:
        raise ValueError("Audio must be an existing .wav, .mp3, .m4a, .flac or .ogg file")
    if not 0 < path.stat().st_size <= MAX_AUDIO_BYTES:
        raise ValueError("Audio must be nonempty and at most 25 MB")
    if model is None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError("Install voice requirements with pip install -e '.[voice]'") from exc
        model = WhisperModel(WHISPER_ID, device=device, compute_type=compute_type)
    segments, _info = model.transcribe(str(path), language="en", vad_filter=True)
    text = " ".join(str(s.text).strip() for s in segments).strip()
    if not text:
        raise ValueError("No intelligible English speech was detected")
    return Transcript(text=text, language="en", model_id=WHISPER_ID)


def synthesize_question(
    text: str,
    output: Path,
    *,
    voice: str = "af_heart",
    pipeline: object | None = None,
    sample_rate: int = 24000,
) -> Path:
    if not 5 <= len(text.strip()) <= 2000:
        raise ValueError("Question text must be 5-2000 characters")
    if output.suffix.lower() != ".wav":
        raise ValueError("Output must be a .wav path")
    if not (voice.startswith("af_") or voice.startswith("am_")):
        raise ValueError("Only English Kokoro voices are supported")
    if pipeline is None:
        try:
            from kokoro import KPipeline
        except ImportError as exc:
            raise RuntimeError("Install voice requirements with pip install -e '.[voice]'") from exc
        pipeline = KPipeline(lang_code="a")
    try:
        import numpy as np
        import soundfile as sf
    except ImportError as exc:
        raise RuntimeError("Install numpy and soundfile for WAV export") from exc
    chunks = []
    for _gs, _ps, audio in pipeline(text, voice=voice, speed=1.0):
        if audio is not None:
            chunks.append(np.asarray(audio, dtype="float32"))
    if not chunks:
        raise RuntimeError("Kokoro did not generate audio")
    output.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output), np.concatenate(chunks), sample_rate)
    return output
