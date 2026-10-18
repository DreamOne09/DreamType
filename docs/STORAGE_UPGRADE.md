# 帳號資料庫的離線升級與回復

Google 登入候選使用 schema 12；目前正式主機仍為 schema 4。部署程式檔案不會自動升級資料庫，也不能把舊程式重新指向新版資料庫當作回復。以下工具只準備儲存格式，不啟用 Google、自助註冊或付款，也不停止／啟動服務。

## 先檢查，不改資料

在包含新版模組及依賴的候選 checkout 執行，`--root` 指向目標安裝根目錄，**不是其 work 子目錄**。請先把範例路徑替換成核對過的實際目標：

```powershell
python outputs/local_voice/storage_upgrade.py inspect --root "C:/DreamType-installation"
```

回應只包含 schema、下一個支援版本、待處理數量、既有收費政策標記與阻擋原因，不列出帳號、提示詞或金鑰。找不到資料庫時拒絕，不會建立空安裝。檢查完整性、已知資料表、未完成錄音／收件、備份所需主機金鑰存在與既有 uvicorn 程序；拒絕已知路徑跳出選定安裝目錄。

`ready_for_next_step` 是當次預檢結果，不是持續的鎖或保證。正式操作前必須停止該安裝的服務與自動重啟排程，確認工作排空，保留相容程式版本及獨立保管的復原金鑰。預檢不會替你取消錄音、放棄收件或終止程序；不同啟動方式的程序仍需由操作人員確認。

## 一次只提交一階段

```powershell
python outputs/local_voice/storage_upgrade.py prepare --root "C:/DreamType-installation" --from-version 4 --to-version 9
python outputs/local_voice/storage_upgrade.py prepare --root "C:/DreamType-installation" --from-version 9 --to-version 10
python outputs/local_voice/storage_upgrade.py prepare --root "C:/DreamType-installation" --from-version 10 --to-version 11
python outputs/local_voice/storage_upgrade.py prepare --root "C:/DreamType-installation" --from-version 11 --to-version 12
```

**逐行執行，每一步成功並核對輸出後才執行下一行。** 不要直接整段貼上讓 shell 在失敗後繼續。中途停止時，已成功提交的階段仍存在；再執行 `inspect`，從實際版本接續，不重跑先前階段。重複、跳級、未知或部分遷移的資料庫均拒絕。

每一階段呼叫既有正式遷移函式：重新確認離線、取得 maintenance lock 與資料庫寫入鎖、確認錄音／收件排空，先建立並解密還原驗證 `.dtbackup`，才以單一交易變更 schema。失敗不得宣稱整條升級鏈回滾；必須重新檢查版本及已產生的備份。輸出 `backup` 是該階段**升級前**的快照路徑。

升級不新增或刪除 `billing_mode` 標記，不改使用者額度，也不建立 OAuth／Google 付款憑證。已要求付款政策的資料庫依然要求相同政策；不能透過移除設定降級成免費模式。schema 12 準備完成後，仍須先驗證候選服務、登入及備份／刪除功能，才安排明確切換。真實 Google OAuth、Play Console、商店商品及真人驗收是另外的門檻。

## 回復到新目錄

保留升級前快照、獨立保管的 `backup-recovery.key` 及**同主機最新**刪除紀錄 `latest-deletions.dtledger`。不得用舊刪除紀錄讓已刪帳號重現，也不得覆寫目前資料庫。透過既有 `backup.restore(new_root, archive, recovery_key, deletion_ledger)` 還原到尚未啟動的新安裝目錄，核對實際 schema 後配對相容的程式與設定，再決定是否切換流量。還原會清除登入 session、錄音結果及短效驗證資料；使用者必須重新登入。

復原金鑰、Google／Cloudflare／Tunnel 設定及付款服務帳號憑證並非全部都在帳號快照內，請依 [備份復原文件](DELETION_RECOVERY.md)、[付款設定](BILLING_CONFIGURATION.md) 與 [Google 登入設定](GOOGLE_SIGNIN.md) 分別準備。工具不處理 DNS、流量切換、R2 上傳或服務啟動。

## 已驗證與未驗證

`test_storage_upgrade.py` 使用合成安裝，透過四個正式入口完成 4→9→10→11→12，逐份還原四個升級前快照及 schema 12 快照，驗證偏好與密碼登入保留、session/challenge 清除、最新刪除紀錄排除已刪密碼／Google 帳號，以及禁止覆寫還原目標。也驗證只讀預檢、待處理工作、運行中主機、維護鎖、錯誤／重複版本與缺失資料。

這是同機隔離演練，尚未對正式主機執行遷移，也不代表獨立電腦的災難復原、真實付款或 OAuth 已通過。
