"""Private, OpenAI-compatible dictation gateway. Audio is processed in RAM."""
import asyncio
import io
import json
import os
from pathlib import Path
import secrets
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'work'
# Windows NVIDIA wheel DLLs must be visible before CTranslate2 is imported.
DLL_HANDLES = []
for directory in (WORK / 'venv/Lib/site-packages/nvidia').glob('*/bin'):
    os.environ['PATH'] = str(directory) + os.pathsep + os.environ.get('PATH', '')
    DLL_HANDLES.append(os.add_dll_directory(str(directory)))

import httpx
import numpy as np
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form, Depends
from fastapi.responses import PlainTextResponse, FileResponse
from faster_whisper import WhisperModel
from faster_whisper.audio import decode_audio
from opencc import OpenCC

PROMPT = (Path(__file__).parent / 'formatting.txt').read_text(encoding='utf-8')
KEY_PATH = WORK / 'local-voice.key'
if not KEY_PATH.exists():
    KEY_PATH.write_text(secrets.token_urlsafe(32), encoding='ascii')
API_KEY = KEY_PATH.read_text(encoding='ascii').strip()
app = FastAPI(title='Local Voice', docs_url=None, redoc_url=None, openapi_url=None)
converter = OpenCC('s2twp')
model = None
gpu_lock = asyncio.Lock()
MAX_BYTES = 25 * 1024 * 1024

async def authorize(request: Request):
    value = request.headers.get('authorization', '')
    if not secrets.compare_digest(value, 'Bearer ' + API_KEY):
        raise HTTPException(401, 'Invalid local access key')

@app.middleware('http')
async def size_limit(request, call_next):
    if request.url.path.startswith('/v1/') and not secrets.compare_digest(
            request.headers.get('authorization', ''), 'Bearer ' + API_KEY):
        return PlainTextResponse('Invalid local access key', status_code=401)
    try:
        if int(request.headers.get('content-length', 0)) > MAX_BYTES:
            return PlainTextResponse('Recording too large (25 MB maximum)', status_code=413)
    except ValueError:
        return PlainTextResponse('Invalid content length', status_code=400)
    # No unbounded/chunked uploads through the private phone gateway.
    if request.method == 'POST' and 'content-length' not in request.headers:
        return PlainTextResponse('Content-Length required', status_code=411)
    return await call_next(request)

@app.get('/')
async def test_page():
    return FileResponse(Path(__file__).parent / 'phone.html', headers={
        'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer',
        'X-Content-Type-Options': 'nosniff'})

@app.get('/download/localvoice.apk')
async def android_apk():
    apk = Path(__file__).parent.parent / 'android/DreamType-0.2.0.apk'
    if not apk.exists():
        raise HTTPException(404, 'Android package is not ready')
    return FileResponse(apk, filename='DreamType-0.2.0.apk',
        media_type='application/vnd.android.package-archive',
        headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})

@app.on_event('startup')
async def load_model():
    global model
    model = await asyncio.to_thread(WhisperModel, str(WORK / 'models/whisper-turbo'),
        device='cuda', compute_type='int8_float16', cpu_threads=4, num_workers=1)

@app.get('/health')
async def health():
    llm_ready = False
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            llm_ready = (await client.get('http://127.0.0.1:19871/health')).status_code == 200
    except httpx.HTTPError:
        pass
    return {'status': 'ready' if model is not None and llm_ready else 'starting',
            'speech_ready': model is not None, 'formatting_ready': llm_ready,
            'processing': 'local', 'version': 1}

async def format_text(text):
    if not text.strip():
        return ''
    async with httpx.AsyncClient(timeout=90) as client:
        result = await client.post('http://127.0.0.1:19871/v1/chat/completions',
            headers={'Authorization': 'Bearer ' + API_KEY}, json={
            'model': 'local-format', 'messages': [
                {'role': 'system', 'content': PROMPT},
                {'role': 'user', 'content': text}],
            'temperature': 0.1, 'max_tokens': 2048, 'stream': False,
            'chat_template_kwargs': {'enable_thinking': False}})
        result.raise_for_status()
        content = result.json()['choices'][0]['message']['content']
        if not isinstance(content, str) or not content.strip():
            raise ValueError('Empty formatting result')
        return converter.convert(content.strip())

