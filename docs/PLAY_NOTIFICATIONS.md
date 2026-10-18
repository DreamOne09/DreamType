# Google 訂閱通知

通知模組與路由已加入，正式服務尚未掛載，也尚未建立 Google Pub/Sub 訂閱或憑證。

## 處理邊界

使用 google-auth 驗證 JWT 簽章、有效期間、發行者與 audience，再比對預設服務帳號 email、email_verified、Pub/Sub 訂閱名稱及 Android 套件。固定 Google 公開憑證網址，不跟隨重導；下載最多 256 KiB，每次讀取 10 秒逾時、讀取間檢查 10 秒預算，鎖等待最多 10 秒，快取 5 分鐘。這不是整筆驗證硬性 10 秒上限。

有效的訂閱／訂閱作廢通知只標記 needs_refresh、增加修訂版本、清除舊重試排程，不直接發放或推測權益。背景工作重新查 Google 後才更新資格；較早開始的查驗因版本不符不能覆蓋通知。已替換憑證的通知沿關聯找到最新訂閱。

測試通知回覆成功。未綁定購買暫回 503，讓通知可以重送；不根據通知自動建立帳號或購買歸屬。已停用帳號略過。尚未支援的一次性商品或退款審查通知回 503，不假裝已處理。

HTTP 路由上限 32 KiB、讀取 10 秒、預設每分鐘 60 次及同時 4 筆；取消請求後，實際驗證執行緒完成前仍佔用名額。所有回應 no-store，錯誤不包含 JWT、購買憑證或 Google 回應。

## 尚待正式營運補齊

目前重送通知會再次要求查驗，不會重複發放額度，但尚無持久化 messageId 去重，可能增加查詢與短暫等待。正式啟用前須補去重、無法處理通知的告警與 dead-letter 操作、Google Pub/Sub 實際推送測試，以及退款審查的人工處理流程。不得把 503 重送當作完整退款審查功能。

## 驗證

合成 RSA 簽章測試實際呼叫 Google 官方 Python 驗證函式庫，涵蓋簽章竄改、錯誤發行者／audience、過期／未到期、憑證快取、重導／超量／逾時拒絕。資料庫及 ASGI 測試涵蓋通知交易、舊版本拒絕、替換鏈、錯誤身分／套件、未知購買、HTTP 限制及取消後容量保留。這不代表真實 Google 身分或 Pub/Sub 服務已驗收。

依賴版本在 requirements-billing-lock.txt，測試環境使用獨立安裝目錄；正式主機依賴未更動。

官方依據（2026-10-18）：[Pub/Sub 推送驗證](https://docs.cloud.google.com/pubsub/docs/authenticate-push-subscriptions)、[Play 即時通知與重新查驗要求](https://developer.android.com/google/play/billing/rtdn-reference)、[Google Auth Python](https://pypi.org/project/google-auth/2.62.0/)。
