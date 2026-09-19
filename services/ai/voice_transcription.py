"""Lazy transcription with configuration AND per-action authorization. No audio writes."""
from dataclasses import dataclass
import io
import os
import wave

from models.transcription import TranscriptionResult
from services.ai.openai_semantic_interpreter import _private_transport_logs, _request_id


@dataclass(frozen=True)
class VoiceConfig:
    onboarding_enabled: bool = False
    transcription_enabled: bool = False
    model: str = ''


def setting(name, environ=None, secrets=None):
    raw = (os.environ if environ is None else environ).get(name)
    if raw is None or not str(raw).strip():
        try:
            raw = secrets.get(name) if secrets is not None else None
        except Exception:
            raw = None
    return str(raw).strip() if raw is not None else ''


def read_voice_config(environ=None, secrets=None):
    return VoiceConfig(setting('VOICE_ONBOARDING_ENABLED', environ, secrets).lower() == 'true',
        setting('VOICE_TRANSCRIPTION_ENABLED', environ, secrets).lower() == 'true',
        setting('VOICE_TRANSCRIPTION_MODEL', environ, secrets))


def audio_duration(data):
    if not isinstance(data, bytes) or not data or len(data) > 10 * 1024 * 1024:
        raise ValueError('invalid_audio')
    try:
        with wave.open(io.BytesIO(data), 'rb') as audio:
            duration = audio.getnframes() / audio.getframerate()
            if not 0 < duration <= 180 or audio.getnchannels() not in (1, 2) or audio.getsampwidth() not in (1, 2, 3, 4):
                raise ValueError('invalid_audio')
            if len(audio.readframes(audio.getnframes())) != audio.getnframes() * audio.getnchannels() * audio.getsampwidth():
                raise ValueError('invalid_audio')
            return duration
    except Exception:
        raise ValueError('invalid_audio') from None


class OpenAITranscriptionProvider:
    def __init__(self, config=None, *, transport_factory=None, secrets=None):
        self.config = config or VoiceConfig()
        self._factory = transport_factory or self._transport
        self._secrets = secrets

    def _transport(self):
        from openai import OpenAI
        key = setting('OPENAI_API_KEY', secrets=self._secrets)
        if not key:
            raise ValueError('provider_unavailable')
        client = OpenAI(api_key=key, max_retries=0, timeout=30.0)
        def execute(data, model):
            from openai import APITimeoutError
            try:
                # Transcription, not translation; no language, prompt or biography supplied.
                response = client.audio.transcriptions.create(model=model,
                    file=('answer.wav', data, 'audio/wav'), response_format='json')
            except APITimeoutError:
                raise TimeoutError() from None
            return TranscriptionResult('succeeded', response.text, model=model,
                request_id=_request_id(getattr(response, '_request_id', None)))
        return execute

    def transcribe(self, audio_bytes, metadata=None, *, allow_external_transcription=False):
        def fail(code):
            return TranscriptionResult('failed', issue_codes=(code,))
        if self.config.transcription_enabled is not True:
            return fail('disabled')
        if allow_external_transcription is not True:
            return fail('not_authorized')
        if not self.config.model:
            return fail('model_not_configured')
        try:
            duration = audio_duration(audio_bytes)
        except ValueError:
            return fail('invalid_audio')
        try:
            with _private_transport_logs():
                transport = self._factory()
                result = transport(audio_bytes, self.config.model)
        except TimeoutError:
            return fail('timeout')
        except Exception:
            return fail('provider_unavailable')
        if not isinstance(result, TranscriptionResult) or result.status != 'succeeded' or not isinstance(result.transcript_text, str) or not result.transcript_text.strip() or len(result.transcript_text) > 20000:
            return fail('invalid_response')
        return TranscriptionResult('succeeded', result.transcript_text, model=self.config.model,
            request_id=_request_id(result.request_id), duration=duration)
