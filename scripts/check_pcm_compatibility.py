import argparse,io,json,sys,time,wave
from pathlib import Path
import av,numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'outputs/local_voice'))
from audio_process import isolated_pcm
from faster_whisper.audio import decode_audio
from importlib.metadata import version
assert version("faster-whisper")=="1.2.1", "Use the pinned reference decoder"

def encoded(container,codec,rate,channels):
    t=np.arange(rate*3)/rate
    values=np.stack([np.sin(t*2*np.pi*(440+c*170))*.6 for c in range(channels)],axis=1)
    pcm=(values*32767).astype('<i2')
    buf=io.BytesIO()
    if container=='wav':
        with wave.open(buf,'wb') as out:
            out.setnchannels(channels);out.setsampwidth(2);out.setframerate(rate);out.writeframes(pcm.tobytes())
    else:
        with av.open(buf,'w',format=container) as out:
            stream=out.add_stream(codec,rate=rate);stream.layout='mono' if channels==1 else 'stereo'
            frame=av.AudioFrame.from_ndarray(pcm.reshape(1,-1),format='s16',layout=stream.layout)
            frame.sample_rate=rate
            for packet in stream.encode(frame):out.mux(packet)
            for packet in stream.encode(None):out.mux(packet)
    return buf.getvalue()

parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
report=[]
for container,codec,rate,channels in [('wav','pcm_s16le',16000,1),('wav','pcm_s16le',48000,2),('flac','flac',48000,2),('adts','aac',48000,2),('mp4','aac',16000,1),('webm','libopus',48000,1)]:
    audio=encoded(container,codec,rate,channels)
    previous=decode_audio(io.BytesIO(audio),sampling_rate=16000)
    started=time.perf_counter();raw=isolated_pcm(audio);elapsed=time.perf_counter()-started
    current=np.frombuffer(raw,dtype='<i2').astype(np.float32)/32768.0
    assert len(current)==len(previous),(container,len(current),len(previous))
    delta=float(np.max(np.abs(current-previous)))
    row=dict(format=container,rate=rate,channels=channels,input_bytes=len(audio),samples=len(current),max_absolute_difference=delta,identical=bool(np.array_equal(current,previous)),child_seconds=elapsed)
    report.append(row);print(json.dumps(row),flush=True)
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text(json.dumps({'synthetic_audio':True,'reference':'installed faster-whisper 1.2.1 decode_audio','cases':report},indent=2))
assert all(row['identical'] for row in report)
