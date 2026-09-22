"""Build a disposable self-instrumented APK on a Linux CI runner. Never a release APK."""
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
import zipfile

repo=Path(__file__).resolve().parents[1]
sdk=Path(os.environ['ANDROID_HOME'])
build=sdk/'build-tools/35.0.0'
android=sdk/'platforms/android-36/android.jar'
source=repo/'outputs/android'
out=repo/'work/emulator-probe'
out.mkdir(parents=True,exist_ok=True)
for name in ('generated','classes','dex'):(out/name).mkdir(exist_ok=True)
def run(*args):subprocess.run(list(map(str,args)),check=True)
ns='http://schemas.android.com/apk/res/android'
ET.register_namespace('android',ns)
manifest=ET.parse(source/'AndroidManifest.xml')
manifest.getroot().find('application').set('{'+ns+'}debuggable','true')
manifest.getroot().find('application').set('{'+ns+'}testOnly','true')
ET.SubElement(manifest.getroot(),'instrumentation',{'{'+ns+'}name':'.SmokeInstrumentation','{'+ns+'}targetPackage':'tw.localvoice.keyboard'})
manifest.write(out/'AndroidManifest.xml',encoding='utf-8')
run(build/'aapt2','compile','--dir',source/'res','-o',out/'resources.zip')
run(build/'aapt2','link','-o',out/'unsigned.apk','-I',android,'--manifest',out/'AndroidManifest.xml','--java',out/'generated',out/'resources.zip')
sources=list((source/'src').rglob('*.java'))+list((out/'generated').rglob('*.java'))+[source/'tests/SmokeInstrumentation.java']
run('javac','--release','8','-encoding','UTF-8','-cp',android,'-d',out/'classes',*sources)
run('jar','cf',out/'classes.jar','-C',out/'classes','.')
run('java','-cp',build/'lib/d8.jar','com.android.tools.r8.D8','--lib',android,'--min-api','26','--output',out/'dex',out/'classes.jar')
with zipfile.ZipFile(out/'unsigned.apk','a',zipfile.ZIP_DEFLATED) as archive:
 for dex in (out/'dex').glob('*.dex'):archive.write(dex,dex.name)
run(build/'zipalign','-f','4',out/'unsigned.apk',out/'aligned.apk')
run('keytool','-genkeypair','-keystore',out/'test.p12','-storepass','android','-keypass','android','-alias','test','-keyalg','RSA','-validity','2','-dname','CN=Disposable Emulator Test')
run(build/'apksigner','sign','--ks',out/'test.p12','--ks-pass','pass:android','--out',out/'probe.apk',out/'aligned.apk')
