"""Run native codecs in a bounded, killable child, without shell or disk audio."""
import math
import os
from pathlib import Path
import subprocess
import sys
import threading
from beta_store import StoreError
from child_lifetime import attach

WORKER=Path(__file__).with_name('audio_worker.py')
TIMEOUT=12


def run_worker(data,mode):
    if mode not in ('duration','pcm'):raise ValueError('Unknown decoder mode')
    maximum=(2 if mode=='duration' else 25)*1024*1024
    if not data or len(data)>maximum:raise ValueError('Invalid recording size')
    timed_out=threading.Event()
    with subprocess.Popen([sys.executable,'-I',str(WORKER),mode,str(os.getpid())],stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0) as child:
        try:close_job=attach(child)
        except Exception:
            child.kill();child.wait()
            raise StoreError(503,'錄音檢查程序無法啟動，請稍後重試。','decoder_unavailable')
        def expire():
            if child.poll() is None:
                timed_out.set()
                try:child.kill()
                except ProcessLookupError:pass
        # Windows communicate(input=...) can block in a pipe write before its
        # timeout wait begins. An independent timer also covers that input phase.
        timer=threading.Timer(TIMEOUT,expire);timer.daemon=True;started=False
        try:
            timer.start();started=True
            output,_=child.communicate(data)
        finally:
            timer.cancel()
            if started:timer.join()
            try:
                if child.poll() is None:child.kill()
                child.wait()
            finally:
                if close_job:close_job()
    if timed_out.is_set():
        raise StoreError(503,'錄音檢查逾時，請稍後重試或改錄較短的一段。','decode_timeout')
    if child.returncode==3:raise StoreError(413,'每段錄音超過允許長度')
    if child.returncode!=0:raise ValueError('Unable to decode recording')
    return output


def isolated_audio_duration(data):
    raw=run_worker(data,'duration')
    if len(raw)>64:raise ValueError('Invalid duration response')
    duration=float(raw)
    if not math.isfinite(duration) or duration<=0:raise ValueError('Invalid duration response')
    return duration


def isolated_pcm(data):
    raw=run_worker(data,'pcm')
    if not raw or len(raw)%2 or len(raw)>360*16000*2:raise ValueError('Invalid PCM response')
    return raw
