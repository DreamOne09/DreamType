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

這不是 Pixel 9，也不驗證 Google Play、Surfshark 行動網路、實體麥克風品質、各種第三方 App 相容性、TalkBack 或原正式 APK 升級。不能用模擬器通過取代這些驗收。

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

## 錄音、HTTP 上傳與插入測試設計

後續探測會透過真實 IME 按鈕開始錄音、停止、等待文字預覽，再按「插入文字」，核對獨立測試 App 的 EditText 完整內容。使用 Android MediaRecorder；跑在模擬器上，聲音可能是靜音，不評分語音辨識品質。

CI 主機的 loopback HTTP 測試服務只接受虛構 token，檢查收到非空 MP4 錄音欄位，再回傳固定的「明天下午四點半到板橋。」。報告只記錄上傳次數與位元組數，不保存音訊。暫時測試 APK 才允許此 HTTP 連線；正式 manifest 與 HTTPS 限制不變，也不連接家中伺服器。這條路徑驗證私人模式的操作與傳輸，不取代帳號模式排隊、結果回執或真實 AI 品質測試。

## 錄音與插入的實際結果

[工作 35724421500](https://github.com/DreamOne09/DreamType/actions/runs/35724421500)，來源 `56d9835`，Android 16 模擬器通過：點擊開始說話、MediaRecorder 錄音、停止、HTTP 上傳、顯示固定繁中回覆、按插入，獨立 App 的 EditText 內容與預期逐字一致。只收到一次上傳，MP4 欄位 27,808 bytes。這是操作與傳輸證據，不是音質、辨識準確率或端到端 AI 延遲測量；畫面中的處理秒數來自合成回覆流程。

保存 [結果 JSON](evidence/android-36-record-insert/ime-result.json)、[Instrumentation 結果](evidence/android-36-record-insert/ime-instrumentation.txt)、[錄音中](evidence/android-36-record-insert/ime-recording.png)、[文字預覽](evidence/android-36-record-insert/ime-preview.png)、[已插入](evidence/android-36-record-insert/ime-inserted.png)。已人工確認最後圖片中的文字位於外部 App，鍵盤提示「已插入，可以繼續說話。」。

測試過程補正了視窗焦點、密碼提示節點更新及插入後畫面重繪的等待；沒有放寬錄音上傳、密碼保護或文字內容條件。前一輪 `35723952005` 也通過內容斷言，但插入截圖早於畫面重繪，因此保存本輪完整證據。這次沒有發布新 APK，測試程式不編入正式版。

## 帳號模式的測試設計

`check_native_ime.py --account` 使用測試專用設定建立虛構的已登入狀態，並重跑原生錄音與外部文字框插入。合成服務檢查 UUID 請求識別碼、回執及語言標頭；依序回傳 queued、running、done，最後只允許一次收到文字的回執。插入完成後，以獨立 Instrumentation 直接檢查手機上的加密錄音檔及暫存檔已不存在，不先呼叫清除或可能順便清除的讀取方法。

這驗證 Android 帳號模式與 HTTP 協定整合；沒有操作登入表單，也沒有連接真實後端／AI。成功回執代表手機已收到文字，不代表使用者已送出聊天訊息。私人模式與帳號模式報告分開保存，後者的結果檔名以 `account-` 開頭。

## 帳號模式的實際結果

[工作 35725665821](https://github.com/DreamOne09/DreamType/actions/runs/35725665821)，來源 `315ccde`：私人與帳號兩條流程均通過。帳號模式收到一次 28,832 bytes 錄音，經 queued → running → done 輪詢、一次回執後，完整繁中文字插入外部測試 App；直接檢查已交付錄音的正式檔與暫存檔均不存在。

證據：[帳號報告](evidence/android-36-account/account-ime-result.json)、[插入斷言](evidence/android-36-account/account-ime-instrumentation.txt)、[錄音清除](evidence/android-36-account/account-delivered.txt)、[已插入截圖](evidence/android-36-account/ime-inserted.png)。截圖已人工確認文字位於外部 App、鍵盤回復「開始說話」。

前一輪第二個案例卡在鍵盤顯示；測試自我 Instrumentation 會重啟目標 App，因此在每個案例設定前先重設模擬器輸入法，再重新選用 DreamType，避免沿用上一個案例的服務連線。這是測試隔離修正，不是正式版設定變更。登入表單、真實後端、斷線恢復及 Pixel 9 仍未由此測試證明。

## 0.9.4 候選版

[工作 35726483810](https://github.com/DreamOne09/DreamType/actions/runs/35726483810)，來源 `39ba910`，重跑私人與帳號模式均通過：[私人](evidence/android-36-094/ime-result.json)、[帳號](evidence/android-36-094/account-ime-result.json)、[完成錄音清除](evidence/android-36-094/account-delivered.txt)。正式候選 APK 使用同來源的產品程式碼與維護者簽章；模擬器仍使用獨立測試 APK，不能當成正式簽章覆蓋安裝的實機證據。

0.9.4 已納入前述首頁系統列修正，另新增接收確認的有限重試：暫時性網路／5xx 錯誤最多三次，只重送可重複確認的 receipt；401 等不可重試錯誤立即停止，不重新送出音訊。新增 `ReceiptRecoveryTest` 的 HTTP 故障注入與其他五組 JVM 測試通過；本輪原生測試只驗證正常路徑，不宣稱已在原生 UI 注入斷線。

[下載候選版](https://github.com/DreamOne09/DreamType/releases/tag/v0.9.4-rc1)。versionCode 14、原 package／簽章，APK SHA-256 `39b8ed78a04043c28384854b6c8a0f4d62836b46a5ea43b0b8b772196b4dc46a`，與 GitHub 發布資產 digest 相符。

## 真正帳號後端的隔離整合設計

`check_native_ime.py --backend` 使用 `native_backend_fixture.py` 建立全新暫存目錄、正式 `install_beta` API、SQLite 與加密儲存。透過管理者 API 建立虛構帳號，再經登入 API 取得真實測試 session；只有這個臨時 token 交給 Android 測試設定。HTTP／ASGI bridge 原樣傳遞 Android 的授權、語言、請求識別碼與回執標頭，交由正式路由與 middleware 處理。

Android MediaRecorder 產生的音訊由 PyAV 實際解碼，正式排隊 worker 使用固定繁中文字的 AI provider。完成後檢查只有一筆 done 工作、一次上傳與回執、資料庫 confirmed=1，且用量等於音訊解碼秒數向上取整，reserved_seconds=0。手機端也檢查插入與錄音清除。

這不包含登入表單操作、真實 ASR／整理模型、HTTPS／Cloudflare 或實體手機；服務 transport 使用測試用 HTTP／ASGI bridge，不能證明正式伺服器程序與網路部署。CI 不讀取家中資料，帳號與資料庫測完刪除，只上傳統計結果與合成文字畫面。

## Android 與正式帳號 API／SQLite 的實際結果

[工作 35728103818（第 2 次執行）](https://github.com/DreamOne09/DreamType/actions/runs/35728103818/attempts/2)，來源 `6dab573`：三條原生流程通過，包含新加入的隔離正式後端。第一次執行在下載 Android Emulator 套件時發生 ZipFile 錯誤，沒有進入 App 測試；未改程式，重跑已結束的工作後通過。

Android 錄音 28,320 bytes，PyAV 解碼 3.136 秒；資料庫只有一筆 done 工作，計入 4 秒、保留額度歸零，provider 呼叫一次、上傳及接收確認各一次。繁中文字成功插入獨立 App；手機保留錄音與暫存檔直接檢查均不存在。

證據：[完整報告](evidence/android-36-backend/backend-ime-result.json)、[插入斷言](evidence/android-36-backend/backend-ime-instrumentation.txt)、[手機錄音清除](evidence/android-36-backend/backend-delivered.txt)、[已插入截圖](evidence/android-36-backend/ime-inserted.png)。已人工確認截圖外部輸入框中的繁中文字與「已插入」提示。

這比固定 HTTP 回覆多驗證了正式帳號驗證、音訊解碼、FIFO worker、加密結果、SQLite 用量與回執整合；AI provider 仍是固定文字，因此沒有新增語音辨識品質或真實模型速度的證據。登入是測試端透過真實 API 完成，尚未測試手機登入表單。此次只有測試與文件變更，沒有發布新 APK。

## 修改頁重建與舊草稿隔離（0.9.6）

[工作 35729978550](https://github.com/DreamOne09/DreamType/actions/runs/35729978550)，來源 `49f4171`：原生 Instrumentation 開啟修改頁、修改繁中文字並選取範圍，呼叫 Activity.recreate 後確認文字與選取位置保留；復原按鈕仍還原初始原文，完成後交回修改文字。另驗證舊頁不能覆蓋新一筆 Draft，登出清除後舊頁不能再存回內容。既有私人、合成帳號及正式後端隔離流程一併通過。

[結果](evidence/android-36-editor/result.txt)、[重建後修改頁](evidence/android-36-editor/editor-recreated.png)。截圖人工確認繁中內容、指引與主要完成按鈕可見；此截图沒有展開 Gboard，因此不代表軟鍵盤彈出或橫向小螢幕版面已驗收。

編輯暫存使用記憶體中的 non-configuration state，不寫入 Bundle／偏好設定；程序死亡仍可能遺失未完成修改。這不是永久草稿，也不是 Pixel 9 實際旋轉測試。0.9.6 候選來源 `b1ecd7a` 相較測試來源只更新 manifest 版號與建置報告，版本代碼 16、原簽章；發布資產雜湊已核對。


## 原生登入表單與 HTTPS：2026-09-23

[工作 35800210436](https://github.com/DreamOne09/DreamType/actions/runs/35800210436)，來源 `59031de`，通過登入表單 → 隔離正式帳號 API／SQLite → 原生錄音 → 文字插入：

- 在真正的 AccountActivity 中，Instrumentation 填入服務網址、帳號和錯誤密碼，呼叫登入按鈕；確認錯誤提示、未建立登入、送出後密碼欄位清空。
- 再填入一次性正確密碼並點登入；確認成功提示、HTTPS 主機、帳號模式與 Keystore 加密保存憑證。
- 使用表單取得的憑證繼續外部 App 的真實 IME 錄音。測試不預先呼叫登入 API 或注入成功 token。
- Android 經過 TLS 到 CI loopback bridge，再由 TestClient 進入正式 API／SQLite。測試專用兩日憑證只加入一次性 debug/testOnly APK；正式 APK、正式 manifest 和正式 resources 不變。
- 伺服器紀錄登入狀態依序為 401、200。一次錄音（27,808 bytes／3.072 秒）、一次 provider 呼叫、計入 4 秒、一次回執，結果完成且手機錄音清除。

保存 [登入原生結果](evidence/android-36-login-https/backend-login.txt)、[整合結果](evidence/android-36-login-https/backend-ime-result.json)、[IME 結果](evidence/android-36-login-https/backend-ime-instrumentation.txt)、[錄音清除](evidence/android-36-login-https/backend-delivered.txt)。JSON 的 response_source 沿用 HTTP/ASGI bridge 名稱，本輪外部傳輸實際為 TLS，另以 https_tested 記錄。

登入欄位由 Instrumentation 的 setText 填入，按鈕用 performClick 觸發，未涵蓋實體觸控打字、密碼管理器、TalkBack。後續 IME 使用實際觸控事件。AI provider 仍為固定文字；本輪不能證明語音準確率、真實翻譯、正式 Cloudflare 部署或 Pixel 9 行動網路已通過。測試憑證、私鑰與帳號資料均不進 Git／發布產物；正式 0.9.8 APK 已檢查不含測試 CA/network resources。


## TLS 回應遺失後恢復：2026-09-23

[工作 35800811740](https://github.com/DreamOne09/DreamType/actions/runs/35800811740)，來源 `a8ef277`，通過正常與故障兩組正式 API／SQLite 隔離環境。故障組仍先操作原生登入表單，再使用其登入憑證錄音。

故障注入在後端完成處理之後、寫出 HTTP 回應之前關閉 TLS socket：第一次結果查詢回應遺失；第一次收件確認已提交資料庫，但回應遺失。下一個相同類型的請求正常回覆。不是預設回傳成功，也未跳過正式結果或用量檢查。

故障組驗證：

- 27,296 bytes／3.008 秒錄音，只上傳一次。
- 一個資料庫 job、一個 AI provider 呼叫；job 完成。
- 收件確認請求兩次，資料庫只有一份已確認回執。
- 用量只計入 4 秒，預留用量回到 0。
- 固定繁中文字完整插入外部 App；手機加密錄音與暫存檔已清除。

[故障組完整結果](evidence/android-36-response-loss/interrupted-backend-ime-result.json) · [正常組](evidence/android-36-response-loss/backend-ime-result.json) · [原生文字插入](evidence/android-36-response-loss/interrupted-backend-ime-instrumentation.txt) · [手機錄音清除](evidence/android-36-response-loss/interrupted-backend-delivered.txt)。

這是原生 Android 在兩次 TLS 回應遺失後恢復的證據，不涵蓋飛航模式、長時間離線、程序被系統終止、Pixel 9／Surfshark 行動網路切換。AI 仍回傳固定文字，不是辨識品質測試。測試沒有改動 0.9.8 的產品程式碼。


## 0.9.10 回歸：2026-09-26

[工作 36214794454](https://github.com/DreamOne09/DreamType/actions/runs/36214794454) 在來源 `d39cab5be9bab3b2d6b948063a038d6cea7c5645` 完成。四條原生流程通過：私人模式、合成帳號 HTTP、正式帳號 API／SQLite 隔離 HTTPS，以及相同 HTTPS 流程遺失查詢與回執回應各一次。測試 APK 從此提交建立，並非直接安裝 GitHub 的維護者簽署 APK。

原生首頁登入導向、Keystore 憑證與錄音、登出清除、離線隱私頁、密碼欄位保護、大圓鈕、選取／emoji 退格、長按連刪、長按上滑翻譯、錄音與固定繁中文字插入通過。故障組只有一次錄音上傳、一次 provider 呼叫、一次完成工作；兩次回執請求沒有重複計費，3.008 秒錄音計入 4 秒。

[私人模式](evidence/android-0.9.10/ime-result.json) · [帳號 fixture](evidence/android-0.9.10/account-ime-result.json) · [正式隔離後端](evidence/android-0.9.10/backend-ime-result.json) · [回應遺失](evidence/android-0.9.10/interrupted-backend-ime-result.json) · [原生安全與首頁](evidence/android-0.9.10/result.txt) · [鍵盤操作](evidence/android-0.9.10/ime-instrumentation.txt)。

這輪原生測試沒有新增「首次 latest-dictation 查詢 503」的故障注入；0.9.10 該修正由七組 JVM 合約中的 HTTP 故障測試驗證。原生回歸證明既有流程未在此次執行退步，不能冒充新增分支已在手機驗證。所有 AI 回應仍為固定文字，Pixel 9、真實辨識、長時間離線與 Surfshark 行動網路仍未驗收。


## 待驗證：保留錄音跨程序重啟

原生工作流程新增兩階段測試：先以真實 Android Keystore 儲存合成帳號憑證及保留錄音，改變目前模式／語言後強制停止 App，再啟動新的 instrumentation 程序。第二階段要求 PID 已改變、憑證可解密、音訊與請求 ID 相同，且重試仍使用錄音原本的日文目標及 zh-TW 來源；最後登出，直接檢查保留檔案與憑證已清除。

此檢查僅放在可拋棄測試 APK，沒有加入發布 APK。當前已通過本機 Android 36 SDK 編譯，原生執行結果待確認。它驗證完整寫入後的跨程序保存，不模擬寫到一半遭終止、裝置重開機、伺服器未完成工作恢復或長時間離線，也不使用真人錄音。
