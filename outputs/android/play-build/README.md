# DreamType Google Play candidate build

This Gradle project reuses the native keyboard sources and resources one directory
above. It includes Google Play Billing Library 9.1.0 and its transitive dependencies.
A basic subscription and restore UI is included. Real Play transactions are unverified; a successful build is not a store release.

Prerequisites: JDK 17 or newer, Android SDK platform 36 and Build Tools 36.0.0.
Set `JAVA_HOME` and `ANDROID_HOME` to your local installations. Use a private local
`GRADLE_USER_HOME` when building on a shared machine. Do not commit SDK paths,
service credentials, signing passwords or keystores.

From this directory:

```powershell
./gradlew.bat assembleRelease bundleRelease
```

The wrapper pins Gradle 9.6.0 with the official distribution SHA-256. Dependency
versions are locked. Outputs are in `build/outputs/apk/release` and
`build/outputs/bundle/release`. Release artifacts are **unsigned**. Do not install
these over the signed private APK; preserve the existing maintainer signer before
testing upgrade or publishing. The original `../build.py` remains available for
private APK candidates without the Billing SDK.

The generated manifest removes legacy package/SDK declarations for AGP 9;
application ID, minimum/target SDK and candidate version come from `build.gradle`.
Verify the merged manifest, permissions, artifact contents and signer for every
release, then perform real Google Play and Pixel 9 tests.

## GitHub build candidate

The manual `Android Play candidate` workflow builds on an isolated Ubuntu runner,
so it does not compete with the home inference server for memory. It compiles and
runs the account display and purchase recovery contracts, builds both release
formats, and requires Android release lint to pass before uploading artifacts.
The artifact includes SHA-256 digests and the exact source commit. It has no
production signing key, deployment credential, or automatic store upload.

After this workflow and all referenced sources/locks are committed and pushed,
select it in GitHub Actions and run it for the intended revision. Download the
unsigned artifact only from a successful run; the lint report is also retained
on failure. Do not treat YAML validation as a successful GitHub build.

2026-10-16: GitHub run 38815358793 succeeded for source
`07d513899a58f7cf3dbd305f7cae068a5aaca32c`, including the purchase recovery change.
Both release formats and release lint passed after fixing API 26 theme resources
and layout constants. Lint warnings remain, including backup extraction rules
and accessibility; passing the build is not production acceptance.

Downloaded artifacts were independently SHA-256 checked:

- APK: `fce6a2495a20351a292be89f2b27109b0cdb508bd90933b693cc592e857b5ddf`
- AAB: `c8614b9e3d74c0e49918ffb024b5a20e290ca2555312c45831a51a26a313c2cb`

These are unsigned candidates, not an installable upgrade or a store release.
Local full builds remain constrained by Windows memory pressure.
