"""Run Android networking/storage JVM contracts without a device or production secrets."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.request

JSON_SHA256 = '3ea61b2a06e31edf1c91134fe9106b0ebb16628be169f3db75bc7a2b06b45796'
JSON_URL = 'https://repo.maven.apache.org/maven2/org/json/json/20250517/json-20250517.jar'
TESTS = ('EmptyResultCheck', 'TranslationContractTest', 'VoiceRecoveryTest', 'EncryptedRecordingTest', 'ErrorMessageTest')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--android-jar', type=Path, required=True)
    parser.add_argument('--java-home', type=Path, default=os.environ.get('JAVA_HOME'))
    parser.add_argument('--json-jar', type=Path)
    args = parser.parse_args()
    if not args.android_jar.is_file():
        parser.error('Android SDK jar does not exist')
    repo = Path(__file__).resolve().parents[1]
    source = repo / 'outputs/android/src/tw/localvoice/keyboard'
    tests = repo / 'outputs/android/tests'
    suffix = '.exe' if os.name == 'nt' else ''
    def java_tool(name):
        return str(args.java_home / 'bin' / (name + suffix)) if args.java_home else name
    with tempfile.TemporaryDirectory(prefix='dreamtype-contracts-') as temporary:
        work = Path(temporary)
        dependency = args.json_jar
        if dependency is None:
            dependency = work / 'json.jar'
            with urllib.request.urlopen(JSON_URL, timeout=30) as response:
                dependency.write_bytes(response.read())
        if hashlib.sha256(dependency.read_bytes()).hexdigest() != JSON_SHA256:
            raise SystemExit('JSON dependency checksum mismatch')
        classes = work / 'classes'
        classes.mkdir()
        sources = [source / (name + '.java') for name in
                   ('AppConfig', 'Draft', 'PendingAudio', 'EncryptedRecording', 'VoiceApi')]
        sources += [tests / (name + '.java') for name in TESTS]
        subprocess.run([java_tool('javac'), '-encoding', 'UTF-8', '-cp', str(args.android_jar),
                        '-d', str(classes), *map(str, sources)], check=True, timeout=90)
        classpath = os.pathsep.join(map(str, (classes, dependency, args.android_jar)))
        for name in TESTS:
            subprocess.run([java_tool('java'), '-cp', classpath, 'tw.localvoice.keyboard.' + name],
                           check=True, timeout=60)
    print('PASS: five JVM contract suites. Native UI and Keystore remain untested.')


if __name__ == '__main__':
    main()
