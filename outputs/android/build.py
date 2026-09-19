"""Build a small native IME with the official Android build tools, no Gradle required."""
from pathlib import Path
import os,subprocess,secrets,zipfile,json,hashlib

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
WORK=ROOT/'work'
TOOLS=WORK/'android-tools'
JDK=next((TOOLS/'jdk').glob('jdk-*'))
BUILD=TOOLS/'build-tools/android-15'
ANDROID=TOOLS/'platform/android-35/android.jar'
OUT=WORK/'android-build'
for directory in [OUT,OUT/'generated',OUT/'classes',OUT/'dex']:directory.mkdir(parents=True,exist_ok=True)
env=os.environ.copy();env['JAVA_HOME']=str(JDK)
def run(*args):
 subprocess.run([str(a) for a in args],env=env,check=True,cwd=HERE)
run(BUILD/'aapt2.exe','compile','--dir',HERE/'res','-o',OUT/'resources.zip')
run(BUILD/'aapt2.exe','link','-o',OUT/'unsigned.apk','-I',ANDROID,'--manifest',HERE/'AndroidManifest.xml','--java',OUT/'generated',OUT/'resources.zip')
sources=list((HERE/'src').rglob('*.java'))+list((OUT/'generated').rglob('*.java'))
run(JDK/'bin/javac.exe','--release','8','-encoding','UTF-8','-classpath',ANDROID,'-d',OUT/'classes',*sources)
run(JDK/'bin/jar.exe','cf',OUT/'classes.jar','-C',OUT/'classes','.')
run(JDK/'bin/java.exe','-cp',BUILD/'lib/d8.jar','com.android.tools.r8.D8','--lib',ANDROID,'--min-api','26','--output',OUT/'dex',OUT/'classes.jar')
with zipfile.ZipFile(OUT/'unsigned.apk','a',zipfile.ZIP_DEFLATED) as apk:
 for dex in (OUT/'dex').glob('*.dex'):apk.write(dex,dex.name)
run(BUILD/'zipalign.exe','-f','4',OUT/'unsigned.apk',OUT/'aligned.apk')
keystore=WORK/'localvoice-signing.p12';password=WORK/'localvoice-signing.password'
if not keystore.exists():
 if not password.exists():password.write_text(secrets.token_urlsafe(32),encoding='ascii')
 env['LOCALVOICE_SIGNING_PASSWORD']=password.read_text(encoding='ascii').strip()
 run(JDK/'bin/keytool.exe','-genkeypair','-keystore',keystore,'-storetype','PKCS12','-alias','localvoice','-keyalg','RSA','-keysize','3072','-validity','10000','-dname','CN=LocalVoice Personal, O=Personal Use, C=TW','-storepass:env','LOCALVOICE_SIGNING_PASSWORD','-keypass:env','LOCALVOICE_SIGNING_PASSWORD')
target=HERE/'DreamType-0.2.0.apk'
env['LOCALVOICE_SIGNING_PASSWORD']=password.read_text(encoding='ascii').strip()
run(JDK/'bin/java.exe','-jar',BUILD/'lib/apksigner.jar','sign','--ks',keystore,'--ks-pass','env:LOCALVOICE_SIGNING_PASSWORD','--key-pass','env:LOCALVOICE_SIGNING_PASSWORD','--out',target,OUT/'aligned.apk')
run(JDK/'bin/java.exe','-jar',BUILD/'lib/apksigner.jar','verify','--verbose','--print-certs',target)
run(BUILD/'aapt2.exe','dump','badging',target)
report={'file':target.name,'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
 'package':'tw.localvoice.keyboard','version':'0.2.0','minSdk':26,'targetSdk':35,
 'secrets_embedded':False,'native_device_test':'Pending Pixel 9 installation'}
(HERE/'build-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
