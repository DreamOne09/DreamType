# Google Play 購買驗證基礎（尚未啟用收費）

`outputs/local_voice/play_billing.py` 是後端驗證介面；目前沒有掛到正式 API、不授予額度、不建立購買資料表，也不會因匯入而連線 Google。現有免費邀請服務維持不變。

## 已實作

- 固定查詢 `tw.localvoice.keyboard` 的官方 `purchases.subscriptionsv2.get`，使用由後端提供的 OAuth 憑證，不相信手機自報付款結果。
- 核對模糊化帳號識別、後端商品／基本方案白名單、訂閱狀態、期限與測試購買標記。取消續訂但仍在付費期限內可保持資格；待付款、暫停、保留與過期不授權。
- 未知狀態、多項目、缺少帳號或不完整回應拒絕處理。測試付款只能以布林 `allow_test=True` 明確允許；畸形標記不能被當作正式付款。
- 前一筆關聯購買只回傳雜湊，供未來交易層撤銷舊權益，避免憑證出現在資料類別或錯誤訊息。
- `ensure_acknowledged` 必須由持久化工作在帳號權益保存後呼叫；每次先重查 Google，已確認則略過 POST。POST 回應遺失時，下一次重查可避免重複確認；POST 成功後仍重查權威狀態。
- 不跟隨重導、不使用環境代理；回應限制 256 KiB。讀取間檢查 15 秒時間預算，另有每次網路讀取的 15 秒逾時，避免持續滴入少量資料造成無限等待。這不是整個購買流程硬性 15 秒的保證；憑證供應端與持久化工作仍須另設期限。

## 官方核對

Google 要求後端驗證、帳號對應、避免重複授權，授權後確認購買，並處理關聯舊購買與撤銷。[安全指引](https://developer.android.com/google/play/billing/security)

回應欄位與狀態依 [SubscriptionPurchaseV2](https://developers.google.com/android-publisher/api-ref/rest/v3/purchases.subscriptionsv2)；確認接口依 [subscriptions.acknowledge](https://developers.google.com/android-publisher/api-ref/rest/v3/purchases.subscriptions/acknowledge)。核對日期：2026-10-18。

## 必須接續完成

1. 明確的 schema 4 → 9 離線遷移與購買金鑰備份已加入隔離演練，見 [付款儲存準備](BILLING_STORAGE.md)；正式主機尚未遷移，仍須與付款版 Store 整合後驗收。
2. 同一資料庫交易中綁定帳號、拒絕跨帳號重用、替換舊訂閱，並以後端政策控制實際錄音額度。
3. 持久化確認與重查工作、Google 通知身分驗證、退款與撤銷同步。訂閱驗證通過不等於這些流程已完成。
4. Android Billing、正式商品設定、Play Console 測試帳號、真實購買／取消／退款／離線重送。使用者目前尚無 Play Console 帳號。

這個介面不會自動退款或撤銷任意傳入的憑證。未來風險處理須先確認購買歸屬及政策，避免攻擊者拿他人的合法憑證觸發錯誤退款。App Store 付款仍是另外的整合需求。

## 證據界線

`test_play_billing.py` 使用合成 Google 回應與 MockTransport，驗證固定官方端點、帳號／商品／狀態核對、回應限制、敏感資訊不外洩、測試標記及確認重試。它證明本地邏輯，不代表 Google 憑證、商品設定或真實交易已驗收。
