# Google 自助登入實作狀態

## 產品路線

Android 優先使用 Google 身分建立／找回 DreamType 帳號；現有邀請帳號保留。不能依信箱、姓名或手機提供的 uid 自動連結舊帳號。未來連結既有帳號須同時證明既有 DreamType 登入及新的 Google 身分，不能以客服手動改信箱取代。

## 已實作的驗證層

`google_signin.GoogleSignIn` 使用 google-auth 驗證 Google 簽章、issuer、固定 server client ID audience 與時間，再檢查 authorized presenter、最近五分鐘的互動憑證及本次 43 字元 URL-safe nonce。Web client ID 與可接受的 Android presenter 都只能由服務端設定；不是請求參數。輸入最多 16 KiB，失敗不輸出原始 token／claims。憑證下載沿用有大小／時間限制及記憶體快取的官方憑證傳輸。

驗證結果只回傳 provider=google 與固定 subject；不回傳信箱、姓名或照片，也不把 email_verified 當作既有帳號的恢復權。Google 對外部信箱的 verified 宣告不一定代表目前仍擁有該信箱；用 subject 登入與用信箱驗證是不同事情。

測試使用現場產生的 RSA 金鑰與合成憑證，驗證跨 App、nonce、issuer、過期／過舊／未來時間、竄改簽章與輸入限制。不是實際 Google 帳號登入驗收。

## 尚未接線，不能開放登入

此類別沒有 HTTP route、不建立 session、不儲存帳號，也不會自行防止同一合法憑證重播。**不可直接將 verify 的成功結果當成完整登入。** 接線必須完成：

1. 服務端產生並保存短效一次性 challenge，綁定發起登入的客戶端秘密；nonce 不得由呼叫者任意指定。
2. 驗證成功後，以同一資料庫交易消耗 challenge、對應 provider/subject、確認帳號未停用並建立 session；重播、併發與帳號刪除／復原必須有測試。
3. 明確資料庫遷移、加密備份／刪除記錄相容；新帳號不能從自助註冊獲得任意免費額度或付費權益。
4. HTTP 有界接收／頻率與併發限制；網頁需綁定登入發起者，防止 login CSRF；Android 需設定正確 client ID、套件及簽章憑證。
5. 原生 Google 登入、取消／換帳號／跨裝置恢復、設定載入及實際測試帳號驗收。OAuth client 設定仍未建立；線上邀請登入不受這個模組影響。

iOS 尚需自己的原生登入與 App Store 要求評估，不能以 Android Google 登入完成取代。

依據：[Google ID token 後端驗證](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token)、[Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect)。

## 一次性登入儲存（schema 11 候選）

`signin_migration.prepare_signin(root)` 明確離線升級 10→11；先檢查原有付款／通知資料表、完整性、待處理錄音與收件，取得維護及寫入鎖並完成加密備份後，才在同一交易建立身分與 challenge 資料表。啟動不自動遷移，正式主機仍為 schema 4。

`SignInStore` 建立五分鐘 challenge，包含隨機 nonce 與只回傳一次的客戶端秘密；資料庫只留秘密雜湊。最多保存 1,000 筆未到期請求，定期清理或建立下一筆時清除過期資料。Google 驗證在資料庫寫入鎖外進行，成功後重新檢查 challenge、帳號是否啟用，再以單一交易消耗 challenge、建立／尋找身分及發出七天 session。相同 challenge 最多成功一次；多個獨立 challenge 的相同 Google subject 仍對應同一帳號。

`signin` 找不到帳號時拒絕，不重建已刪除帳號；只有明確 `signup` 意圖能建立新帳號。新帳號沒有可用密碼、沒有免費額度，不會自動連結現有邀請帳號。原有密碼帳號保持不變。停用帳號不得繞過到 signup 重新取得權限；真正刪除後的明確 signup 可以建立全新的零額度帳號，不復活舊 uid／偏好／訂閱。

加密備份保留 provider/subject 對應；不保留登入 challenge 或 session。還原會再次清除 challenge，並依最新刪除紀錄連動移除身分。schema 9／10 的備份繼續支援。遷移或 session 寫入失敗須回滾整個交易，不能只留下空帳號或提早消耗 challenge。

