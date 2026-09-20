# DreamType maintenance
User-facing language: Traditional Chinese. Keep the UI simple, monochrome, and explicit about connection state.
Never commit work/, credentials, signing keys, pairing pages/QRs, audio samples, or machine-specific paths. Distribute APKs through GitHub Releases.
Preserve Android package tw.localvoice.keyboard and the maintainer signing key for upgrades. Do not claim native device verification unless actually performed.
The default dictation prompt preserves user meaning; do not silently turn it into requirement expansion.
Store direction is documented in docs/STORE_ROADMAP.md: cloud service with login and payments, no user-owned computer required. Preserve replaceable speech/text provider interfaces for two or three integrations; providers are not selected yet. Keep roadmap claims separate from implemented features. Current request authorizes documentation first, not paid infrastructure or live billing changes.
Python code resides under outputs/local_voice, Android under outputs/android. Keep paths relative to the repo root.
