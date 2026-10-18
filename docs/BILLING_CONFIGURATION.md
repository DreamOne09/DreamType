# 主機付款設定入口

server.py 已讀取 WORK/billing-config.json，載入成功後將 runtime 交給錄音服務。沒有檔案或內容僅為 {"enabled": false} 時維持試用；數字 0、字串 false 或不完整設定不算關閉。已標記付款的資料庫即使刪除設定，也會由 Store 拒絕退回試用。

## 設定格式

啟用設定只接受 enabled、products、push、credentials_file 四個欄位。enabled 必須是真正的布林 true。

- products：1–20 個商品，每筆 product_id、base_plan_id、plan、monthly_seconds，必須使用 Play Console 實際建立的商品；重複、未知欄位或不合法額度拒絕。
- push：audience 固定為 https://dreamtype.dreamone.li/billing/google/play/notifications，email 是專用推送服務帳號，subscription 是對應 Pub/Sub 訂閱完整名稱。
- credentials_file：WORK 直屬的服務帳號 JSON 檔名。禁止路徑分隔、上層路徑、磁碟名稱或解析到 WORK 外的檔案。設定最多 32 KiB，憑證最多 64 KiB，以有界讀取防止檔案變更繞過大小限制。

憑證只使用 Google 官方 OAuth endpoint 與 androidpublisher scope，不跟隨重導、不使用環境代理，回應最多 64 KiB。每次網路讀取逾時 10 秒，讀取間另檢查 10 秒預算；憑證刷新鎖最多等 10 秒。這不是整個付款請求的硬性 10 秒期限。成功 token 留在記憶體供有效期間內重用，失敗只回通用錯誤。

## 啟用條件

本次沒有建立正式設定或憑證，也沒有更動線上服務。啟用前需完成 Play Console／Google 權限、真實購買與通知驗收、通知去重與告警、管理 UI 付款模式、離線遷移備份及復原演練。載入設定本身不遷移資料庫；schema 4 搭配付款政策會拒絕啟動。

Google 服務帳號憑證不是目前 DreamType 備份封存的成員。災難還原必須另外從安全保管處重新提供或重建憑證，不可假設 R2 備份包含它。不得把設定中的真實服務資訊或私鑰提交 Git。

測試以短暫產生的 RSA 金鑰及 MockTransport 驗證 OAuth scope、快取、重導／逾時拒絕、設定格式與目錄限制。沒有向 Google 取得真實 access token。