這些目前是可測試的儲存服務，仍未接 HTTP、設定或手機 UI。開放前還必須完成原生 Google 登入、發起者綁定與 login CSRF、接收／驗證限流、身分連結及 Google-only 帳號以重新驗證身分刪除帳號的流程；既有密碼刪除介面不能直接套用 Google-only 帳號。不得先開放註冊再補資料刪除。

## Google 身分重新確認與刪除（schema 12 候選）

`reauth_migration.prepare_reauth(root)` 明確離線升級 11→12；沿用加密預備份、維護／寫入鎖、錄音與收件檢查及 DDL 失敗回滾。現有登入 challenge 不改用途，另設 `deletion_challenges`，防止一般登入憑證被當成刪除確認。線上尚未遷移。

`GoogleAccountDeletion` 只接受已登入且綁定 Google 的啟用帳號。每個帳號最多一筆五分鐘刪除確認，綁定發起的 session 雜湊、隨機秘密雜湊與 Google nonce；重新發起會使前一筆失效。確認時要重新驗證同一個 Google subject。網路驗證之後，在寫入交易內再次檢查 session、啟用狀態、身分與 challenge，才刪除帳號、連動資料、全部 session 及帳號 audit，並寫入既有 uid-only 刪除紀錄。刪除紀錄寫入失敗會回滾帳號刪除。

登出／撤銷 session 會連動移除其刪除確認；備份不保存刪除確認，還原也再次清除。最新刪除紀錄會移除舊快照的帳號及 Google 身分對應。這不是異機復原驗收。

回應明確為 `deleted=true`、`subscription_cancelled=false`。**刪除 DreamType 帳號不會取消 Google Play 訂閱或自動退款。** 客戶端在送出刪除前必須告知並提供商店訂閱管理入口，讓使用者自行決定；不得宣稱付款停止。重新註冊不復活舊資料或自動搬移舊購買權益。

儲存層已補刪除能力，HTTP、Google OAuth 設定、原生／網頁重新驗證與清楚的刪除確認介面仍未接線。未接齊前不能開放自助註冊。

## HTTP 與啟用設定（預設停用）

`server.py` 讀取私人 `work/signin-config.json`。不存在或只有 `{"enabled": false}` 時不安裝 Google routes。啟用內容必須完整包含 `enabled: true`、實際 OAuth `client_id`、`presenters` 陣列與布林 `allow_signup`；設定最多 16 KiB，檔案須位於 work 內。需要既有 google-auth dependency overlay；錯誤設定拒絕啟用，不默默降級。先以唯讀方式確認完整 schema 12，才建立共享帳號服務。

| 路徑 | 方法與內容 | 用途 |
|---|---|---|
| `/v2/auth/google/config` | GET | 公開 client ID 與註冊開關，不包含秘密 |
| `/v2/auth/google/challenge` | POST `purpose: signin / signup` | 產生一次性登入請求 |
| `/v2/auth/google/complete` | POST `challenge, secret, id_token` | 驗證後發出 DreamType session |
| `/v2/me/google/delete/challenge` | POST `{}`，Bearer session | 為目前登入產生刪除確認 |
| `/v2/me/google/delete/complete` | POST `challenge, secret, id_token, confirm: true`，相同 Bearer session | 重新驗證並刪除帳號 |

所有請求需 `X-DreamType-Client: web` 或 `android`。網頁變更請求必須帶固定 `https://dreamtype.dreamone.li` Origin；唯讀 config GET 若未帶 Origin，必須帶 `Sec-Fetch-Site: same-origin`；不同 Origin 或跨站 Fetch Metadata 一律拒絕。原生允許沒有 Origin，但這不是裝置認證。使用 JSON／自訂標頭強制瀏覽器跨站 preflight，未授予 CORS。前端必須在自己的登入操作中產生並持有 challenge/secret，不能接受網址或其他頁面提供的登入 callback 資料；Google credential 的 nonce 必須對應這次 challenge。

Router 在讀取 body 前限制全服務每分鐘 60 次與同時 4 筆，body 上限 24 KiB、讀取 10 秒、拒絕壓縮或未知欄位；回應不快取。取消 HTTP 等待不會讓仍在驗證的執行緒提前釋放名額。資料庫及驗證 I/O 在背景執行緒進行。這是單主機限制，不代表分散式防濫用或裝置可信。

只有這五個已安裝路徑交由專屬 router 驗證；其餘 v2 路徑維持原本登入／管理權限。關閉 `allow_signup` 同時拒絕新的 signup challenge 及先前尚未完成的 signup，不影響既有 Google 帳號登入。

