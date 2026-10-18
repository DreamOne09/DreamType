"""Resident speech model with a hard process deadline, including pipe writes.

Only one caller owns the child. On timeout it is killed and reaped before a
replacement can be created; cancelling an HTTP request cannot orphan GPU work.
No audio or transcript is written to disk or stderr.
"""
import json
import asyncio
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

from child_lifetime import attach


class SpeechUnavailable(RuntimeError):
    pass


async def finish_before_cancel(function, *args):
    """Hold the caller's GPU lock until the bounded thread has really finished."""
    task = asyncio.create_task(asyncio.to_thread(function, *args))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                continue
            except Exception:
                break
        if task.done() and not task.cancelled():
            task.exception()  # Retrieve a failed worker result, without exposing it.
        raise


class SpeechProcess:
    def __init__(self, model_path, *, timeout=60, startup_timeout=60, command=None):
        self.command = command or [sys.executable, '-I',
            str(Path(__file__).with_name('speech_worker.py')), str(model_path), str(os.getpid())]
        self.timeout = timeout
        self.startup_timeout = startup_timeout
        self.child = None
        self.close_job = None
        self.lock = threading.Lock()
        self.stage = 'stopped'
        self.started_at = None
        self.failures = 0

    def status(self):
        age = time.monotonic() - self.started_at if self.started_at is not None else 0
        limit = self.startup_timeout if self.stage == 'loading' else self.timeout
        alive = self.child is not None and self.child.poll() is None
        return {'ready': alive and self.stage in ('idle', 'recognizing') and age < limit,
                'stage': self.stage, 'elapsed_seconds': round(age, 1), 'failures': self.failures}

    def _stop(self):
        child, job = self.child, self.close_job
        # Retain ownership if termination fails: never start a second GPU worker.
        if child is not None:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=10)
            for pipe in (child.stdin, child.stdout):
                if pipe is not None:
                    pipe.close()
        if job:
            job()
        self.child = self.close_job = None
        self.stage = 'stopped'
        self.started_at = None

    def close(self):
        with self.lock:
            self._stop()

    def _bounded(self, action, timeout, stage):
        self.stage, self.started_at = stage, time.monotonic()
        expired = threading.Event()
        child = self.child
        def expire():
            expired.set()
            if child.poll() is None:
                try:
                    child.kill()
                except ProcessLookupError:
                    pass
        timer = threading.Timer(timeout, expire)
        timer.daemon = True
        try:
            timer.start()
            result = action()
            timer.cancel()
            timer.join()
            if expired.is_set():
                raise SpeechUnavailable('Speech deadline exceeded')
            self.stage, self.started_at = 'idle', None
            return result
        except Exception:
            self.failures += 1
            self._stop()
            raise SpeechUnavailable('Speech worker unavailable; retry recording') from None
        finally:
            timer.cancel()
            timer.join()

    def _read(self):
        raw = self.child.stdout.readline(1024 * 1024 + 1)
        if not raw.endswith(b'\n') or len(raw) > 1024 * 1024:
            raise SpeechUnavailable('Invalid speech response')
        return json.loads(raw)

    def _start(self):
        if self.child is not None and self.child.poll() is None:
            return
        self._stop()
        self.child = subprocess.Popen(self.command, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        try:
            self.close_job = attach(self.child)
            ready = self._bounded(self._read, self.startup_timeout, 'loading')
            if ready != {'ready': True}:
                raise SpeechUnavailable('Speech startup failed')
        except Exception:
            self._stop()
            raise

    def start(self):
        with self.lock:
            self._start()

    def recognize(self, pcm, language, prompt):
        if not pcm or len(pcm) % 4 or len(pcm) > 360 * 16000 * 4:
            raise ValueError('Invalid speech PCM')
        header = json.dumps({'bytes': len(pcm), 'language': language, 'prompt': prompt}).encode() + b'\n'
        if len(header) > 65536:
            raise ValueError('Speech hints too large')
        with self.lock:
            self._start()
            def request():
                self.child.stdin.write(header)
                self.child.stdin.write(pcm)
                self.child.stdin.flush()
                result = self._read()
                if (not isinstance(result, dict) or not isinstance(result.get('text'), str)
                        or not isinstance(result.get('language'), str)):
                    raise SpeechUnavailable('Invalid speech result')
                return result['text'], result['language']
            return self._bounded(request, self.timeout, 'recognizing')
