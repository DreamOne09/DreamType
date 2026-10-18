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
TESTS = ('EmptyResultCheck', 'TranslationContractTest', 'VoiceRecoveryTest', 'EncryptedRecordingTest', 'ErrorMessageTest', 'ReceiptRecoveryTest', 'UpdateCheckTest', 'WordSuggestionsTest', 'ResponseDeadlineTest', 'DefaultServerTest', 'ServiceDiscoveryTest', 'UploadProgressTest')
RECOVERY_TESTS = ('AccountPlanTest', 'PurchaseRecoveryTest', 'PurchaseStateTest', 'ConnectionPersistenceTest',
                  'ConnectionVerificationTest', 'PendingAudioSessionTest', 'PreferenceSyncTest',
                  'ReceiptPendingAudioTest', 'ResponseIntegrityTest', 'SessionClearFailureTest',
                  'UploadResponseFailureTest')


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
                   ('AppConfig', 'Draft', 'PendingAudio', 'EncryptedRecording', 'VoiceApi', 'UpdateCheck', 'WordSuggestions', 'ServiceDiscovery', 'AccountPlan', 'PurchaseRecovery', 'PurchaseState', 'PreferenceSync')]
        # Only this host-JVM runner uses these bridges. APK builders compile src/,
        # never tests/stubs/, and native instrumentation uses the real framework.
        sources += list((tests / 'stubs').rglob('*.java'))
        subprocess.run([java_tool('javac'), '-encoding', 'UTF-8', '-cp', str(args.android_jar),
                        '-d', str(classes), *map(str, sources)], check=True, timeout=90)
        classpath = os.pathsep.join(map(str, (classes, dependency, args.android_jar)))
        # Fixtures use the host JSON implementation; compile production classes
        # above against Android's API first so host-only APIs cannot slip in.
        test_sources = [tests / (name + '.java') for name in TESTS + RECOVERY_TESTS]
        subprocess.run([java_tool('javac'), '-encoding', 'UTF-8', '-cp', classpath,
                        '-d', str(classes), *map(str, test_sources)], check=True, timeout=90)
        for name in TESTS + RECOVERY_TESTS:
            evidence = [str(work / (name + '.json'))] if name in RECOVERY_TESTS and name not in ('AccountPlanTest', 'PurchaseRecoveryTest', 'PurchaseStateTest') else []
            subprocess.run([java_tool('java'), '-cp', classpath, 'tw.localvoice.keyboard.' + name, *evidence],
                           check=True, timeout=60)
    print(f'PASS: {len(TESTS) + len(RECOVERY_TESTS)} JVM contract suites. This runner does not test native UI or Keystore.')


if __name__ == '__main__':
    main()
