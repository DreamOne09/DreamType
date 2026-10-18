"""Private framed PCM worker. Model stays warm; no network or file audio input."""
import json
import os
from pathlib import Path
import sys


def recognize(model, audio, language, prompt):
    segments, info = model.transcribe(audio, language=language, beam_size=1,
        vad_filter=True, vad_parameters={'min_silence_duration_ms': 350},
        condition_on_previous_text=False, hotwords=prompt)
    return ''.join(segment.text for segment in segments).strip(), info.language


def main():
    if len(sys.argv) != 3:
        return 2
    if sys.platform == 'linux':
        import ctypes
        libc = ctypes.CDLL(None, use_errno=True)
        libc.prctl.argtypes = [ctypes.c_int] + [ctypes.c_ulong] * 4
        libc.prctl.restype = ctypes.c_int
        if libc.prctl(1, 9, 0, 0, 0) != 0 or os.getppid() != int(sys.argv[2]):
            return 2
    # Isolated Python still uses the venv; explicitly retain DLL directory handles.
    handles = []
    for directory in (Path(sys.prefix) / 'Lib/site-packages/nvidia').glob('*/bin'):
        if os.name == 'nt':
            handles.append(os.add_dll_directory(str(directory)))
    import numpy as np
    from faster_whisper import WhisperModel
    model = WhisperModel(sys.argv[1], device='cuda', compute_type='int8_float16',
                         cpu_threads=4, num_workers=1, local_files_only=True)
    def respond(value):
        sys.stdout.buffer.write(json.dumps(value, ensure_ascii=True).encode() + b'\n')
        sys.stdout.buffer.flush()
    respond({'ready': True})
    while True:
        line = sys.stdin.buffer.readline(65537)
        if not line:
            return 0
        if len(line) > 65536 or not line.endswith(b'\n'):
            return 2
        header = json.loads(line)
        size = header['bytes']
        if not isinstance(size, int) or not 0 < size <= 360 * 16000 * 4 or size % 4:
            return 2
        pcm = sys.stdin.buffer.read(size)
        if len(pcm) != size:
            return 2
        audio = np.frombuffer(pcm, dtype='<f4')
        if not np.isfinite(audio).all():
            return 2
        text, language = recognize(model, audio, header['language'], header['prompt'])
        respond({'text': text, 'language': language})


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        sys.exit(2)  # Never log audio, prompt, transcript or model exception contents.
