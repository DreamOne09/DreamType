"""Build a disposable self-instrumented APK on a Linux CI runner. Never a release APK."""
import os
import shutil
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
# Only the disposable probe may reach the synthetic runner-local HTTP service.
manifest.getroot().find('application').set('{'+ns+'}usesCleartextTraffic','true')
ET.SubElement(manifest.getroot(),'instrumentation',{'{'+ns+'}name':'.SmokeInstrumentation','{'+ns+'}targetPackage':'tw.localvoice.keyboard'})
# A short-lived CA exists only in this disposable APK, never the production resources.
run('openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','2','-subj','/CN=DreamType native fixture',
    '-addext','subjectAltName=IP:10.0.2.2','-keyout',out/'tls-key.pem','-out',out/'tls-cert.pem')
resources=out/'test-res'
shutil.copytree(source/'res',resources,dirs_exist_ok=True)
(resources/'raw').mkdir(exist_ok=True)
shutil.copyfile(out/'tls-cert.pem',resources/'raw/native_ca.pem')
(resources/'xml/native_network.xml').write_text('<network-security-config><base-config cleartextTrafficPermitted="true"><trust-anchors><certificates src="system"/></trust-anchors></base-config><debug-overrides><trust-anchors><certificates src="@raw/native_ca"/></trust-anchors></debug-overrides></network-security-config>')
manifest.getroot().find('application').set('{'+ns+'}networkSecurityConfig','@xml/native_network')
manifest.write(out/'AndroidManifest.xml',encoding='utf-8')
run(build/'aapt2','compile','--dir',resources,'-o',out/'resources.zip')
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

# A separate package is necessary: DreamType intentionally disables voice inside its own editor.
fixture=out/'fixture'
for name in ('classes','dex'):(fixture/name).mkdir(parents=True,exist_ok=True)
(fixture/'AndroidManifest.xml').write_text("""<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="tw.dreamtype.fixture"><uses-sdk android:minSdkVersion="26" android:targetSdkVersion="36"/><application android:label="DreamType Test Editor" android:theme="@android:style/Theme.Material.Light.NoActionBar" android:testOnly="true"><activity android:name=".InputFixture" android:exported="true"/></application><instrumentation android:name=".ImeInstrumentation" android:targetPackage="tw.dreamtype.fixture"/></manifest>""",encoding='utf-8')
run(build/'aapt2','link','-o',fixture/'unsigned.apk','-I',android,'--manifest',fixture/'AndroidManifest.xml')
run('javac','--release','8','-encoding','UTF-8','-cp',android,'-d',fixture/'classes',source/'tests/InputFixture.java',source/'tests/ImeInstrumentation.java')
run('jar','cf',fixture/'classes.jar','-C',fixture/'classes','.')
run('java','-cp',build/'lib/d8.jar','com.android.tools.r8.D8','--lib',android,'--min-api','26','--output',fixture/'dex',fixture/'classes.jar')
with zipfile.ZipFile(fixture/'unsigned.apk','a',zipfile.ZIP_DEFLATED) as archive:
 for dex in (fixture/'dex').glob('*.dex'):archive.write(dex,dex.name)
run(build/'zipalign','-f','4',fixture/'unsigned.apk',fixture/'aligned.apk')
run(build/'apksigner','sign','--ks',out/'test.p12','--ks-pass','pass:android','--out',out/'fixture.apk',fixture/'aligned.apk')
