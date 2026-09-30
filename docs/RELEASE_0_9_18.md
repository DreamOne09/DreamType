# 0.9.18 預覽版候選

版本碼 28；目前準備發布，下載入口仍維持已公開的 0.9.17，直到新資產上傳與下載核對完成。

這版限制持續慢慢傳送的 API 回應內容，避免只靠無資料逾時而一直等待。不新增錄音自動重送，也不改重試識別碼或扣額度邏輯。完整限制見 [Android 回應期限](ANDROID_RESPONSE_DEADLINE.md)：這不是整個上傳與處理操作的硬期限。

## 驗證

- 九組 JVM 契約測試通過，包括真實本機 HTTP 滴流測試、遲到 EOF 拒絕及原有收件／重試契約。
- Android 16 原生回歸 [36735842046](https://github.com/DreamOne09/DreamType/actions/runs/36735842046) 通過，提交 `e491d10427a725950a0ae64adb7b631fb21ffd6b`。下載的 `result.txt` 明確包含 `response_deadline=passed` 與 `dreamtype=passed`。
- 原生回歸使用該提交的 0.9.17 測試 manifest，並非這份 0.9.18 正式簽章 APK 的安裝升級驗證。這次版本準備只提高版本號／碼；手機仍待實測。
- 本機 APK v2／v3 簽章驗證通過，沿用原簽章；package `tw.localvoice.keyboard`，minSdk 26、targetSdk 36。
- APK 未包含已知測試 instrumentation、測試 CA 或兩個當前主機私有金鑰值。這是有限檢查，不是獨立安全稽核。

APK：`DreamType-0.9.18.apk`，66333 bytes。

SHA-256：`ef2263083fd57a7089fc3eb8d886430a51427bfa38f4731c2968e31cccb722fe`。

簽章憑證 SHA-256：`8af01d69be8604c2f4a288d55651bb72bed42a391c546f04db4a2a0deb14fc98`。

仍是邀請免費試用。Pixel 9／Surfshark、翻譯人稱忠實度、真正 R2 備份與離機還原、固定入口、Play 付款均未完成驗收；不得把此版本標為公開收費 production。
