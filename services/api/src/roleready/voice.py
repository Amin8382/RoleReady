"""Lazy local voice adapters. Audio stays in memory and is never logged."""

import json
from io import BytesIO
from threading import Lock

from roleready.paths import ROOT
from roleready.schemas import ServiceError


class Voice:
    def __init__(self, enabled: bool):
        self.enabled, self.asr, self.tts, self.voice = enabled, None, None, None
        self.lock = Lock()

    def require_enabled(self):
        if not self.enabled:
            raise ServiceError(
                "voice_disabled", "Voice models are not connected. You can type your answer instead."
            )

    def transcribe(self, content: bytes) -> str:
        self.require_enabled()
        with self.lock:
            try:
                from faster_whisper import WhisperModel
                from faster_whisper.audio import decode_audio
                from huggingface_hub import snapshot_download
                import numpy as np

                model_id = "Systran/faster-whisper-small.en"
                config = json.loads((ROOT / "configs/models.json").read_text())[model_id]
                # Decode and validate before loading weights or starting inference.
                audio = decode_audio(BytesIO(content), sampling_rate=16000)
                if len(audio) > 16000 * 180:
                    raise ServiceError("audio_duration", "Keep each answer under three minutes.", 413)
                if len(audio) < 8000 or float(np.max(np.abs(audio))) < 0.001:
                    raise ServiceError("no_speech", "No usable speech was found. Try recording again.", 422)
                if self.asr is None:
                    path = snapshot_download(model_id, revision=config["revision"])
                    self.asr = WhisperModel(path, device="cpu", compute_type="int8", cpu_threads=4)
                segments, _ = self.asr.transcribe(
                    audio, language="en", vad_filter=True, condition_on_previous_text=False, beam_size=5
                )
                text = " ".join(segment.text.strip() for segment in segments).strip()
                if not text:
                    raise ServiceError(
                        "no_speech", "No speech was detected. Try again or type your answer.", 422
                    )
                if len(text) > 8000:
                    raise ServiceError(
                        "transcript_limit", "The transcript is too long. Try a shorter answer.", 413
                    )
                return text
            except ServiceError:
                raise
            except Exception as exc:
                raise ServiceError(
                    "transcription_unavailable",
                    "Transcription is unavailable. Check the voice installation, or type your answer.",
                ) from exc

    def speak(self, text: str) -> bytes:
        self.require_enabled()
        with self.lock:
            try:
                import numpy as np
                import soundfile as sf
                import torch
                from huggingface_hub import hf_hub_download
                from kokoro import KModel, KPipeline

                model_id = "hexgrad/Kokoro-82M"
                config = json.loads((ROOT / "configs/models.json").read_text())[model_id]
                if self.tts is None:
                    kwargs = {"repo_id": model_id, "revision": config["revision"]}
                    model_config = hf_hub_download(filename="config.json", **kwargs)
                    weights = hf_hub_download(filename="kokoro-v1_0.pth", **kwargs)
                    voice = hf_hub_download(filename="voices/af_heart.pt", **kwargs)
                    model = KModel(repo_id=model_id, config=model_config, model=weights).to("cpu").eval()
                    self.tts = KPipeline(lang_code="a", repo_id=model_id, model=model, device="cpu")
                    self.voice = torch.load(voice, map_location="cpu", weights_only=True)
                chunks = [audio.numpy() for _, _, audio in self.tts(text[:2200], voice=self.voice, speed=1)]
                if not chunks:
                    raise ValueError("Empty audio")
                output = BytesIO()
                sf.write(output, np.concatenate(chunks), 24000, format="WAV")
                return output.getvalue()
            except Exception as exc:
                raise ServiceError(
                    "speech_unavailable",
                    "Question audio is unavailable. You can read the question on screen.",
                ) from exc
