from typing import Optional
from pydantic import BaseModel, Field


class STTResponse(BaseModel):
    transcript: str
    detected_language: str = "en"
    duration_seconds: Optional[float] = None
    confidence_note: str = "Candidate can edit the transcript before submitting for scoring."


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=2, max_length=1500, description="Question text to be synthesized into audio")
    voice_name: str = Field(default="af_heart", description="Kokoro 82M voice profile (e.g. af_heart, am_adam)")


class TTSResponse(BaseModel):
    audio_format: str = "audio/wav"
    audio_base64: str = Field(..., description="Base64 encoded audio stream or data URL")
    voice_used: str