整合測試透過完整 install_beta 和合成 RSA Google proof 完成註冊、零額度查詢、重播拒絕及重新驗證刪除；另外驗證非法來源、body 上限／逾時、HTTP 取消後名額保留與未設定時路由不存在。沒有真實 Google OAuth 帳號驗收，沒有啟用線上設定。手機／網頁 UI 及完整真人流程仍待完成。

## Android 候選介面

Play build 新增 `GoogleAccountActivity`，使用官方 Credential Manager 1.6.0 與 googleid 1.2.1（固定依賴鎖）。從「我的帳號 → Google 帳號登入與管理」進入，先讀取服務設定，才顯示登入／允許時的註冊。未啟用時顯示可返回原帳號登入的說明，不啟動 Google 選帳號畫面。新安裝預設改為固定 `https://dreamtype.dreamone.li`，不覆蓋既有自訂網址。

Google ID token 與 challenge 只存在記憶體；只送往固定 DreamType HTTPS origin，不使用任意輸入的主機網址。換登入前明確確認舊登入及未完成錄音的處理；成功後沿用既有 session 比對、加密儲存及偏好更新。Activity 關閉或 session 已變更時拒絕遲到回應，未採用的新 session 嘗試在服務端撤銷。

已連結 Google 的帳號顯示 Google Play 訂閱入口及永久刪除確認。刪除前再次告知不會取消訂閱，並用相同 nonce 流程重新驗證。原帳號頁透過 `/v2/me` 的 `login_methods` 隱藏 Google-only 帳號不適用的密碼修改／密碼刪除。回應不包含密碼雜湊或 Google subject。登出清除應用程式憑證狀態；不會登出整支手機的 Google 帳號。

本候選尚未發布新版簽章 APK，真實 OAuth client ID／Android 套件簽章／測試使用者尚未設定。編譯與 lint 不代表 Pixel 9、Google 選帳號、TalkBack、旋轉／背景切換或真實刪除已驗收。Google 品牌按鈕及正式同意畫面仍需上架前檢視；iOS 與網頁 Google 介面未在此批完成。

官方依據：[Credential Manager 實作](https://developer.android.com/identity/sign-in/credential-manager-siwg-implementation)、[穩定版資訊](https://developer.android.com/jetpack/androidx/releases/credentials)、[Google nonce builder](https://developers.google.com/identity/android-credential-manager/android/reference/com/google/android/libraries/identity/googleid/GetSignInWithGoogleOption.Builder)。


## 網頁候選介面（2026-10-18）

帳號頁及語音輸入頁共用 `google_account.mjs`。使用者先選擇 Google 帳號方式，再選登入或服務允許的註冊，才載入官方 Google Identity Services script 並顯示官方按鈕；沒有 One Tap 或自動登入。未啟用時保留邀請帳號登入。只在固定 DreamType origin 運作，不讀取 URL 或跨視窗傳入的 credential/challenge。

每次驗證使用服務端 nonce，提供取消與四分鐘內的到期提示。取消後忽略舊 callback；完成時核對同一個分頁 session，未採用的已建立 session 嘗試撤銷。憑證不放入 localStorage/sessionStorage、網址或日誌。Google-only 帳號隱藏密碼刪除，改為明確永久刪除確認及 Google 再驗證，並連結 Play 訂閱管理，說明刪除不等於停訂或退款。

只有使用者頁面加入 Google GIS 指定的 script/style/frame/connect CSP 路徑及 popup policy；管理者頁面維持原限制。Google SDK 只有使用者主動進入驗證時才載入。依據：[Google 網頁設定與 CSP](https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid)、[JavaScript API](https://developers.google.com/identity/gsi/web/reference/js-reference)。

隔離 Chrome 驗證登入、註冊開關、nonce、取消後舊 callback、刪除確認、Google-only 欄位、登出、手機寬度及未啟用回退；原有詞庫衝突、錄音、重試、翻譯設定、收件與復原測試維持通過。合成 Google SDK 並不代表真實 OAuth/FedCM/跨瀏覽器驗收。仍未部署新 schema、啟用 OAuth 或發布新簽章 APK；上述早期段落描述的是各階段當時的進度，最新客戶端候選已包含 Android 和網頁。
