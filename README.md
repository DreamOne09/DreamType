# DreamType

![DreamType](outputs/brand/dreamtype-preview.png)

**自然說，清楚寫。** Android 語音鍵盤，由你的 Windows 電腦辨識與整理繁體中文。

[下載 Android APK](https://github.com/DreamOne09/DreamType/releases/latest/download/DreamType.apk) · [安裝步驟](docs/INSTALL.md) · [版本與限制](docs/STATUS.md)

> 目前為 0.3.1 試用版。GitHub 提供程式與安裝檔，不會替你運行 AI。電腦必須開著；新版原生鍵盤仍待 Pixel 9 實機驗收。

## 下一階段：登入即可使用的商店版

已確認方向：上架 Google Play，提供登入與付費機制，由雲端處理語音，使用者不必開自己的電腦。保留整合兩到三個工具／服務的彈性，辨識、文字整理、登入與付款分開設計，避免綁死單一供應商。

這是下一階段規劃，**目前 APK 尚未具備雲端帳號、訂閱或商店上架能力**。現有本機版保留作為開發與效果比較用途；不要求商店版使用者設定私人網址、金鑰或 Cloudflare Tunnel。

詳見 [商店版與多工具整合規劃](docs/STORE_ROADMAP.md)。這次先更新文件，工具名單、訂閱價格與雲端部署仍待選定。

已補上 [三組雲端方案與成本試算](docs/CLOUD_COSTS.md)：以每天 40 分鐘比較 API 費用，包含零碎錄音的成本影響、營運預算與品質驗證方式。屬研究建議，尚未購買或串接服務。

## 0.3.1：更簡單的操作

新 D 字母與聲波 logo；支援 Android 自適應圖示及 Android 13+ 主題圖示。首頁依目前設定狀態，只引導下一步。鍵盤主要按鈕依狀態顯示「開始說話 → 停止並整理 → 插入文字」，結果出來才顯示修改／捨棄。刪除、換行、偏好和連線收進「更多」。

## 我已經有電腦服務，只要裝手機

1. 下載上方 APK，在 Chrome 的「下載」開啟，完成安裝。
2. 開啟 **DreamType**，按「連接電腦」，填入私人電腦網址與金鑰，按「儲存並測試連線」。也可沿用私人配對頁的配對按鈕。
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

## 我的設定

開啟 App 的「我的設定」，或在鍵盤按「更多 → 我的設定」。

- **台灣地名**：內建縣市名稱參考，可開關。鄉鎮、路名、人名等常用詞可以自行加入；不保證同音字完全正確。
- **個人提示詞**：每支手機保存自己的整理偏好，每次錄音獨立套用，不會改其他手機的偏好。最多 2,000 字。
- **常用詞庫**：最多 1,000 字，最常用的放前面；作為語音與文字整理參考。
- **修改文字**：關閉「整理完成後直接插入」，錄音後先按「修改文字」，切換 Gboard 修改。完成後回原 App 切回 DreamType，再按「插入」。新安裝預設先確認，舊版升級保留原設定。捨棄可清掉本次草稿。
- **更新**：管理頁按「檢查 App 更新」，有新版時開啟 GitHub 下載並覆蓋安裝。不是背景自動安裝。

這是每支手機的個人設定，不是多人帳號、管理員權限或跨裝置雲端同步。提示詞與词库會送到你設定的電腦處理，手機端保存設定，伺服器不保存個人檔案。

電腦服務也必須更新到 0.3.0，才能套用提示詞與詞庫。目前使用中的電腦已同步更新。其他電腦可更新 repo 後重新啟動服務；重新開通道可能改網址，需要重新配對。

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
