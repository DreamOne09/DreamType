# DreamType 的 Cloudflare 配置方向

使用者指定 `dreamone.li` 作為 DreamType 網域，不使用或修改個人的 `dreamcube.tw`。建議 `api.dreamone.li` 給手機、`admin.dreamone.li` 給管理後台、`type.dreamone.li` 給下載與說明；尚未修改 DNS 或對外發布。

已查核：指定 Cloudflare 帳戶尚無 `dreamone.li`；公開 NS 查詢指向 Gandi。固定網域需先確認該網域的管理權限與既有 DNS 記錄，避免影響現有網站及信箱。不能把「新增子網域」誤當成可以直接替換整個網域的 DNS。

規劃以 Named Tunnel 取代臨時 Tunnel，家中主機維持 AI 運算。管理後台需先加 Access 政策並測試阻擋未登入者，再發布管理入口；手機 API 必須保留 app 帳號驗證、隔離管理路由及主機私有相容端點。現階段尚未建立 Named Tunnel、Access 應用程式或新的 DNS 記錄。

R2 使用獨立私有 `dreamtype-backups` 貯體。程式設定、驗證與復原步驟見 [R2 備份](R2_BACKUP.md)。目前憑證尚未建立，雲端同步尚未啟用。不得把固定網址、私有貯體存在或傳輸替身測試視為可公開收費上線的證據。
