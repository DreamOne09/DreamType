"""Opt-in, single-clip cloud ASR comparison. Never changes the live provider."""
import argparse
import asyncio
import base64
import getpass
import hashlib
import io
import json
import re
import time
import wave
from pathlib import Path

import httpx

MAX_AUDIO = 2_000_000
MAX_RESPONSE = 1_000_000
MODELS = {'cloudflare': '@cf/openai/whisper-large-v3-turbo',
          'groq': 'whisper-large-v3-turbo'}
HINT = '以下為台灣繁體中文，可能包含英文專有名詞。'


class ProbeError(Exception):
    """Only stable codes, never remote bodies, URLs or credentials."""
    def __init__(self, code, status=None):
        super().__init__(code)
        self.code, self.status = code, status


def read_clip(path):
    with Path(path).open('rb') as stream:
        audio = stream.read(MAX_AUDIO + 1)
    if not audio or len(audio) > MAX_AUDIO:
        raise ValueError('Use a WAV smaller than 2 MB')
    with wave.open(io.BytesIO(audio), 'rb') as wav:
        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getcomptype()) != (1, 2, 16000, 'NONE'):
            raise ValueError('Use mono 16 kHz PCM16 WAV')
        frames = wav.getnframes()
        if not 160 <= frames <= 960000 or len(wav.readframes(frames)) != frames * 2:
            raise ValueError('Use a complete WAV lasting 0.01 to 60 seconds')
    return audio, frames / 16000


def request_options(provider, audio, account_id=None):
    if provider == 'cloudflare':
        if not isinstance(account_id, str) or not re.fullmatch('[a-f0-9]{32}', account_id):
            raise ValueError('Cloudflare requires a 32-character account ID')
        return ('https://api.cloudflare.com/client/v4/accounts/' + account_id + '/ai/run/' + MODELS[provider],
                {'json': {'audio': base64.b64encode(audio).decode('ascii'), 'task': 'transcribe',
                          'language': 'zh', 'initial_prompt': HINT}})
    if provider == 'groq':
        return ('https://api.groq.com/openai/v1/audio/transcriptions',
                {'files': {'file': ('clip.wav', audio, 'audio/wav')},
                 'data': {'model': MODELS[provider], 'language': 'zh', 'prompt': HINT,
                          'temperature': '0', 'response_format': 'json'}})
    raise ValueError('Unsupported provider')


async def transcribe(provider, audio, credential, account_id=None, *, transport=None, deadline=60):
    url, options = request_options(provider, audio, account_id)
    if not isinstance(credential, str) or not credential or not credential.isascii() or any(c.isspace() for c in credential):
        raise ValueError('Invalid credential')
    start = time.perf_counter()
    try:
        async with asyncio.timeout(deadline):
            async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=10), transport=transport,
                                         follow_redirects=False, trust_env=False) as client:
                async with client.stream('POST', url, headers={'Authorization': 'Bearer ' + credential}, **options) as response:
                    status = response.status_code
                    if status != 200:
                        code = ('quota_or_rate_limit' if status == 429 else 'authentication' if status in (401, 403)
                                else 'redirect_refused' if 300 <= status < 400 else 'provider_http_error')
                        raise ProbeError(code, status)
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(data) + len(chunk) > MAX_RESPONSE:
                            raise ProbeError('response_too_large', status)
                        data.extend(chunk)
        body = json.loads(data)
        if not isinstance(body, dict): raise ProbeError('invalid_response', status)
        if provider == 'cloudflare':
            if body.get('success') is not True: raise ProbeError('provider_error', status)
            body = body.get('result')
        if not isinstance(body, dict) or not isinstance(body.get('text'), str):
            raise ProbeError('invalid_response', status)
        text = body['text'].strip()
        return {'text': text, 'empty': not bool(text), 'http_status': status,
                'request_seconds': round(time.perf_counter() - start, 3)}
    except (TimeoutError, httpx.TimeoutException):
        raise ProbeError('timeout') from None
    except httpx.HTTPError:
        raise ProbeError('network_error') from None
    except (ValueError, UnicodeError):
        raise ProbeError('invalid_response') from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider', choices=tuple(MODELS), required=True)
    parser.add_argument('--audio', type=Path, required=True)
    parser.add_argument('--account-id')
    parser.add_argument('--upload', action='store_true', help='Authorize one upload of this reviewed clip to the selected provider')
    parser.add_argument('--include-transcript', action='store_true', help='Print returned text; use only with non-private test audio')
    args = parser.parse_args(argv)
    audio, seconds = read_clip(args.audio)
    request_options(args.provider, audio, args.account_id)  # Validate before prompting or connecting.
    report = {'provider': args.provider, 'model': MODELS[args.provider],
              'audio_sha256': hashlib.sha256(audio).hexdigest(), 'audio_seconds': seconds,
              'bytes': len(audio), 'requests': 0, 'status': 'dry_run', 'actual_charge': None}
    if args.upload:
        credential = getpass.getpass('Provider API credential (not saved): ')
        report['requests'] = 1  # Attempted; a timeout does not prove the provider did no work.
        try:
            result = asyncio.run(transcribe(args.provider, audio, credential, args.account_id))
            report.update(status='empty_transcription' if result['empty'] else 'ok',
                          request_seconds=result['request_seconds'], http_status=result['http_status'])
            if args.include_transcript: report['transcript'] = result['text']
        except ProbeError as error:
            report.update(status=error.code, http_status=error.status)
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report['status'] in ('dry_run', 'ok') else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, EOFError, wave.Error):
        print(json.dumps({'status': 'invalid_local_input'}))
        raise SystemExit(1)
