"""Host-only tested translation offload choices, independent of phone settings."""
import json
from pathlib import Path


def gpu_layers(work, speech_profile='turbo'):
    path=Path(work)/'translation-profile.json'
    if not path.exists():return 10
    value=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value,dict) or set(value)!={'gpu_layers'}:
        raise ValueError('translation-profile.json requires only gpu_layers')
    layers=value['gpu_layers']
    if type(layers) is not int or layers not in (10,16):
        raise ValueError('translation gpu_layers must be 10 or 16')
    # The larger optional ASR was only measured with the original 10 layers.
    return layers if speech_profile=='turbo' else 10
