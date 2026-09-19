"""One local WAV transcription, dry-run by default. Never prints transcript or audio."""
import argparse
import json
from pathlib import Path
import sys

if __package__ in {None, ''}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.ai.voice_transcription import read_voice_config, OpenAITranscriptionProvider, audio_duration


def main(argv=None, *, config=None, provider=None, output=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio', type=Path)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--confirm-external-ai', action='store_true')
    args = parser.parse_args(argv)
    cfg = config or read_voice_config()
    data, duration = b'', None
    if args.audio:
        try:
            if args.audio.stat().st_size > 10 * 1024 * 1024:
                raise ValueError()
            data = args.audio.read_bytes()
            duration = audio_duration(data)
        except Exception:
            print(json.dumps(dict(status='invalid_audio', executed_requests=0)), file=output or sys.stdout)
            return 2
    authorized = args.live and args.confirm_external_ai and cfg.transcription_enabled
    print(json.dumps(dict(provider='openai', model=cfg.model or None, duration=duration,
        audio_present=bool(data), authorized=bool(authorized), planned_requests=1,
        executed_requests=0, mode='live_requested' if args.live else 'dry_run')), file=output or sys.stdout)
    if not args.live:
        return 0
    if not authorized or not data or not cfg.model:
        return 2
    result = (provider or OpenAITranscriptionProvider(cfg)).transcribe(data, {}, allow_external_transcription=True)
    print(json.dumps(dict(status=result.status, issue_codes=result.issue_codes,
        request_id=result.request_id, duration=result.duration)), file=output or sys.stdout)
    return 0 if result.status == 'succeeded' else 1


if __name__ == '__main__':
    raise SystemExit(main())
