"""Build a small native IME with the official Android build tools, no Gradle required."""
from pathlib import Path
import os,subprocess,secrets,zipfile,json,hashlib,tempfile,argparse,re
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--work-root',type=Path,help='Existing tools and signing configuration directory')
parser.add_argument('--output-dir',type=Path,help='Separate candidate output directory; existing APKs are not overwritten')
parser.add_argument('--require-existing-signing',action='store_true',help='Fail instead of generating signing material')
parser.add_argument('--version-name',help='Isolated candidate version, for example 0.9.20-rc2')
parser.add_argument('--version-code',type=int,help='Candidate code greater than the source manifest code')
args=parser.parse_args()
if (args.version_name is None)!=(args.version_code is None):
 parser.error('Candidate version name and code must be supplied together')
if args.version_name is not None:
 if not args.output_dir or not args.require_existing_signing:
  parser.error('Candidate overrides require separate output and existing signing')
 if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:-rc[0-9]+)?',args.version_name):
  parser.error('Unsupported candidate version name')
WORK=(args.work_root or ROOT/'work').resolve()
destination=(args.output_dir or HERE).resolve()
keystore=WORK/'localvoice-signing.p12';password=WORK/'localvoice-signing.password'
if args.require_existing_signing and (not keystore.is_file() or not password.is_file()):
 raise SystemExit('Existing signing configuration required; nothing generated')
TOOLS=WORK/'android-tools'
JDK=next((TOOLS/'jdk').glob('jdk-*'))
BUILD=TOOLS/'build-tools/android-15'
ANDROID=TOOLS/'platform/android-36/android.jar'
manifest_tree=ET.parse(HERE/'AndroidManifest.xml')
manifest=manifest_tree.getroot()
ns='{http://schemas.android.com/apk/res/android}'
base_version=manifest.get(ns+'versionName')
base_code=int(manifest.get(ns+'versionCode'))
if args.version_name is not None:
 if not base_code<args.version_code<=2100000000:
  parser.error('Candidate code must be greater than the source version code and within Android range')
 manifest.set(ns+'versionName',args.version_name)
 manifest.set(ns+'versionCode',str(args.version_code))
version=manifest.get(ns+'versionName')
target=destination/('DreamType-'+version+'.apk')
if args.output_dir and target.exists():raise SystemExit('Candidate APK already exists; select a new output directory')
destination.mkdir(parents=True,exist_ok=True)
# Isolate each build so removed Java classes cannot leak into the APK.
_build_temp=tempfile.TemporaryDirectory(prefix='android-apk-',dir=WORK)
OUT=Path(_build_temp.name)
for directory in [OUT,OUT/'generated',OUT/'classes',OUT/'dex']:directory.mkdir(parents=True,exist_ok=True)
build_manifest=HERE/'AndroidManifest.xml'
if args.version_name is not None:
 ET.register_namespace('android','http://schemas.android.com/apk/res/android')
 build_manifest=OUT/'AndroidManifest.xml'
 manifest_tree.write(build_manifest,encoding='utf-8',xml_declaration=True)
env=os.environ.copy();env['JAVA_HOME']=str(JDK)
def run(*args):
 subprocess.run([str(a) for a in args],env=env,check=True,cwd=HERE)
run(BUILD/'aapt2.exe','compile','--dir',HERE/'res','-o',OUT/'resources.zip')
run(BUILD/'aapt2.exe','link','-o',OUT/'unsigned.apk','-I',ANDROID,'--manifest',build_manifest,'--java',OUT/'generated',OUT/'resources.zip')
sources=list((HERE/'src').rglob('*.java'))+list((OUT/'generated').rglob('*.java'))
run(JDK/'bin/javac.exe','--release','8','-encoding','UTF-8','-classpath',ANDROID,'-d',OUT/'classes',*sources)
run(JDK/'bin/jar.exe','cf',OUT/'classes.jar','-C',OUT/'classes','.')
run(JDK/'bin/java.exe','-cp',BUILD/'lib/d8.jar','com.android.tools.r8.D8','--lib',ANDROID,'--min-api','26','--output',OUT/'dex',OUT/'classes.jar')
with zipfile.ZipFile(OUT/'unsigned.apk','a',zipfile.ZIP_DEFLATED) as apk:
 for dex in (OUT/'dex').glob('*.dex'):apk.write(dex,dex.name)
run(BUILD/'zipalign.exe','-f','4',OUT/'unsigned.apk',OUT/'aligned.apk')
if not keystore.exists():
 if not password.exists():password.write_text(secrets.token_urlsafe(32),encoding='ascii')
 env['LOCALVOICE_SIGNING_PASSWORD']=password.read_text(encoding='ascii').strip()
 run(JDK/'bin/keytool.exe','-genkeypair','-keystore',keystore,'-storetype','PKCS12','-alias','localvoice','-keyalg','RSA','-keysize','3072','-validity','10000','-dname','CN=LocalVoice Personal, O=Personal Use, C=TW','-storepass:env','LOCALVOICE_SIGNING_PASSWORD','-keypass:env','LOCALVOICE_SIGNING_PASSWORD')
env['LOCALVOICE_SIGNING_PASSWORD']=password.read_text(encoding='ascii').strip()
run(JDK/'bin/java.exe','-jar',BUILD/'lib/apksigner.jar','sign','--ks',keystore,'--ks-pass','env:LOCALVOICE_SIGNING_PASSWORD','--key-pass','env:LOCALVOICE_SIGNING_PASSWORD','--out',target,OUT/'aligned.apk')
run(JDK/'bin/java.exe','-jar',BUILD/'lib/apksigner.jar','verify','--verbose','--print-certs',target)
run(BUILD/'aapt2.exe','dump','badging',target)
report={'file':target.name,'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
 'package':manifest.get('package'),'version':version,'versionCode':int(manifest.get(ns+'versionCode')),'minSdk':26,'targetSdk':int(manifest.find('uses-sdk').get(ns+'targetSdkVersion')),
 'candidate_version_override':args.version_name is not None,'source_version':base_version,'source_version_code':base_code,
 'secret_scan':'Not performed by build; requires separate artifact verification','native_device_test':'Pending Pixel 9 installation'}
(destination/'build-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
