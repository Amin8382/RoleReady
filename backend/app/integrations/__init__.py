"""Teammate integrations and adapter stubs."""

from .amin_pipeline import (
    run_cv_job_analysis,
    generate_seven_questions,
    generate_cheat_sheet,
)
from .khaled_voice import (
    transcribe_audio_whisper,
    synthesize_speech_kokoro,
)

__all__ = [
    "run_cv_job_analysis",
    "generate_seven_questions",
    "generate_cheat_sheet",
    "transcribe_audio_whisper",
    "synthesize_speech_kokoro",
]
