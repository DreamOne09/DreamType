import asyncio
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest

from speech_process import SpeechProcess, SpeechUnavailable, finish_before_cancel


WORKER = '''import json,sys,time
print(json.dumps({'ready': True}),flush=True)
while True:
    line=sys.stdin.buffer.readline()
    if not line: break
    header=json.loads(line)
    data=sys.stdin.buffer.read(header['bytes'])
    if header['prompt']=='hang': time.sleep(60)
    if header['prompt']=='exit': sys.exit(2)
    if header['prompt']=='bad': print('broken',flush=True); continue
    print(json.dumps({'text': header['prompt'], 'language': header['language']}),flush=True)
'''


class SpeechProcessTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.script = Path(self.directory.name) / 'worker.py'
        self.script.write_text(WORKER, encoding='utf-8')
        self.worker = SpeechProcess('unused', timeout=.3, startup_timeout=3,
            command=[sys.executable, '-I', str(self.script)])

    def tearDown(self):
        self.worker.close()
        self.directory.cleanup()

    def test_resident_child_reused_and_closed(self):
        self.worker.start()
        child = self.worker.child
        for text in ('台灣', '請幫我生成計畫'):
            self.assertEqual(self.worker.recognize(b'\0'*4, 'zh', text), (text, 'zh'))
            self.assertIs(self.worker.child, child)
        self.assertTrue(self.worker.status()['ready'])
        self.worker.close()
        self.assertIsNotNone(child.poll())
        self.assertFalse(self.worker.status()['ready'])

    def test_hang_kills_reaps_then_next_request_recovers(self):
        self.worker.start()
        child = self.worker.child
        start = time.monotonic()
        with self.assertRaises(SpeechUnavailable):
            self.worker.recognize(b'\0'*4, 'zh', 'hang')
        self.assertLess(time.monotonic()-start, 5)
        self.assertIsNotNone(child.poll())
        self.assertFalse(self.worker.status()['ready'])
        self.assertEqual(self.worker.status()['failures'], 1)
        self.assertEqual(self.worker.recognize(b'\0'*4, 'zh', 'recovered'), ('recovered','zh'))
        self.assertNotEqual(child.pid, self.worker.child.pid)

    def test_crash_and_invalid_response_are_recoverable(self):
        for prompt in ('exit', 'bad'):
            with self.assertRaises(SpeechUnavailable):
                self.worker.recognize(b'\0'*4, 'zh', prompt)
            self.assertIsNone(self.worker.child)
            self.assertEqual(self.worker.recognize(b'\0'*4, 'en', 'ok'), ('ok', 'en'))

    def test_startup_deadline(self):
        self.script.write_text('import time; time.sleep(60)', encoding='utf-8')
        self.worker.startup_timeout = .3
        with self.assertRaises(SpeechUnavailable):
            self.worker.start()
        self.assertIsNone(self.worker.child)
        self.assertFalse(self.worker.status()['ready'])

    def test_deadline_covers_blocked_pipe_write(self):
        self.script.write_text("import time; print('{\"ready\": true}',flush=True); time.sleep(60)",encoding='utf-8')
        self.worker.start()
        child = self.worker.child
        with self.assertRaises(SpeechUnavailable):
            self.worker.recognize(b'\0'*(4*16000*10), 'zh', '')
        self.assertIsNotNone(child.poll())

    def test_input_limits_before_worker_start(self):
        for pcm in (b'', b'123', b'\0'*(360*16000*4+4)):
            with self.assertRaises(ValueError):
                self.worker.recognize(pcm, 'zh', '')
        self.assertIsNone(self.worker.child)

    def test_health_does_not_report_overdue_inference_as_ready(self):
        self.worker.start()
        self.worker.stage = 'recognizing'
        self.worker.started_at = time.monotonic() - self.worker.timeout - 1
        self.assertFalse(self.worker.status()['ready'])
        self.worker.started_at = time.monotonic()
        self.assertTrue(self.worker.status()['ready'])


class CancellationTests(unittest.IsolatedAsyncioTestCase):
    async def test_repeated_cancellation_keeps_lock_until_thread_done(self):
        entered, release = threading.Event(), threading.Event()
        lock = asyncio.Lock()
        def work():
            entered.set()
            release.wait(5)
            raise SpeechUnavailable('worker failed')
        async def request():
            async with lock:
                await finish_before_cancel(work)
        task = asyncio.create_task(request())
        while not entered.is_set():
            await asyncio.sleep(.01)
        try:
            for _ in range(2):
                task.cancel()
                await asyncio.sleep(.02)
                self.assertTrue(lock.locked())
                self.assertFalse(task.done())
        finally:
            release.set()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertFalse(lock.locked())
