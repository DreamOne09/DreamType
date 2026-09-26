# APK 安裝入口與版本一致性

2026-09-26 修正：私人手機測試頁的 `download` 檔名仍是 0.3.1，服務端實際傳回 0.8.0，與 README 建議的 0.9.9 不一致。主機初始下載腳本也仍下載 0.8.0。

現在 `outputs/local_voice/android_release.py` 集中記錄**已發布**測試版的版本、GitHub tag、APK 名稱與 SHA-256。手機安裝端點只提供雜湊符合這份紀錄的本機 APK；檔案不存在或與發布版不同時，導向該 GitHub Release 的確切下載網址。網頁不再指定舊檔名，回應禁止快取及傳送 referrer。這個端點不需要私人服務金鑰，也不把配對資料附到 GitHub 網址。

`scripts/download_runtime.py` 使用同一份版本紀錄；先下載到暫存目錄、核對雜湊，再發布到本機 APK 路徑。中斷或檔案不符不會覆蓋既有檔案，也不會重新下載已符合雜湊的檔案。

目前為 `v0.9.9-rc1` / `DreamType-0.9.9.apk`，SHA-256：

```
c92dd0a442cc22b22dc94d71b42fbe3ea13d98fb4e5f57a9b40ae71ad7d4b963
```

這是測試版入口。GitHub 的正式 stable channel 仍是 0.8.0，沒有把尚未實機驗收的版本改稱正式上線。

## 發布下一版

1. 遞增 Android 版本及 versionCode，保留包名與維護者簽章；不要覆寫已發布版本的 APK。
2. 完成建置、必要合約／原生檢查，再建立 GitHub Release。
3. 確認公開下載可用、檔案雜湊和簽章，才更新 `android_release.py` 與 README 建議下載。不要僅憑本機 build-report 自動改成未發布版本。
4. 驗證 `/download/localvoice.apk` 的檔名、內容雜湊，以及缺少本機 APK 時的公開下載導向。

這不代替 Pixel 9 安裝升級測試、Play 商店發布或簽章驗證。下載網址可用也不代表服務登入及行動網路流程已驗收。
