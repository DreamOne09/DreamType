# 備份建立後的本機還原驗證

2026-09-26 起，`backup.py create` 寫好加密備份並匯出刪除紀錄後，會使用正式 `restore` 流程還原到 `work/restore-check-*` 隔離暫存目錄。解密、快照格式、SQLite 完整性、外鍵、資料庫版本與刪除紀錄核對均沿用真正搬機時的程式；另外檢查沒有登入 session、錄音、結果、重設碼、回執或仍在執行的工作，且已刪帳號未復活。驗證失敗時不回報建立成功，維護程式不複製該備份到同步資料夾。

這不會覆蓋正式資料庫或撤銷目前登入。正常完成或 Python 例外時，暫存資料庫與金鑰會清除；程序遭強制終止或斷電時，暫存目錄仍可能留下，不能把它當成加密備份公開分享。整個 `work` 仍需限主機擁有者存取。未新增自動刪除歷史備份的政策。

新檔案先以加密 `.verifying` 暫存檔寫入，驗證成功後才改名發布成 `.dtbackup`。一般驗證失敗會清除暫存檔，不留下看似成功的新備份；強制終止留下的 `.verifying` 仍不可當作驗證通過。

## 使用

每日維護自動使用此流程。需要立即建立並記錄新驗證狀態時：

```powershell
.\work\venv\Scripts\python.exe .\outputs\local_voice\maintenance.py --backup-now
```

這仍會執行既有健康檢查及維護，不只是備份命令。若只想檢查一份現有檔案，不更新正式主機或維護狀態：

```powershell
.\work\venv\Scripts\python.exe .\outputs\local_voice\backup.py verify --archive "D:\Backups\example.dtbackup" --recovery-key "E:\Private\backup-recovery.key" --deletion-ledger "D:\Backups\latest-deletions.dtledger"
```

金鑰必須分開保管；還原仍需同主機最新刪除紀錄。工具只能拒絕已知太舊的紀錄，不能憑一份檔案判斷它包含所有後續刪除。

管理介面新增「備份還原驗證」。它要求最近 36 小時內成功，且 `backup_verified_file` 必須對應目前 `backup_file`；前一份的成功紀錄不能替新備份背書。首次升級未建立新備份前，顯示待確認是正常的。

## 證據與界線

22 項備份／維護／狀態／持久化測試通過，包括真正呼叫 restore、清除暫存、損壞備份拒絕、失敗不複製、正式登入與資料庫不變，以及舊驗證不能套用到新檔案。另已對目前主機資料建立加密備份並完成兩次本機隔離還原，[無帳號內容的結果](evidence/backup-verification/local-restore-check.json)已保存。

這只能證明當次本機可解密與還原，不能證明資料來源本來就完整、異機依賴可用、雲端已收到、硬碟故障後可恢復，或復原金鑰已獨立保管。離機備份、雲端下載後還原、歷史備份保留與故障中斷演練仍是上線缺口。
