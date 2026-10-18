# 0.9.21-rc1 交付驗證

2026-10-18。[免費邀請預覽版已發布](https://github.com/DreamOne09/DreamType/releases/tag/v0.9.21-rc1)，尚未上架或開放付費。未登入公開下載的雜湊與 v2/v3 原簽章均再次核對一致，首頁與安裝入口已更新。

## 使用者可見變更

- 上傳按實際寫入位元組顯示進度，與伺服器處理分開。
- 正確比較預覽版次序，rc11 高於 rc2；同版本正式版高於預覽版。不依 GitHub 回傳排序選版本。
- 同期服務部署忠實整理引擎，保留識別碼、引文、中英語序與明確改口；不代為執行口述指令。
- 同期服務隔離常駐語音模型，可終止卡住程序；健康狀態反映模型程序故障，後續請求可重建模型。

錄音大圓鈕、長按上滑翻譯、刪除與復原保留。本機 APK 不含真實 Play 付款；付款候選與 schema 9 沒有部署到目前 schema 4 主機。

## 安裝包來源

| 項目 | 值 |
|---|---|
| package | `tw.localvoice.keyboard` |
| versionName / versionCode | `0.9.21-rc1` / `41` |
| APK 建置來源 | `3ff246e`（後續提交未改 Android 原始碼） |
| 公開資產檔名 | `DreamType-0.9.21.apk`，與建置檔 `DreamType-0.9.21-rc1.apk` 同位元組 |
| 大小 | 74,604 bytes |
| SHA-256 | `818e8bbe95eb13d82dd78d4b7a06262e25e4f253a322b12a51056dd1130a0529` |
| 簽章憑證 SHA-256 | `8af01d69be8604c2f4a288d55651bb72bed42a391c546f04db4a2a0deb14fc98` |

使用原維護者簽章，v2/v3 驗證通過。沒有使用建置時版本覆寫；版本與 Play Gradle 設定一致。公開檔名保留舊 App 可辨識的格式，並提高核心版號，讓既有 0.9.20 更新檢查可發現它。

解壓檔案未發現所檢查的五個已知主機秘密值或禁止的測試／資料檔名；不代表全面安全稽核。

## 驗證

- [Android 16 原生流程](https://github.com/DreamOne09/DreamType/actions/runs/39108014055)：成功；覆蓋錄音、輸入、取消／復原、翻譯選單、Keystore、重啟保留錄音、明文快取清除與斷線回應恢復。使用隔離測試帳號和合成 provider，不是 Pixel 9 或語音準確率證據。
- [Play APK/AAB/lint](https://github.com/DreamOne09/DreamType/actions/runs/39108067856)：成功；輸出仍是無簽章建置候選，不能當成可安裝升級或 Play 上架。
- [後端與 JVM CI](https://github.com/DreamOne09/DreamType/actions/runs/39108220924)：251 項後端、16 項腳本測試、22 組 JVM 契約與真實 faster-whisper 視窗提示詞契約通過。
- 真實公開錄音與 ASR 子程序恢復證據見 [REA 升級紀錄](REA_UPGRADE_2026_10_18.md)。仍有同音字、專名及短句漏辨問題，不宣稱第一流準確度。

## 必須保留的限制

Pixel 9 行動網路＋Surfshark、實際覆蓋安裝、母語翻譯檢視、真實付款、iOS 與商店審核未完成。固定服務網址是 `https://dreamtype.dreamone.li`；家用主機必須在線，沒有雲端推論備援或可用性 SLA。

更新應直接覆蓋，不先解除安裝；Android 不支援直接覆蓋降版。後端保留本機回復檔與 schema 4，未遷移付款資料庫。復原金鑰仍須獨立安全保管，R2 下載驗證不等於另一台電腦完整復原。
