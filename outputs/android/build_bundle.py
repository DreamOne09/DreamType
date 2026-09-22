"""Build and validate a signed experimental AAB; never uploads to Google Play."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TOOLS = ROOT / 'work/android-tools'
PINS = {
    'bundletool-all-1.18.3.jar': (
        'https://github.com/google/bundletool/releases/download/1.18.3/bundletool-all-1.18.3.jar',
        'a099cfa1543f55593bc2ed16a70a7c67fe54b1747bb7301f37fdfd6d91028e29'),
    'aapt2-9.4.1-15978811-windows.jar': (
        'https://dl.google.com/dl/android/maven2/com/android/tools/build/aapt2/9.4.1-15978811/aapt2-9.4.1-15978811-windows.jar',
        '5fe3c8ee5c6b3f47efd1fced1d6418084037f54f13290816c5db717e6b5c92aa'),
}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download-tools', action='store_true')
    args = parser.parse_args()
    tool_dir = TOOLS / 'bundle'; tool_dir.mkdir(parents=True, exist_ok=True)
    for name, (url, digest) in PINS.items():
        path = tool_dir / name
        if not path.exists():
            if not args.download_tools:
                raise ValueError('Missing pinned tool; run with --download-tools: ' + name)
            urllib.request.urlretrieve(url, path)
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Tool checksum mismatch: ' + name)
    jdk = next((TOOLS/'jdk').glob('jdk-*'))
    sdk = TOOLS/'platform/android-36/android.jar'
    build = TOOLS/'build-tools/android-15'
    keystore = ROOT/'work/localvoice-signing.p12'
    password = ROOT/'work/localvoice-signing.password'
    if not keystore.is_file() or not password.is_file():
        raise ValueError('Existing maintainer signing key required; refusing to create a new identity.')
    env = os.environ.copy(); env['JAVA_HOME'] = str(jdk)
    env['DREAMTYPE_BUNDLE_PASSWORD'] = password.read_text(encoding='ascii').strip()
    java = jdk/'bin/java.exe'
    bundletool = tool_dir/'bundletool-all-1.18.3.jar'
    def run(*command):
        subprocess.run([str(arg) for arg in command], env=env, cwd=HERE, check=True)
    manifest = ET.parse(HERE/'AndroidManifest.xml').getroot()
    ns = '{http://schemas.android.com/apk/res/android}'
    version = manifest.get(ns+'versionName')
    # Do not overwrite the released APK or mix stale compiled classes into an AAB.
    output = HERE/('DreamType-'+version+'-experimental.aab')
    apk_output = HERE/('DreamType-'+version+'-bundle-test.apk')
    with tempfile.TemporaryDirectory(prefix='bundle-', dir=ROOT/'work') as directory:
        temp = Path(directory)
        with zipfile.ZipFile(tool_dir/'aapt2-9.4.1-15978811-windows.jar') as jar:
            (temp/'aapt2.exe').write_bytes(jar.read('aapt2.exe'))
        for name in ('generated','classes','dex'):(temp/name).mkdir()
        run(temp/'aapt2.exe','compile','--dir',HERE/'res','-o',temp/'resources.zip')
        run(temp/'aapt2.exe','link','--proto-format','-o',temp/'resources.apk','-I',sdk,
            '--manifest',HERE/'AndroidManifest.xml','--java',temp/'generated',temp/'resources.zip')
        channel = temp/'generated/BuildChannel.java'
        channel.write_text('package tw.localvoice.keyboard; final class BuildChannel { static final boolean PLAY_STORE = true; }',encoding='utf-8')
        sources=[p for p in (HERE/'src').rglob('*.java') if p.name!='BuildChannel.java']+list((temp/'generated').rglob('*.java'))
        run(jdk/'bin/javac.exe','--release','8','-encoding','UTF-8','-classpath',sdk,'-d',temp/'classes',*sources)
        run(jdk/'bin/jar.exe','cf',temp/'classes.jar','-C',temp/'classes','.')
        run(java,'-cp',build/'lib/d8.jar','com.android.tools.r8.D8','--lib',sdk,'--min-api','26','--output',temp/'dex',temp/'classes.jar')
        with zipfile.ZipFile(temp/'base.zip','w',zipfile.ZIP_DEFLATED) as base:
            with zipfile.ZipFile(temp/'resources.apk') as resources:
                for item in resources.namelist():
                    target = 'manifest/AndroidManifest.xml' if item=='AndroidManifest.xml' else item
                    if item!='AndroidManifest.xml' and item!='resources.pb' and not item.startswith('res/'):
                        raise ValueError('Unexpected linked resource: '+item)
                    base.writestr(target,resources.read(item))
            for dex in (temp/'dex').glob('*.dex'):base.write(dex,'dex/'+dex.name)
        run(java,'-jar',bundletool,'build-bundle','--modules='+str(temp/'base.zip'),'--output='+str(temp/'app.aab'))
        run(jdk/'bin/jarsigner.exe','-keystore',keystore,'-storepass:env','DREAMTYPE_BUNDLE_PASSWORD',
            '-keypass:env','DREAMTYPE_BUNDLE_PASSWORD',temp/'app.aab','localvoice')
        run(jdk/'bin/jarsigner.exe','-verify',temp/'app.aab')
        run(java,'-jar',bundletool,'validate','--bundle='+str(temp/'app.aab'))
        run(java,'-jar',bundletool,'build-apks','--bundle='+str(temp/'app.aab'),
            '--output='+str(temp/'app.apks'),'--mode=universal','--ks='+str(keystore),
            '--ks-key-alias=localvoice','--ks-pass=file:'+str(password),'--key-pass=file:'+str(password))
        with zipfile.ZipFile(temp/'app.apks') as apks:
            (temp/'universal.apk').write_bytes(apks.read('universal.apk'))
        run(java,'-jar',build/'lib/apksigner.jar','verify','--verbose','--print-certs',temp/'universal.apk')
        run(build/'aapt2.exe','dump','badging',temp/'universal.apk')
        output.write_bytes((temp/'app.aab').read_bytes())
        apk_output.write_bytes((temp/'universal.apk').read_bytes())
    report = {'aab':output.name,'aab_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
        'test_apk':apk_output.name,'test_apk_sha256':hashlib.sha256(apk_output.read_bytes()).hexdigest(),
        'package':manifest.get('package'),'version':version,'version_code':int(manifest.get(ns+'versionCode')),'target_sdk':int(manifest.find('uses-sdk').get(ns+'targetSdkVersion')),'compile_sdk':36,
        'bundletool_validation':True,'signed':True,'apk_signature_verified':True,'distribution_channel':'play',
        'native_device_test':False,'play_upload_test':False,'store_ready':False,
        'remaining':['Play Console and signing enrollment','Play listing update link verification','Billing and purchase verification',
                     'Android 16 native behavior verification','Native device tests and store disclosures'],
        'tool_sha256':{name:pin[1] for name,pin in PINS.items()}}
    (HERE/'bundle-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))

if __name__=='__main__':main()
