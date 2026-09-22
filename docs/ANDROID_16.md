# Android 16／API 36 升級驗收

0.9.0 候選版 versionCode 10，compile SDK 36／target SDK 36／min SDK 26。原 0.8.0 APK 與 GitHub Release 保留；0.9.0 已以 v0.9.0-rc1 發布預覽版。0.9.1（versionCode 11）延續相同 SDK 設定，加入主畫面簡化。

## 已完成

- 官方 `platform-36_r02.zip` 已依 Google SDK repository 公布的 SHA-1 `2c1a80dd4d9f7d0e6dd336ec603d9b5c55a6f576` 驗證，下載腳本保留固定版本。
- APK 與 AAB 建置均改用 Android 36 平台；APK 檔名及版本報告改從 manifest 取得，避免繼續寫死舊版號。
- 0.9.0 APK／AAB／衍生 APK 建置成功；bundletool validate、AAB jarsigner 及 APK v2/v3 簽章檢查通過；套件 `tw.localvoice.keyboard` 與維護者簽章維持一致。
- 原始碼檢查：各 Activity 已有系統邊界 inset 處理，沒有自訂 `onBackPressed`；未加入以停用 edge-to-edge 規避新平台要求的設定。這只能證明程式有處理，不能代替實際畫面驗收。

## 裝置上仍須驗收

1. Android 16／Pixel 9 的首頁、登入、設定、編輯與資料說明頁，確認狀態列、導航列、鍵盤及螢幕挖孔不遮住操作。
2. 系統返回手勢、三鍵返回與 App 切換；錄音、結果編輯及保留錄音狀態不應遺失或重複插入。
3. 放大字體、橫向、平板／大螢幕；包含泰文等字體的行高及長文字編輯。
4. 麥克風權限拒絕／重新授權、背景切換、行動網路與 Surfshark、加密錄音恢復。
5. Play Console 上傳與 Play App Signing 設定、從舊側載版更新的實際相容性。

沒有 Pixel 9 或模擬器執行證據時，不得宣稱 Android 16 相容性全部通過。建置成功只完成其中一項上架門檻；付款、固定服務入口與正式資料政策仍待完成。

依據：[Google Play target API 要求](https://support.google.com/googleplay/android-developer/answer/11926878?hl=en)、[Android 16 目標版本行為變更](https://developer.android.com/about/versions/16/behavior-changes-16)、[Android 16 所有 App 行為變更](https://developer.android.com/about/versions/16/behavior-changes-all)。查核日期 2026-09-22。
