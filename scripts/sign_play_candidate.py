"""Sign a checksum-pinned CI APK locally with the existing maintainer identity."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('apk', 'work-root', 'build-tools', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--signer-sha256', required=True)
    parser.add_argument('--version-code', type=int, required=True)
    args = parser.parse_args()
    for digest in (args.sha256, args.signer_sha256):
        if not re.fullmatch('[0-9a-f]{64}', digest):
            parser.error('Expected a lowercase SHA-256 digest')
    if args.output.exists():
        parser.error('Refusing to overwrite an existing artifact')
    if hashlib.sha256(args.apk.read_bytes()).hexdigest() != args.sha256:
        parser.error('Input differs from the expected CI artifact')
    work = args.work_root.resolve()
    key = work / 'localvoice-signing.p12'
    password = work / 'localvoice-signing.password'
    if not key.is_file() or not password.is_file():
        parser.error('Existing signing key and password are required; nothing generated')
    java = next((work / 'android-tools/jdk').glob('jdk-*/bin/java.exe'))
    tools = args.build_tools.resolve()
    def run(*command, env=None):
        return subprocess.run(list(map(str, command)), env=env, check=True,
                              capture_output=True, text=True, timeout=120).stdout
    badging = run(tools / 'aapt2.exe', 'dump', 'badging', args.apk)
    if not re.search(r"package: name='tw\.localvoice\.keyboard' versionCode='" + str(args.version_code) + "'", badging):
        parser.error('Unexpected package or version')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='sign-play-', dir=args.output.parent) as directory:
        aligned = Path(directory) / 'aligned.apk'
        signed = Path(directory) / 'signed.apk'
        run(tools / 'zipalign.exe', '-f', '4', args.apk, aligned)
        env = dict(os.environ, LOCALVOICE_SIGNING_PASSWORD=password.read_text(encoding='ascii').strip())
        run(java, '-Xmx128m', '-jar', tools / 'lib/apksigner.jar', 'sign', '--ks', key,
            '--ks-pass', 'env:LOCALVOICE_SIGNING_PASSWORD', '--key-pass', 'env:LOCALVOICE_SIGNING_PASSWORD',
            '--out', signed, aligned, env=env)
        del env['LOCALVOICE_SIGNING_PASSWORD']
        verification = run(java, '-Xmx128m', '-jar', tools / 'lib/apksigner.jar', 'verify', '--verbose', '--print-certs', signed)
        signers = re.findall(r'Signer #\d+ certificate SHA-256 digest: ([0-9a-f]+)', verification)
        if signers != [args.signer_sha256] or 'Verified using v2 scheme (APK Signature Scheme v2): true' not in verification:
            raise ValueError('Unexpected signer or missing v2 signature; candidate not published')
        run(tools / 'zipalign.exe', '-c', '4', signed)
        # Exclusive creation avoids replacing an artifact created during signing.
        with args.output.open('xb') as target:
            target.write(signed.read_bytes())
    print(json.dumps({'apk': args.output.name, 'sha256': hashlib.sha256(args.output.read_bytes()).hexdigest(),
                      'signer_sha256': args.signer_sha256, 'version_code': args.version_code,
                      'status': 'signed candidate; device and store acceptance required'}))


if __name__ == '__main__':
    main()
