# 上線狀態（2026-10-18）

目前是可下載的封閉測試產品，尚不能公開付費上線，也沒有證據證明整體比 Typeless 更好。本文彙整當前差距，歷史版本文件的完成項目不能代替這些門檻。

最新預覽版為 [0.9.21-rc1](https://github.com/DreamOne09/DreamType/releases/tag/v0.9.21-rc1)，versionCode 41。已修正上傳進度與預覽版更新判斷，沿用原套件與簽章。公開未登入下載雜湊、v2/v3 簽章、22 組 JVM 契約、Android 16 原生流程與 Play APK/AAB/lint 已核對；Pixel 9 與真實付款仍待驗收。詳見 [版本證據](RELEASE_0_9_21.md)。

| 要求 | 已有證據 | 尚缺 |
|---|---|---|
| 台灣中文輸入 | 19 件基礎、5 件較長、6 件個人提示詞邊界合成文字結果；兩組共 132 段公開台灣短句 CPU ASR 比較、96 段同機 GPU 比較（見 GPU_ASR_COMPARISON.md）；台灣字形與個人排版偏好 | 自然長口述、更多台灣口音與中英夾雜（另有 ASCEND 香港自然混說 96 段比較，見 NATURAL_CODESWITCHING.md）、長時負載與自然口述驗證（省 RAM 後 Breeze 三輪完整 API 通過，見 ASR_PROFILES.md）、同批音訊與 Typeless 比較 |
| 多語翻譯 | 八種目標、模型與 JVM API 測試 | 各語言母語品質檢視及實機使用 |
| 手機體驗 | 0.9.21-rc1 APK（下載雜湊與原生回歸通過，更新安裝 UI 仍待 Pixel 9 驗收）；Android 16 模擬器首頁導向、Keystore、登出清除、離線隱私頁、密碼欄位保護；私人與帳號模式錄音／固定繁中文字插入、帳號輪詢回執與錄音清除通過；新程序可解密保留錄音及原語言，啟動清除遺留明文快取（見 ANDROID_NATIVE_CI.md） | Pixel 9 登入輸入操作與正式部署整段流程、長時間離線、寫入途中終止及裝置重開機恢復、Pixel 9 安裝升級、Keystore、輸入法、TalkBack、Surfshark 行動網路 |
| 多人使用 | 十二帳號突發：9 筆接受、3 筆排隊滿拒絕，被拒不扣費，最後一筆原約 62 秒，16 層 GPU 配置回歸約 54 秒（見 TRANSLATION_GPU.md）；排空後恢復（見 CAPACITY.md）。三帳號 5／30／60 秒中文整理、日英翻譯十輪共 30 筆完成，跨帳號拒絕與回執用量正確；有限優先排程與 FIFO 接續比較，短整理當次 14.87→10.45 秒；跨帳號讀取拒絕與用量驗證 | 仍需等待正在處理的長翻譯；全天／開放式到達負載、更多語言、自然長口述及外部網路容量 |
| 資料與恢復 | 加密資料、每份新備份自動記憶體還原驗證、複製內容核對與失敗保留舊副本（見 BACKUP_COPY.md）、備份／驗證中斷無明文暫存測試、刪除紀錄、程序突然退出及未提交交易回滾測試 | 異機完整還原與復原金鑰分開保管、備份保留政策、其他安裝的舊版遺留暫存檢查、獨立安全審查 |
| 服務入口 | 家用主機、dreamtype.dreamone.li 固定 Cloudflare Tunnel、簽章網址查詢與續期 | 休眠／斷電可用性與外部離線通知 |
| 商店與付款 | main 已有 Play Billing、伺服器購買驗證、訂閱權益、背景重新查驗、RTDN 身分驗證與去重、退款相關異常提醒；unsigned APK/AAB/lint 通過 | 線上尚未啟用；Play Console／商品／服務帳號／Pub/Sub 設定、真實付款與退款生命週期、正式簽章上架及資料揭露 |
| iOS／App Store | 目標已確認；共用服務端可供未來客戶端使用 | iOS 原生鍵盤與登入／購買／更新實作、Apple Developer、Mac／iPhone、商店及實機驗收；Android 證據不能代替 |

沒有付款接入前維持邀請免費試用；不以手機聲稱付款作為授權依據。固定入口已可用；仍須核發試用帳號，尚未完成公開自助註冊付費。

手機與後端整合補充：Android 16 已透過 HTTP／ASGI bridge 接上隔離的正式帳號 API／SQLite，驗證實際錄音解碼、排隊、文字插入、一次用量計入、回執及錄音清除。新增原生登入表單經隔離 HTTPS 取得憑證後接續錄音，錯誤密碼亦驗證拒絕；欄位由測試程式填入，AI provider 為固定文字。仍缺實機登入輸入操作、真實 AI、正式 HTTPS 部署與 Pixel 9 的整段驗收。詳見 [原生證據](ANDROID_NATIVE_CI.md)。

下一個最有價值的外部證據是 Pixel 9 驗收，以及獨立設備上的完整復原演練；可先用 [手機驗收步驟](PIXEL9_ACCEPTANCE.md)，不需要 USB。

詳細證據：[中文品質](CHINESE_QUALITY.md)、[翻譯](TRANSLATION.md)、[容量](CAPACITY.md)、[恢復](RECOVERY.md)、[刪除還原](DELETION_RECOVERY.md)、[商店規劃](STORE_ROADMAP.md)。

0.9.7 圓形錄音／停止、直接退格／連刪及長按上滑翻譯已通過 Android 16 實際觸控測試（私人、帳號及正式 API 隔離環境），詳見 [鍵盤操作與證據](KEYBOARD_INTERACTION.md)。

原生連線恢復補充：Android 16 已驗證查詢回應與已提交收件確認回應各遺失一次後，仍完成文字插入；錄音上傳與 provider 呼叫各一次，用量不重複計入。這不取代實機行動網路／長時間離線測試，詳見 [原生證據](ANDROID_NATIVE_CI.md)。

0.9.9 已加入口述指令防擴寫檢查、辨識原文還原及插入撤回。Android 16 模擬器通過四種連線流程與撤回／選取文字還原；仍不等同於 Pixel 9 或完整語意品質驗證，詳見 [修正及限制](DICTATION_ONLY.md)。

翻譯角色隔離補充：專用翻譯模型取代聊天模型的英文橋接，新增捏造標記拒絕；合成測試仍找到日文漏限制條件，因此不把「指令不執行／忠實翻譯」列為全面驗收通過。見 [翻譯證據](TRANSLATION.md)。

日文路線補充：中文改為直接翻日文，八案比較中修正已發現的星期／時間添加／限制漏譯。仍有主詞不清楚與自然度問題，不代表全面通過，見 [最新日文比較](TRANSLATION.md)。


## 部署與原始碼的界線（2026-10-18）

| 層級 | 已核對狀態 | 不代表 |
|---|---|---|
| 家用正式主機 | 固定 HTTPS 入口、schema 4 免費邀請帳號、中文整理／翻譯、常駐 ASR、R2 加密同步；新版管理頁已部署 | 付費服務、無人值守可用性或異機復原完成 |
| GitHub main | PR #90–#107 的付款模組、Google 身分驗證／schema 11–12、Android 與網頁登入／再驗證刪除候選 | 這些付款後端模組已部署或 Google 已驗收 |
| Android 候選 | PR #106 已加入 Credential Manager Google 登入與刪除，23 組 JVM 契約及 unsigned Play APK/AAB/lint 通過 | 已發布新的簽章 APK、已在 Pixel 9 使用，或真實付款通過 |
| 已發布 APK | 上方 0.9.21-rc1 仍為下載版本 | 包含之後 main 的所有修正 |

付款相關部署必須先完成 [設定條件](BILLING_CONFIGURATION.md)、[schema 4→9 離線遷移](BILLING_STORAGE.md) 與 [9→10 通知遷移](NOTIFICATION_STORAGE.md)。預設啟動不自動遷移；不能為展示功能直接把線上試用資料庫切成收費模式。

證據：[PR #100](https://github.com/DreamOne09/DreamType/pull/100)、[後端與網頁檢查](https://github.com/DreamOne09/DreamType/actions/runs/39115925085)、[Play 建置與 lint](https://github.com/DreamOne09/DreamType/actions/runs/39115919388)。這些是程式與隔離測試證據；正式退款審查、失敗佇列及離機告警仍見 [付款維運缺口](BILLING_OPERATIONS.md)。

正式交付還需要完成真實 OAuth 設定／公開註冊驗收與身分恢復、外部離線通知、離機金鑰保管與異機還原、自然語音及 Pixel 9 驗收。商店帳號與實機尚未提供，先繼續不依賴這些條件的工作；不以增加測試數量或合併次數當作可商用證明。

## 最新可接續狀態

2026-10-18：REA 靜態研究已完成限定範圍分析；忠實整理引擎與可終止的常駐 ASR 程序已部署，保留 live schema 4。完整後端回歸 248 項通過，新增健康逾時測試亦通過；公開音訊 12 筆中 11 筆成功、1 筆漏辨，不宣稱第一流準確度。Android 16 工作 39107455190 通過原生流程；Pixel 9 仍待驗收。0.9.21-rc1 已發布並完成公開下載核對。詳見 [本輪證據與限制](REA_UPGRADE_2026_10_18.md)。

- 上一輪 [0.9.11-rc1](https://github.com/DreamOne09/DreamType/releases/tag/v0.9.11-rc1)，versionCode 21，完成家中下載入口與健康檢查；目前已由本文開頭的最新版本 取代。仍維持免費邀請試用。
- 正式辨識仍為 Turbo。新固定 96 段比較中，Breeze CER 5.97%、Turbo 14.63%，但 Breeze 有 8 段退步，且兩次 CPU 比較速度排序不同；沒有宣稱 GPU／手機更快。見 [完整比較](ASR_MODEL_COMPARISON.md)。
- Breeze 固定模型已下載、同機 GPU／三模型共載／三輪 API 測試已完成；正式服務仍為 Turbo。Qwen 改用 `--load-mode none` 後完整 API 測試可用 RAM 最低約 819 MiB，仍需長時間驗證。舊版下載前資源快照不是目前部署狀態；見 [記憶體測試](MEMORY_TUNING.md) 與 [完整 API](ASR_PROFILES.md)。
- 目前主機的加密備份已完成新版記憶體驗證，未改正式資料庫；當次未發現舊版備份暫存目錄。R2 已啟用自動加密同步；2026-10-18 再次下載並完成解密、資料庫與刪除紀錄驗證，未覆蓋正式資料庫。尚不代表異機復原。
- 下一輪重點仍是 Pixel 9 實機驗收、獨立保管復原金鑰及異機還原、台灣自然長口述、辨識否定／專有名詞品質，以及 Play Console／正式付款。尚無證據支持公開付費上線或整體優於 Typeless。

本輪接收資源審查已修正 queue 前的上傳／解碼併發缺口，並新增取消與逾時測試；剩餘安全範圍見 [接收資源審查](UPLOAD_ADMISSION.md)。不因這項修正將獨立安全審查或公開上線標為完成。


## Google 帳號整合候選

[PR #106 Android](https://github.com/DreamOne09/DreamType/pull/106) 與 [PR #107 網頁](https://github.com/DreamOne09/DreamType/pull/107) 已補上 Google 登入、明確註冊與再次驗證刪除。Android 最終來源 Play 建置見 [39118297785](https://github.com/DreamOne09/DreamType/actions/runs/39118297785)。網頁使用官方 GIS 按鈕，只有主動選擇時載入 Google script；Google-only 帳號不顯示無法使用的密碼刪除，並清楚告知 Play 訂閱須另行取消。

正式主機仍是 schema 4，沒有 OAuth client 設定，這些功能未在線上啟用；下載 APK 仍是原版本。下一次部署必須先演練逐級 4→9→10→11→12 遷移／還原，準備 OAuth client 與 Android 簽章設定，完成 Google 帳號建立、跨裝置登入、取消、停用、刪除及恢復購買的真人驗收。Google 登入本身不開通付費權益，註冊新帳號預設零額度。不得只部署網頁按鈕就宣告服務可商用。詳見 [Google 登入文件](GOOGLE_SIGNIN.md)。
