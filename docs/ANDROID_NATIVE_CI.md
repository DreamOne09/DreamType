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

## 登出清除的直接驗證

[工作 35719296370](https://github.com/DreamOne09/DreamType/actions/runs/35719296370)，來源 `e4b2eb4`，新增直接檢查：先確認加密錄音檔存在，僅執行 `AppConfig.clearSession`，再檢查正式檔、暫存檔及憑證均已清除；不先呼叫 `PendingAudio.clear`，也不以會順便刪檔的 `exists` 當證據。此檢查在 Android 16 內通過，原始 [結果](evidence/android-36-logout/result.txt) 已保存。

這不表示線上帳號已刪除；登出只清除手機登入及本機暫存。

## 首頁系統列與一般啟動

首頁在取得視窗焦點時明確要求淺色背景使用深色系統圖示。Instrumentation 內設定值正確，但即使延後截圖，首頁時間仍曾呈淺色，因此設定值通過不能作為視覺通過的唯一證據。

[工作 35720545412](https://github.com/DreamOne09/DreamType/actions/runs/35720545412)，來源 `c563423`，新增測試結束後 force-stop，再以 MAIN／LAUNCHER 啟動首頁，等待三秒後截圖。[一般啟動首頁](evidence/android-36-launcher/launcher-home.png) 人工檢視可見深色時間與系統圖示，與淺色背景有清楚區別；[原生結果](evidence/android-36-launcher/result.txt) 同時確認登出清除與既有檢查通過。這不解釋所有 Instrumentation 內截圖差異，也不代表不同機型、字級與輸入法畫面已驗收。

首頁設定修正尚未打包到 0.9.3-rc1，待下一個候選版；本次沒有覆蓋已發布 APK。

## 外部 App 的真實輸入法視窗

[工作 35722107778](https://github.com/DreamOne09/DreamType/actions/runs/35722107778)，來源 `5d6f257`：Android 16 模擬器啟用真實 `VoiceIme`，在獨立套件 `tw.dreamtype.fixture` 的文字框測試，一般文字的「開始說話」可用；密碼欄位的同一按鈕停用且顯示密碼保護提示；切回一般文字後恢復可用。

[結構化結果](evidence/android-36-ime/ime-result.json)、[Instrumentation 結果](evidence/android-36-ime/ime-instrumentation.txt)、[一般文字](evidence/android-36-ime/ime-normal.png)、[密碼欄位](evidence/android-36-ime/ime-password.png)、[切回一般文字](evidence/android-36-ime/ime-normal-return.png)。截圖已人工核對按鈕外觀與提示。

前兩次嘗試使用舊的 shell UI dump，只列出輸入 App 的節點，漏掉已出現在截圖及系統狀態中的 IME 視窗，造成測試誤報。改成 fixture 內的 UiAutomation，啟用 `FLAG_RETRIEVE_INTERACTIVE_WINDOWS` 並走訪所有視窗；保持相同啟用／停用條件，沒有放寬判定。

測試 App、Instrumentation、測試簽章都不進正式 APK。此次以測試 App 的 requestFocus／showSoftInput 切換輸入框，未錄音、未連 AI、未插入辨識結果，不能當成完整語音流程通過。Pixel 9、Surfshark 與其他輸入類型仍待驗證。
