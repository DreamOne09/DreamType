# 刪除帳號後還原舊備份

2026-09-22 後端補強，資料庫 schema 4。APK 不需更新。

刪除帳號與刪除紀錄寫入同一筆資料庫交易。紀錄只含隨機帳號 ID 與刪除時間，不含帳號名稱、密碼、提示詞或錄音。紀錄持續保留，因為旧備份可能長期存在；相同帳號名稱重新註冊會產生不同 ID。

還原工具必須取得同一主機最新的加密刪除紀錄。它會先移除舊備份中已刪帳號及其關聯資料，合併刪除紀錄、清除相關 audit 並 VACUUM，完成後才寫入新主機。缺少紀錄、解密失敗、主機不符或資料庫版本過新，均拒絕還原。不要降級執行 schema 3 的旧服務。

## 操作

搬機／還原前，在原主機匯出最新紀錄：

```powershell
.\work\venv\Scripts\python.exe .\outputs\local_voice\backup.py export-deletions
```

產生 `work/backups/latest-deletions.dtledger`。使用獨立保管的 `backup-recovery.key` 加密；不能把解密金鑰一起同步。

```powershell
.\work\venv\Scripts\python.exe .\outputs\local_voice\backup.py restore --archive "D:\Backups\example.dtbackup" --recovery-key "E:\Private\backup-recovery.key" --deletion-ledger "D:\Backups\latest-deletions.dtledger"
```

不指定 `--deletion-ledger` 時，工具從備份旁尋找 `latest-deletions.dtledger`，不會因為檔案不存在就略過核對。仍禁止覆蓋已有帳號資料庫。

建立備份會同時更新刪除紀錄；五分鐘維護工作另行更新它，不必等每日備份。有設定同步資料夾時會複製加密紀錄，狀態為 `last_deletion_export`／`last_deletion_copy`；這只代表本機匯出／複製，不代表雲端已收到。尚未設定雲端同步。

## 界線與剩餘工作

- 無法從一份舊檔案自行證明它是最新紀錄；操作者必須取得最新來源。不能拿舊紀錄當作完整刪除歷史。
- 主機在下一次五分鐘匯出前故障，最新刪除可能只在原資料庫；異機同步延遲亦可能丟失最新紀錄。外部可靠備援尚未完成。
- 升級前已刪除的帳號沒有可追溯紀錄。還原升級前備份仍需核對過往刪除要求，不能宣稱自動修復這段歷史。
- 原始舊備份沒有被改寫或刪除；本功能防止資料重新進入運作中的系統，不等於從所有歷史備份消除資料。備份保留期限與雲端刪除政策仍待完成。

驗證：43 項 Python 測試通過，含刪除後還原舊備份、同名重新註冊、錯誤密碼不留下刪除紀錄、紀錄缺失／竄改／主機不符拒絕，以及維護只複製加密備份和紀錄。

部署後已對家中主機建立加密快照，在隔離暫存目錄還原，確認資料庫完整、schema 4、已刪 ID 與使用中帳號無交集、登入 session 清空；檢查完成後移除暫存資料。Android Java HTTPS 登入、辨識、用量流程亦通過。此演練不代表異機／雲端救災已通過。
