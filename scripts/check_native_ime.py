"""Use fixture instrumentation to inspect every interactive Android window, including IME."""
import json
from pathlib import Path
import subprocess

out=Path('work/emulator-probe/screenshots')
out.mkdir(parents=True,exist_ok=True)
def adb(*args):return subprocess.run(['adb',*args],check=True,capture_output=True,timeout=90).stdout
try:
    adb('install','-t','work/emulator-probe/fixture.apk')
    adb('shell','ime','enable','tw.localvoice.keyboard/.VoiceIme')
    adb('shell','ime','set','tw.localvoice.keyboard/.VoiceIme')
    adb('shell','settings','put','secure','show_ime_with_hard_keyboard','1')
    result=adb('shell','am','instrument','-w','tw.dreamtype.fixture/.ImeInstrumentation').decode('utf-8')
    Path('work/emulator-probe/ime-instrumentation.txt').write_text(result,encoding='utf-8')
    adb('pull','/sdcard/Android/data/tw.dreamtype.fixture/files',str(out/'ime'))
    if 'INSTRUMENTATION_RESULT: ime=passed' not in result or 'INSTRUMENTATION_CODE: -1' not in result:
        raise AssertionError(result)
    report={'external_editor':True,'ime_visible':True,'password_voice_disabled':True,
            'normal_field_reenabled':True,'microphone_recording_tested':False,
            'text_insertion_tested':False,'pixel9_tested':False}
    Path('work/emulator-probe/ime-result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))
except Exception:
    for name,command in (
        ('ime-failure.png',('exec-out','screencap','-p')),
        ('ime-state.txt',('shell','dumpsys','input_method')),
        ('ime-log.txt',('shell','logcat','-d','-t','300'))):
        try:(out/name).write_bytes(adb(*command))
        except Exception:pass
    raise
