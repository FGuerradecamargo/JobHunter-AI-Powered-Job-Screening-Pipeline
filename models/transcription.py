"""Provider-neutral transcription result. Text is an unconfirmed draft."""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class TranscriptionResult:
    status: str
    transcript_text: str = ''
    detected_language: str | None = None
    provider: str = 'openai'
    model: str | None = None
    request_id: str | None = None
    duration: float | None = None
    issue_codes: tuple[str, ...] = ()


class TranscriptionProvider(Protocol):
    def transcribe(self, audio_bytes: bytes, metadata: dict, *, allow_external_transcription: bool = False) -> TranscriptionResult: ...
