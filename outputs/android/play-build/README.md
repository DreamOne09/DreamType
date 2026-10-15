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

2026-10-16: workflow syntax and the two JVM contract programs were checked locally.
The new workflow has not yet been run on GitHub. Local full builds remain blocked
by Windows memory pressure; the most recent purchase recovery change is not yet
proven to be included in a successfully rebuilt APK/AAB pair.