def recognize(audio, language, prompt):
    segments, info = model.transcribe(audio, language=language, beam_size=1,
        vad_filter=True, vad_parameters={'min_silence_duration_ms': 350},
        condition_on_previous_text=False, initial_prompt=prompt)
    text = ''.join(segment.text for segment in segments).strip()
    return converter.convert(text), info.language

async def acquire():
    try:
        await asyncio.wait_for(gpu_lock.acquire(), timeout=5)
    except TimeoutError:
        raise HTTPException(429, 'Previous recording is still processing; please retry')

@app.get('/v1/models', dependencies=[Depends(authorize)])
async def models():
    return {'object': 'list', 'data': [{'id': name, 'object': 'model', 'owned_by': 'local'}
        for name in ['local-dictation', 'local-raw', 'local-format']]}

@app.post('/v1/audio/transcriptions', dependencies=[Depends(authorize)])
async def transcribe(file: UploadFile = File(...), model: str = Form('local-dictation'),
                     language: str = Form('zh'), response_format: str = Form('json'),
                     prompt: str = Form('以下為台灣繁體中文，可能包含英文專有名詞。')):
    started = time.perf_counter()
    try:
        data = await file.read(MAX_BYTES + 1)
    finally:
        await file.close()
    if not data or len(data) > MAX_BYTES:
        raise HTTPException(413, 'Empty recording or recording too large')
    try:
        audio = await asyncio.to_thread(decode_audio, io.BytesIO(data), sampling_rate=16000)
    except Exception:
        raise HTTPException(400, 'Unable to decode recording')
    duration = len(audio) / 16000
    if duration > 360:
        raise HTTPException(413, 'Recording exceeds six minutes')
    await acquire()
    try:
        speech_start = time.perf_counter()
        raw, detected = await asyncio.to_thread(recognize, audio,
            None if language in ('', 'auto') else language, prompt[:2000])
        speech_seconds = time.perf_counter() - speech_start
        format_start = time.perf_counter()
        text, warning = raw, None
        if raw and model != 'local-raw':
            try:
                text = await format_text(raw)
            except (httpx.HTTPError, ValueError, KeyError, IndexError):
                warning = 'Formatting unavailable; returning original transcription'
        timings = {'speech_seconds': round(speech_seconds, 3),
                   'format_seconds': round(time.perf_counter() - format_start, 3),
                   'total_seconds': round(time.perf_counter() - started, 3)}
        headers = {'X-Local-Total-Seconds': str(timings['total_seconds'])}
        if warning:
            headers['X-Local-Warning'] = warning
        if response_format == 'text':
            return PlainTextResponse(text, headers=headers)
        return {'text': text, 'raw_text': raw, 'language': detected,
                'duration': duration, 'timings': timings, 'warning': warning}
    finally:
        gpu_lock.release()

@app.post('/v1/chat/completions', dependencies=[Depends(authorize)])
async def cleanup(request: Request):
    body = await request.json()
    messages = body.get('messages', [])
    text = next((m.get('content', '') for m in reversed(messages) if m.get('role') == 'user'), '')
    if not isinstance(text, str) or len(text) > 12000:
        raise HTTPException(400, 'Expected a transcript shorter than 12000 characters')
    if body.get('stream'):
        raise HTTPException(400, 'Streaming is not enabled for this private formatter')
    await acquire()
    try:
        result = await format_text(text)
        return {'id': 'local-' + secrets.token_hex(6), 'object': 'chat.completion',
            'created': int(time.time()), 'model': 'local-format',
            'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': result},
                         'finish_reason': 'stop'}]}
    finally:
        gpu_lock.release()
