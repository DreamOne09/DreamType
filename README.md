# DreamType

**自然說，清楚寫。** Android 語音鍵盤，由你的 Windows 電腦辨識與整理繁體中文。

[下載 Android APK](https://github.com/DreamOne09/DreamType/releases/latest/download/DreamType.apk) · [安裝步驟](docs/INSTALL.md) · [版本與限制](docs/STATUS.md)

> 目前為 0.2.0 試用版。GitHub 提供程式與安裝檔，不會替你運行 AI。電腦必須開著；新版原生鍵盤仍待 Pixel 9 實機驗收。

## 我已經有電腦服務，只要裝手機

1. 下載上方 APK，在 Chrome 的「下載」開啟，完成安裝。
2. 開啟 **DreamType**，展開「連接電腦」，填入私人電腦網址與金鑰，按「儲存並測試連線」。也可沿用私人配對頁的配對按鈕。
3. 允許麥克風，在 Android 鍵盤設定啟用 DreamType，保留 Gboard。
4. 到記事本的輸入框切換鍵盤，按「開始說話」，說完按「停止並整理」。

安裝與配對完成後，不需要開網頁。升級直接安裝新版，不用刪除舊版。

## 新電腦第一次設定

此版本支援 **Windows x64 + NVIDIA CUDA 顯示卡**，建議 8 GB 顯示記憶體、16 GB RAM、至少 15 GB 可用空間，並先安裝 Python 3.12 與 NVIDIA 驅動。其他硬體尚未驗證。

下載此 repo 的 ZIP 並解壓縮，或使用 `git clone`。在資料夾開啟 PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

第一次會下載數 GB 的 Whisper、Qwen 模型與運行工具，耗時取決於網速。啟動後會在 `work/pairing.html` 產生私人連線資料，在電腦開啟即可查看；不要上傳或分享給其他人。

停止：`powershell -ExecutionPolicy Bypass -File .\scripts\stop.ps1`

## 怎麼運作

Android 錄音 → HTTPS 通道 → 電腦上的 Whisper 辨識 → Qwen 整理 → 放回手機輸入框。

- 自動整理口頭禪、標點、段落與適合的列點；不承諾逐字正確。
- 不會替你傳送訊息，也不會自動補寫你沒說的需求。
- 沒有按字數計費的 AI API；仍有電費、網路費。
- 手機可用行動網路並保持 Surfshark。錄音經 Cloudflare 代理，並非裝置間端對端加密。
- 臨時通道重開可能換網址，要重新填入 App；換 Android 手機亦需安裝及配對。iPhone 不能安裝此 APK。

## 專案結構

`outputs/android`：原生 Java 鍵盤與建置腳本。`outputs/local_voice`：FastAPI 服務、手機配對頁、整理提示詞。`scripts`：安裝與啟停。`work`：僅在本機生成的模型、私鑰、日誌，不納入 Git。

## 修改與建置

文字整理規則在 `outputs/local_voice/formatting.txt`。修改後重啟服務。

如需自行編譯 Android：先執行 `python scripts/download_android_tools.py`，再執行 `python outputs/android/build.py`。建置會下載官方 SDK / JDK，並在 `work` 產生自己的簽署憑證。自行簽署的 APK 無法覆蓋其他憑證簽署的版本。維護者更新必須保留原簽署憑證，切勿提交到 GitHub。

## 第三方元件

使用 faster-whisper / CTranslate2、llama.cpp、Qwen、Whisper、FastAPI、OpenCC、Cloudflare Tunnel，以及 Android SDK。模型與工具從原始提供者下載，各自遵循其授權；本 repo 不包含模型權重或第三方工具二進位檔。DreamType 與 Typeless 無隸屬關係。
