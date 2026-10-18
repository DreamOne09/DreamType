# 固定服務網址與邀請入口

目前服務入口為 `https://dreamtype.dreamone.li`。管理頁與簽章網址發布程式共用 `service_address.fixed_address`，避免邀請頁顯示舊臨時網址，或換機後發布程式只能尋找 Quick Tunnel。

私有 `work/endpoint-discovery.json`：

```json
{"public_url":"https://dreamtype.dreamone.li"}
```

固定入口只允許 `dreamone.li` 下的 HTTPS 原點，不接受路徑、連接埠、使用者資訊、查詢或其他網域。此檔不含憑證，但仍與主機設定一起放在忽略的 work 目錄。它不會自行建立 DNS 或 Tunnel；固定通道必須另外完成設定。

設定錯誤時停止網址發布，管理頁顯示設定有誤，不退回歷史網址。`tunnel-config.json` 指定 `mode: named` 而沒有固定網址時，也不會發布臨時通道。沒有固定設定的既有 Quick Tunnel 安裝仍可使用發布程式。

管理頁不再讀 `logs/tunnel.err.log` 作為目前地址，也不相信請求的 Host／X-Forwarded-Host。臨時入口只有未過期、時間合理的 `endpoint-published.json` 才會顯示，並標示其可能改變；舊日誌、過期或不符模式的發布紀錄不提供邀請網址。

固定設定與發布紀錄都是地址來源，不是在線證明。管理者仍需確認公開 `/health` 與主機狀態。發布程式保留既有公開健康檢查、簽章及 GitHub 版本比對更新；有效快取期間不會每次重新發布。

測試 `test_service_address.py` 覆蓋舊日誌、過期紀錄、錯誤設定、named 模式缺設定及管理 API 的 Host 偽造。`test_endpoint_publish.py` 覆蓋固定網址不查 Quick Tunnel、替換舊入口與錯誤設定不發布。
