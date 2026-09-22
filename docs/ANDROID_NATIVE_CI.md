# Android 16 原生模擬器驗證

新增可手動啟動的 GitHub Actions 工作 `android-native.yml`。以 Linux KVM 啟動 API 36 x86_64 模擬器，在 Android 系統內執行 Instrumentation；與既有 JVM 測試分開。實際結果需查看工作及產物，檔案存在本身不代表通過。

## 範圍

- 開啟 HomeActivity，尋找繁體中文登入按鈕並點擊，確認進入 AccountActivity。
- 使用 Android Keystore 儲存、讀回虛構 token；確認 SharedPreferences 沒有直接保存該 token。
- 使用 Android Keystore 加密、讀回合成錄音與語言資料。
- 不連接家中服務，開啟離線 PrivacyActivity，確認中文標題。
- 保存首頁與隱私頁的 Android 實際截圖。

## 隔離

`scripts/build_emulator_probe.py` 只為暫時 CI 環境建立含測試 instrumentation 的 testOnly APK，使用一次性測試簽章，不讀取維護者簽章或金鑰。正式 `outputs/android/build.py` 不會編入 tests 目錄。CI 不上傳測試 APK、簽章、錄音或 token；只保留測試文字結果與合成環境的截圖。

這不是 Pixel 9，也不驗證 Google Play、Surfshark 行動網路、真實麥克風、不同 App 的輸入法插入、TalkBack 或原正式 APK 升級。不能用模擬器通過取代這些驗收。

啟動：`gh workflow run android-native.yml --ref main`。執行前確認 main 為要驗證的來源。流程只有手動觸發，不會每次提交都啟動模擬器。

參考：[android-emulator-runner 官方專案](https://github.com/ReactiveCircus/android-emulator-runner)。

## 首次實際結果

[工作 35718802826](https://github.com/DreamOne09/DreamType/actions/runs/35718802826)，來源 commit `43a84de`，Android 16／API 36 x86_64：Instrumentation 回傳 `dreamtype=passed`、`INSTRUMENTATION_CODE: -1`。首頁登入導向、Keystore 憑證與錄音讀寫、離線隱私頁檢查通過。這次測試先手動清除錄音再登出，因此不把它當成「登出會清除錄音」的獨立證據。

原始結果與截圖：[結果](evidence/android-36-20260922/result.txt)、[首頁](evidence/android-36-20260922/home.png)、[隱私頁](evidence/android-36-20260922/privacy.png)。截圖人工檢視顯示繁中內容與主要按鈕可見；首頁頂端狀態列圖示對比偏低，需要排除啟動截圖時機與系統列外觀問題，尚未完成視覺驗收。
