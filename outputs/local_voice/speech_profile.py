"""Explicit host-side ASR profiles; no client-selected paths or downloads."""
from pathlib import Path

PROFILES = {
    'turbo': 'models/whisper-turbo',
    'breeze': 'models/breeze-asr-25/int8_float16',
}


def speech_model_path(work: Path, profile='turbo'):
    if not isinstance(profile,str) or profile not in PROFILES:
        raise ValueError('DREAMTYPE_ASR_MODEL must be turbo or breeze')
    return work / PROFILES[profile]
