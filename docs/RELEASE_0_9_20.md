# 0.9.20：簽章服務網址查詢（候選）

首次設定會從固定 GitHub 位置查詢管理者簽署的最新地址；查詢失敗保留畫面原值。已保存自訂網址不會在開啟畫面時被覆蓋，可主動按「取得最新服務網址」。帳號頁提供「更新服務網址並重新登入」。查詢只改網址欄位，不搬移登入 token，不上傳錄音，也不自動儲存連線。重新登入成功沿用既有 session 替換機制；有未完成錄音時先提醒清除影響。

`ServiceDiscovery` 固定公開資料來源與 P-256 公鑰，驗證 SHA256withECDSA 簽章、服務 ID、24 小時期限、未來時間與單調序號，只接受單層 trycloudflare.com 或 dreamone.li HTTPS origin。拒絕帳密、路徑、port、query、fragment、轉址與過大回應。手機時鐘嚴重錯誤會拒絕資料。下載不帶產品憑證。簽章证明發布者授權該網址，不代表服務永久在線。

## 主機發布

`endpoint_cli.py --work <work-directory> init` 建立 Windows 目前使用者 DPAPI 加密金鑰；不可重跑覆蓋。`sign --url <https-origin>` 產生公開簽章檔。私鑰、序號及主機狀態都在 work，不提交 Git。遺失私鑰或換 Windows 使用者需要復原方案或新版 App 公鑰更新，尚未提供無感輪替。

正式公開資料位於 GitHub `service-discovery` 專用分支的 endpoint.json。分支只包含公開網址資料，不包含主程式、帳號或私鑰。`endpoint_publish.publish()` 使用已有登入的 gh CLI，核對公開服務 ready，以 GitHub 檔案 SHA 防止並行覆蓋。主機 `work/endpoint-discovery.json` 的 enabled 為 true 時，既有維護工作會在網址改變或有效期剩 12 小時內續期。GitHub 授權、Windows 登入或網路失效時會記錄 discovery_publish_failed；不重啟語音服務。

此功能是設定畫面的網址取得與重新登入，並非錄音中無感切換、未完成工作搬移或固定域名。DNS、家用主機斷電及休眠可用性仍未解決。GitHub 故障時可手動輸入網址。

## 驗證狀態

10 組 Python 簽章／發布測試與 14 組維護回歸通過。11 組 JVM 測試包含 Python 簽章與 Java 驗證互通。主機實際簽署、GitHub 發布、無登入下載驗證及維護流程已測，ready/tunnel_ready 為 true，errors 為空。

新增原生畫面競態案例並已編譯，Android 模擬器仍待執行。0.9.20 APK（versionCode 30）已本機打包，保持原簽章；尚未公開發布。Pixel 9 行動網路及 Surfshark 仍待實機驗收。
