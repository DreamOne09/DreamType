# R2 加密備份與復原（實作完成，尚未啟用真實雲端同步）

目前新增 `r2_sync.py`、`r2_config.py`、`r2_cli.py` 與維護排程接線。下方原始傳輸核心仍保留；自動同步改用以密文 SHA-256 命名的快照及刪除紀錄，避免每五分鐘重傳整份快照。這些檔案沒有刪除或保留期自動清理。

## 安裝與設定

主機虛擬環境另安裝 `outputs/local_voice/requirements-r2-lock.txt`。執行下列命令時，`python` 指主機專用虛擬環境；請在 repo 根目錄執行。

```powershell
python -m pip install -r outputs/local_voice/requirements-r2-lock.txt
python outputs/local_voice/r2_cli.py configure --account-id YOUR_ACCOUNT_ID --bucket dreamtype-backups
python outputs/local_voice/r2_cli.py enable
```

`configure` 透過不回顯的終端提示輸入 Access Key ID 與 Secret Access Key，不接受命令列上的明文密鑰。Windows DPAPI 將憑證綁定目前使用者，保存在 `work/r2-credentials.dpapi`；不進 Git、不上傳。設定完成仍是停用狀態；`enable` 成功上傳、下載驗證與還原檢查之後才開啟自動同步。既有設定不自動覆蓋。SDK endpoint 只允許由合法 Cloudflare 帳戶 ID 組成的官方 HTTPS 網址。

## 每五分鐘的維護流程

維護工作保留每日本機快照，匯出新的刪除紀錄，再同步到 R2。當快照未改變時，下載核對既有密文，僅新增當次刪除紀錄。兩者通過還原驗證後，才以條件式更新發布 AES-GCM 加密的 `current.dtindex`。索引包含配對的雜湊與時間，使用 ETag compare-and-swap，拒絕較舊快照、較舊刪除紀錄及其他主機覆蓋。

維護排程與手動同步共用作業系統鎖；工作中斷會由作業系統釋放，不會因上次留下鎖檔而永久停住。雲端失敗不影響已完成的本機備份，也不會更新雲端成功時間。管理介面將 R2 下載還原驗證與「另一台電腦完整復原」分開呈現。

啟用、停用與同步也使用同一把鎖；已有工作進行時會回報 `LockBusy`，請等該工作完成後重試，不能將忙碌視為停用成功。手動同步成功僅清除 R2 同步錯誤，不清除其他維護錯誤，也不更新未實際檢查的模型、通道或磁碟健康時間。

## 驗證、還原與停用

```powershell
python outputs/local_voice/r2_cli.py verify
python outputs/local_voice/r2_cli.py restore --destination C:\DreamType-Restore --recovery-key X:\backup-recovery.key
python outputs/local_voice/r2_cli.py disable
```

下載大小與雜湊、解密、資料庫、刪除紀錄及索引時間全部核對。`verify` 不安裝明文資料；`restore` 只接受不存在或空的目的目錄，不覆蓋目前主機。刪除紀錄超過 15 分鐘會拒絕，真正災難情境需人工核對後明確加上 `--accept-stale-ledger`；這無法證明來源端在最後同步後沒有新的帳號刪除。復原金鑰必須另存，DPAPI 憑證不能直接搬到另一個 Windows 帳戶，異機復原須另行取得合法 R2 存取權限。

尚未啟用真實憑證或上傳。以下保留原始核心說明，測試證據仍只有本機傳輸替身與 Windows 合成憑證往返，不能稱為已完成雲端備援。

`outputs/local_voice/r2_backup.py` 提供 `upload_verified_pair`，接收限定貯體的 S3 client、一份 `.dtbackup`、對應最新 `.dtledger` 與只留本機的復原金鑰路徑。依 [Cloudflare 官方 boto3 介面](https://developers.cloudflare.com/r2/examples/aws/boto3/) 設定 R2 endpoint、region `auto` 與貯體專用憑證；此模組不自動取得憑證、不修改帳戶權限。

流程：

1. 限定加密副檔名、DTB1／DTD1 標記與大小，冻结密文副本。
2. 上傳前以既有還原驗證確認金鑰、資料庫、主機與刪除紀錄相符。密文標記本身不當作加密正確的證據。
3. 每次使用獨立隨機物件路徑；失敗不覆蓋先前成功備份。
4. 上傳後重新 GET 完整密文，比對長度與 SHA-256，不能只信任 ETag 或 metadata。
5. 再用下載的檔案跑記憶體還原驗證，全部成功才回傳 verified。

復原金鑰永不上傳；暫存目錄只有密文。未包含自動刪除遠端檔案，失敗可能留下密文物件，需要另訂保留與清理政策。

6 項離線傳輸替身測試驗證成功配對、不上傳金鑰、下載損毀拒絕、部分失敗保留舊副本、壞密文／舊刪除紀錄／明文 ZIP 在連線前拒絕。這不代表已成功連線 R2。

## 尚缺的步驟

專用權杖目前待使用者確認建立，沒有把任何真實備份送到雲端。程式已接入排程，但設定缺省為停用。仍須完成真實 R2 上下載與異機還原驗收、金鑰離機保管、物件保留政策。R2 Bucket Lock 若啟用，應限定快照／歷史刪除紀錄前綴，不能鎖定需要更新的 `current.dtindex`。

一份快照當時的刪除紀錄無法涵蓋之後刪除的帳號。還原舊快照時仍必須取得最新刪除紀錄；此傳輸核心不聲稱任一歷史配對就是最新紀錄，不應直接當成完整災難復原方案。
