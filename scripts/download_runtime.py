from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1] / 'work'
ROOT.mkdir(exist_ok=True)
os.environ['HF_HOME'] = str(ROOT / 'hf-cache')
os.environ['HF_HUB_DISABLE_XET'] = '1'
from huggingface_hub import hf_hub_download, snapshot_download

def speech():
    snapshot_download('mobiuslabsgmbh/faster-whisper-large-v3-turbo',
        local_dir=ROOT / 'models/whisper-turbo',
        allow_patterns=['*.json', 'model.bin', '*.txt'])
    print('Speech model downloaded', flush=True)

def llm():
    hf_hub_download('lmstudio-community/Qwen3-4B-Instruct-2507-GGUF', 'Qwen3-4B-Instruct-2507-Q4_K_M.gguf',
        local_dir=ROOT / 'models/qwen-instruct')
    print('Formatting model downloaded', flush=True)

def engine():
    tag = 'b11055'
    asset = f'llama-{tag}-bin-win-cuda-12.4-x64.zip'
    url = f'https://github.com/ggml-org/llama.cpp/releases/download/{tag}/{asset}'
    archive = ROOT / asset
    urllib.request.urlretrieve(url, archive)
    with zipfile.ZipFile(archive) as package:
        package.extractall(ROOT / 'llama')
    print('llama.cpp engine downloaded', flush=True)

with ThreadPoolExecutor(max_workers=3) as pool:
    for result in [pool.submit(speech), pool.submit(llm), pool.submit(engine)]:
        result.result()

cloud=ROOT/'cloudflared.exe'
urllib.request.urlretrieve('https://github.com/cloudflare/cloudflared/releases/download/2026.9.1/cloudflared-windows-amd64.exe',cloud)
apk=ROOT.parent/'outputs/android/DreamType-0.3.0.apk'
urllib.request.urlretrieve('https://github.com/DreamOne09/DreamType/releases/download/v0.3.0/DreamType.apk',apk)
if hashlib.sha256(apk.read_bytes()).hexdigest() != 'bf4e99308a2d2a2141c8ba8cd1c0a05e69806e00c9f10aa547456c01e563a492':raise RuntimeError('APK checksum mismatch')
