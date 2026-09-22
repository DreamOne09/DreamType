"""Drive the real IME in a disposable Android emulator via an external editor."""
import json
from pathlib import Path
import re
import subprocess
import time
import xml.etree.ElementTree as ET

out=Path('work/emulator-probe/screenshots')
out.mkdir(parents=True,exist_ok=True)
def adb(*args):
    return subprocess.run(['adb',*args],check=True,capture_output=True,timeout=30).stdout

def tree():
    adb('shell','uiautomator','dump','/sdcard/dreamtype-ui.xml')
    return ET.fromstring(adb('exec-out','cat','/sdcard/dreamtype-ui.xml'))

def find(root,attribute,value):
    return next((node for node in root.iter('node') if node.get(attribute)==value),None)

def wait_node(attribute,value):
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        root=tree()
        node=find(root,attribute,value)
        if node is not None:return node
        time.sleep(0.25)
    raise AssertionError('Expected UI node missing: '+value)

def tap_field(name):
    node=wait_node('content-desc',name)
    x1,y1,x2,y2=map(int,re.findall(r'\d+',node.get('bounds')))
    adb('shell','input','tap',str((x1+x2)//2),str((y1+y2)//2))

def check_mic(enabled,label):
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        root=tree()
        mic=find(root,'text','開始說話')
        if mic is not None and mic.get('enabled')==str(enabled).lower():
            if not enabled and not any('密碼欄位不使用語音' in n.get('text','') for n in root.iter('node')):
                raise AssertionError('Password guidance missing')
            (out/(label+'.xml')).write_bytes(ET.tostring(root,encoding='utf-8'))
            (out/(label+'.png')).write_bytes(adb('exec-out','screencap','-p'))
            return
        time.sleep(0.25)
    raise AssertionError('IME microphone state incorrect: '+label)

try:
    adb('install','-t','work/emulator-probe/fixture.apk')
    adb('shell','ime','enable','tw.localvoice.keyboard/.VoiceIme')
    adb('shell','ime','set','tw.localvoice.keyboard/.VoiceIme')
    adb('shell','settings','put','secure','show_ime_with_hard_keyboard','1')
    adb('shell','am','start','-W','-n','tw.dreamtype.fixture/.InputFixture')
    tap_field('一般文字')
    check_mic(True,'ime-normal')
    tap_field('密碼欄位')
    check_mic(False,'ime-password')
    tap_field('一般文字')
    check_mic(True,'ime-normal-return')
    report={'external_editor':True,'ime_visible':True,'password_voice_disabled':True,
            'normal_field_reenabled':True,'microphone_recording_tested':False,'text_insertion_tested':False,
            'pixel9_tested':False}
    Path('work/emulator-probe/ime-result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))
except Exception:
    for name,command in (
        ('ime-failure.png',('exec-out','screencap','-p')),
        ('ime-state.txt',('shell','dumpsys','input_method')),
        ('ime-log.txt',('shell','logcat','-d','-t','300')),
        ('ime-failure.xml',('exec-out','cat','/sdcard/dreamtype-ui.xml'))):
        try:(out/name).write_bytes(adb(*command))
        except Exception:pass
    raise
