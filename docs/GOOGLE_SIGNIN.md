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
