# DreamType maintenance
User-facing language: Traditional Chinese. Keep the UI simple, monochrome, and explicit about connection state.
Never commit work/, credentials, signing keys, pairing pages/QRs, audio samples, or machine-specific paths. Distribute APKs through GitHub Releases.
Preserve Android package tw.localvoice.keyboard and the maintainer signing key for upgrades. Do not claim native device verification unless actually performed.
The default dictation prompt preserves user meaning; do not silently turn it into requirement expansion.
Store direction is documented in docs/STORE_ROADMAP.md: cloud service with login and payments, no user-owned computer required. Preserve replaceable speech/text provider interfaces for two or three integrations; providers are not selected yet. Keep roadmap claims separate from implemented features. Current request authorizes documentation first, not paid infrastructure or live billing changes.
Python code resides under outputs/local_voice, Android under outputs/android. Keep paths relative to the repo root.
Latest hosting decision (2026-09-21): docs/HOME_SERVER.md supersedes hosted AI API recommendations. Serve phones from the owner's home PC first, migrate to an AI PC later if appropriate. End users need not run their own PC. Preserve future provider flexibility; do not infer authorization to buy cloud services or expose the current shared-key prototype publicly. Multi-user capacity is unverified.

0.4.0 implementation: invitation accounts, FIFO queue, per-account preferences/quotas and administrator UI are now implemented. Current verification and remaining work are in docs/BETA_ACCEPTANCE.md. Keep private v1 compatibility but never distribute the owner key to beta users. The user chose to keep a temporary tunnel; no domain or paid services should be purchased. Native Pixel 9 testing and Play billing remain pending.

0.5.0 adds read-only result recovery, a web account deletion page, and private SQLite backup/restore. See docs/RECOVERY.md. Recovery does not persist audio/text and cannot restore expired results or survive a host restart. Backups contain private keys and must remain outside Git. Never overwrite an existing account database during restore.

0.6.0 adds a single encrypted, one-hour client recording retry buffer for account mode. See docs/TWO_ROUND_REVIEW.md for exact retention, logout and completed-but-expired limitations. Android Keystore/device behavior remains unverified. Explicit failed-job retry reuses the request ID; successful or active jobs are never rerun automatically.

0.7.0 adds encrypted durable 15-minute results, opt-in client receipts and undelivered refunds, encrypted backups (recovery key stored separately), schema version 3 with encrypted pending-audio recovery, one-time admin-issued password reset, audit/health endpoints and Windows maintenance. See docs/PRODUCTION_STATUS.md. Do not claim cloud backups, native device tests or Play Billing are complete. Never commit .dtbackup or recovery keys.

0.8.0 is Taiwan-first: Traditional Chinese UI, organize mode and zh-TW source by default. Eight translation targets, explicit per-request language headers, Qwen English bridge + local TranslateGemma on 19873. Preserve amount markers and fail instead of returning untranslated fallback. See docs/TRANSLATION.md. Do not claim native-speaker or native-device validation.
