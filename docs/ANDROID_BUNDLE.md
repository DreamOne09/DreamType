# Android App Bundle 建置

已能產生簽署的實驗 AAB，並以 Google bundletool 驗證、轉成 universal APK。這是建置驗證，不代表可直接公開上架。沒有上傳 Play Console，沒有新增付費服務。

## 建置

先完成既有 Windows Android 工具安裝，並保留 `work/localvoice-signing.p12` 與其密碼檔。缺少既有簽章時本流程會停止，不自行建立新簽章。

```powershell
.\work\venv\Scripts\python.exe .\outputs\android\build_bundle.py --download-tools
```

首次可下載固定版本的 Google bundletool 1.18.3、Google Maven AAPT2 9.4.1-15978811，並檢查程式內固定的 SHA-256；已下載後可省略參數。沿用專案 JDK、Android 35 平台與 D8。每次使用全新的暫存編譯目錄，不混入舊 class／dex。

產物：

- `outputs/android/DreamType-0.8.0-experimental.aab`：商店建置候選，不能直接安裝到手機。
- `outputs/android/DreamType-0.8.0-bundle-test.apk`：由 AAB 產生的本機測試安裝檔，不取代 GitHub 已發布 APK。
- `outputs/android/bundle-report.json`：雜湊、工具版本、驗證結果及未完成項目。

二進位檔不提交 Git；既有 0.8.0 發布檔沒有被覆寫。本次未建立新版 GitHub Release。

## 發行方式與簽章

`BuildChannel.PLAY_STORE` 預設 false，GitHub APK 保留 GitHub 更新入口；AAB 建置在暫存目錄提供 true 的版本，改顯示「在 Google Play 查看更新」。目前尚無已發布商店頁，實際連結與商店更新流程尚未驗收。

套件仍為 `tw.localvoice.keyboard`，versionCode 9／versionName 0.8.0。本次衍生 APK 的簽章 SHA-256 為 `8af01d69be8604c2f4a288d55651bb72bed42a391c546f04db4a2a0deb14fc98`，與既有 APK 相同。Google Play App Signing 的註冊／金鑰策略尚未設定；必須在第一次上架前確認，不能僅凭本機同簽章推斷商店安裝一定能覆蓋側載版本。

## 已驗證與缺口

- AAB jarsigner 簽署與驗證、bundletool validate 通過。
- bundletool 能產生 universal APK；APK v2/v3 簽章驗證通過，套件、版本及 IME 元件正常。
- GitHub APK 原始碼分流仍能編譯，沒有覆蓋發布檔。
- 尚未完成：Pixel 9 原生安裝／鍵盤測試、Play Console 上傳驗證、正式 Billing 與後端購買驗證、固定服務入口、審查揭露。
- 此產物 target SDK 仍為 35。2026-09-22 查核 [Google Play 官方要求](https://support.google.com/googleplay/android-developer/answer/11926878?hl=en)：自 2026-08-31 起一般手機新 App／更新需 target API 36。因此目前此產物尚不符合該上架門檻，必須升級並驗證 Android 16 行為。AAB 格式通過不等於商店政策通過。

待發布原始碼另加入離線繁中 [資料說明頁](DATA_DISCLOSURE.md)，仍待原生畫面驗收及完整正式政策。

流程依照 [Android 官方命令列建置文件](https://developer.android.com/build/building-cmdline) 的 protobuf 資源、base module、bundletool 與 jarsigner 作法；工具來源為 [Google bundletool](https://github.com/google/bundletool/releases/tag/1.18.3) 和 Google Maven。
