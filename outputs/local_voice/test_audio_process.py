"""Exercise real decoder children, including termination and post-timeout recovery."""
import io
import struct
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import wave
import asyncio
import threading
import os
import sys
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import audio_process
from beta_store import StoreError
from request_limits import DecoderBudget


def wav(seconds=1,rate=16000,extra=0):
    buffer=io.BytesIO()
    with wave.open(buffer,'wb') as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(rate)
        out.writeframes(struct.pack('<h',1234)*(seconds*rate+extra))
    return buffer.getvalue()


class AudioProcessTests(unittest.TestCase):
    def test_duration_preserves_exact_billing_and_over_limit_boundary(self):
        self.assertEqual(audio_process.isolated_audio_duration(wav(120,8000)),120)
        self.assertGreater(audio_process.isolated_audio_duration(wav(120,8000,1)),120)

    def test_pcm_preserves_samples_and_resamples_without_plane_padding(self):
        raw=audio_process.isolated_pcm(wav())
        self.assertEqual(raw,struct.pack('<h',1234)*16000)
        self.assertEqual(len(audio_process.isolated_pcm(wav(1,48000))),16000*2)

    def test_pcm_rejects_long_recording_and_invalid_input(self):
        with self.assertRaises(StoreError) as caught:audio_process.isolated_pcm(wav(361,8000))
        self.assertEqual(caught.exception.status,413)
        for decode in (audio_process.isolated_audio_duration,audio_process.isolated_pcm):
            with self.assertRaises(ValueError):decode(b'invalid recording')

    def test_timeout_kills_real_child_and_next_recording_works(self):
        original=subprocess.Popen;children=[]
        def capture(*args,**kwargs):
            child=original(*args,**kwargs);children.append(child);return child
        with tempfile.TemporaryDirectory() as directory:
            worker=Path(directory)/'blocked_worker.py'
            worker.write_text('import time\ntime.sleep(60)\n')
            started=time.monotonic()
            with patch.object(audio_process,'WORKER',worker),patch.object(audio_process,'TIMEOUT',.2),patch('audio_process.subprocess.Popen',side_effect=capture):
                with self.assertRaises(StoreError) as caught:audio_process.isolated_audio_duration(wav())
                self.assertEqual(caught.exception.code,'decode_timeout')
            self.assertEqual(len(children),1)
            self.assertIsNotNone(children[0].poll())
            self.assertNotEqual(children[0].returncode,0)
            self.assertLess(time.monotonic()-started,3)
        self.assertEqual(audio_process.isolated_audio_duration(wav()),1)

    def test_child_crash_does_not_affect_parent_or_next_recording(self):
        with tempfile.TemporaryDirectory() as directory:
            worker=Path(directory)/'crashed_worker.py';worker.write_text('import os\nos._exit(7)\n')
            with patch.object(audio_process,'WORKER',worker):
                with self.assertRaises(ValueError):audio_process.isolated_pcm(wav())
        self.assertEqual(len(audio_process.isolated_pcm(wav())),32000)

    def test_unexpected_child_output_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            worker=Path(directory)/'bad_worker.py';worker.write_text("import sys\nsys.stdout.buffer.write(b'nan')\n")
            with patch.object(audio_process,'WORKER',worker):
                with self.assertRaises(ValueError):audio_process.isolated_audio_duration(wav())
                with self.assertRaises(ValueError):audio_process.isolated_pcm(wav())

    def test_playlist_does_not_fetch_nested_http_resource(self):
        requests=[]
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append(self.path);self.send_response(404);self.end_headers()
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        playlist=f'#EXTM3U\n#EXT-X-TARGETDURATION:1\n#EXTINF:1,\nhttp://127.0.0.1:{server.server_port}/audio.aac\n#EXT-X-ENDLIST\n'.encode()
        try:
            for decode in (audio_process.isolated_audio_duration,audio_process.isolated_pcm):
                with self.assertRaises(ValueError):decode(playlist)
            self.assertEqual(requests,[])
        finally:server.shutdown();server.server_close();thread.join()

    @unittest.skipUnless(os.name=='nt' or sys.platform=='linux','Parent lifetime support is Windows/Linux')
    def test_parent_crash_does_not_leave_codec_process_running(self):
        import psutil
        with tempfile.TemporaryDirectory() as directory:
            worker=Path(directory)/'blocked_real_worker.py'
            source=audio_process.WORKER.read_text(encoding='utf-8')
            source=source.replace('data=sys.stdin.buffer.read(maximum+1)',
                                  'data=sys.stdin.buffer.read(maximum+1)\n        import time; time.sleep(60)')
            worker.write_text(source,encoding='utf-8')
            parent_file=Path(directory)/'parent.py'
            parent_file.write_text(
                'import sys,subprocess,threading\nfrom pathlib import Path\n'
                f'sys.path.insert(0,{str(Path(__file__).resolve().parent)!r})\n'
                'import audio_process\n'
                f'audio_process.WORKER=Path({str(worker)!r})\naudio_process.TIMEOUT=60\n'
                'original=subprocess.Popen\ndef capture(*a,**k):\n'
                ' child=original(*a,**k)\n threading.Timer(.5,lambda:print(child.pid,flush=True)).start()\n return child\n'
                'audio_process.subprocess.Popen=capture\naudio_process.isolated_audio_duration(b"test")\n',encoding='utf-8')
            parent=subprocess.Popen([sys.executable,str(parent_file)],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            child=None;watchdog=threading.Timer(5,parent.kill);watchdog.start()
            try:
                child=psutil.Process(int(parent.stdout.readline().strip()))
                watchdog.cancel();parent.kill();parent.wait(timeout=3)
                deadline=time.monotonic()+3
                def gone():
                    try:
                        return not child.is_running() or child.status()==psutil.STATUS_ZOMBIE
                    except psutil.NoSuchProcess:
                        return True
                while not gone() and time.monotonic()<deadline:time.sleep(.02)
                self.assertTrue(gone())
            finally:
                watchdog.cancel();watchdog.join()
                if parent.poll() is None:parent.kill()
                parent.wait();parent.stdout.close()
                if child is not None:
                    try:
                        if child.is_running() and child.status()!=psutil.STATUS_ZOMBIE:child.kill()
                    except psutil.NoSuchProcess:pass


class CancelledDecoderTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancelled_request_keeps_slot_until_child_is_killed(self):
        budget=DecoderBudget();original=subprocess.Popen;children=[]
        def capture(*args,**kwargs):
            child=original(*args,**kwargs);children.append(child);return child
        with tempfile.TemporaryDirectory() as directory:
            worker=Path(directory)/'blocked.py';worker.write_text('import time\ntime.sleep(60)\n')
            with patch.object(audio_process,'WORKER',worker),patch.object(audio_process,'TIMEOUT',.5),patch('audio_process.subprocess.Popen',side_effect=capture):
                request=asyncio.create_task(budget.run(audio_process.isolated_audio_duration,wav()))
                async def started():
                    while not children:await asyncio.sleep(.005)
                await asyncio.wait_for(started(),2)
                request.cancel()
                with self.assertRaises(asyncio.CancelledError):await request
                self.assertEqual(len(budget.tasks),1)
                await asyncio.wait_for(asyncio.gather(*list(budget.tasks),return_exceptions=True),3)
                self.assertIsNotNone(children[0].poll());self.assertFalse(budget.tasks)
        self.assertEqual(await budget.run(audio_process.isolated_audio_duration,wav()),1)


if __name__=='__main__':unittest.main()
