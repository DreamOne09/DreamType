"""Fixed-purpose child process. Audio travels through pipes, never a temp file."""
import io
import math
import sys
import os

# Input is already an in-memory file. Do not follow network or local-file URLs
# embedded in playlist-like input; no file/http/tcp protocol is needed here.
INPUT_OPTIONS={'protocol_whitelist':'pipe'}


def audio_duration(data):
    import av
    samples_by_rate={}
    with av.open(io.BytesIO(data),options=INPUT_OPTIONS) as container:
        for frame in container.decode(audio=0):
            rate=frame.sample_rate
            samples_by_rate[rate]=samples_by_rate.get(rate,0)+frame.samples
            seconds=math.fsum(samples/rate for rate,samples in samples_by_rate.items())
            if seconds>120:return seconds
    return math.fsum(samples/rate for rate,samples in samples_by_rate.items())


def pcm16(data):
    import av
    resampler=av.AudioResampler(format='s16',layout='mono',rate=16000)
    output=bytearray();maximum=360*16000*2
    def collect(frame):
        size=frame.samples*2
        if len(output)+size>maximum:raise OverflowError('duration limit')
        # Packed mono plane may contain alignment padding, which is not audio.
        raw=bytes(frame.planes[0])[:size]
        if sys.byteorder!='little':
            import array
            samples=array.array('h',raw);samples.byteswap();raw=samples.tobytes()
        output.extend(raw)
    with av.open(io.BytesIO(data),mode='r',metadata_errors='ignore',options=INPUT_OPTIONS) as container:
        for frame in container.decode(audio=0):
            frame.pts=None
            for converted in resampler.resample(frame):collect(converted)
        for converted in resampler.resample(None):collect(converted)
    return bytes(output)


if __name__=='__main__':
    mode=sys.argv[1] if len(sys.argv)==3 else ''
    if mode not in ('duration','pcm'):sys.exit(2)
    if sys.platform=='linux':
        import ctypes
        libc=ctypes.CDLL(None,use_errno=True)
        libc.prctl.argtypes=[ctypes.c_int]+[ctypes.c_ulong]*4
        libc.prctl.restype=ctypes.c_int
        if libc.prctl(1,9,0,0,0)!=0:sys.exit(2)  # PR_SET_PDEATHSIG / SIGKILL
        if os.getppid()!=int(sys.argv[2]):sys.exit(2)
    maximum=(2 if mode=='duration' else 25)*1024*1024
    try:
        data=sys.stdin.buffer.read(maximum+1)
        if not data or len(data)>maximum:sys.exit(2)
        if mode=='duration':
            seconds=audio_duration(data)
            if not math.isfinite(seconds) or seconds<=0:sys.exit(2)
            sys.stdout.buffer.write(repr(seconds).encode('ascii'))
        else:
            output=pcm16(data)
            if not output:sys.exit(2)
            sys.stdout.buffer.write(output)
    except OverflowError:sys.exit(3)
    except Exception:sys.exit(2)
