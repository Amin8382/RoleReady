from fastapi import APIRouter, UploadFile, File, HTTPException, status
from ..schemas.audio import STTResponse, TTSRequest, TTSResponse
from ..integrations.khaled_voice import transcribe_audio_whisper, synthesize_speech_kokoro

router = APIRouter(tags=["Voice & Audio Adapters"])


@router.post("/stt/transcribe", response_model=STTResponse)
async def transcribe_audio(file: UploadFile = File(...)):
    """
    Adapter endpoint for Khaled (Frontend):
    Uploads candidate voice recording, invokes Whisper small English,
    and returns initial transcript for candidate review.
    """
    if not file:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No audio file uploaded")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded audio file is empty")

    res = await transcribe_audio_whisper(content, filename=file.filename or "recording.wav")
    return STTResponse(**res)


@router.post("/tts/speak", response_model=TTSResponse)
async def speak_text(payload: TTSRequest):
    """
    Adapter endpoint for Khaled (Frontend):
    Converts question text into speech using Kokoro 82M English voice profile.
    """
    if not payload.text or len(payload.text.strip()) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Text must not be empty")

    res = await synthesize_speech_kokoro(payload.text, voice_name=payload.voice_name)
    return TTSResponse(**res)

