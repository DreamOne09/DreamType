# 0.7.0：資料保護與維運補強

2026-09-22 補充：後端已升級 schema 4，加入加密刪除紀錄與舊備份還原核對；以下 0.7.0 歷史敘述由 [刪除與還原說明](DELETION_RECOVERY.md) 更新。還原現在必須攜帶最新 `latest-deletions.dtledger`。雲端同步、升級前刪除歷史與備份保留政策仍未完成。

目前仍是封閉試用，不是公開付費 production。以下是實作與驗證，不用完成百分比代替證據。

## 資料放在哪裡

| 資料 | 保存位置與期限 |
|---|---|
| 帳號、密碼雜湊、提示詞、詞庫 | 主機 SQLite；密碼不保存原文，提示詞與詞庫目前未做欄位加密 |
| 登入 | 主機保存 token 雜湊，手機保存加密 token；最長七天 |
| 工作與用量 | SQLite；啟動時清理超過 93 天工作 |
| 錄音 | 主機加密暫存待處理錄音以恢復佇列，成功／失敗清除，超過一小時於重啟清理；Android 帳號模式保留一份加密重試錄音，最長一小時，詳見 0.6.0 文件 |
| 辨識結果 | 主機 SQLite AES-256-GCM 加密，15 分鐘；約每 30 秒清理過期資料；主機停機時待下次啟動清理 |
| 管理操作 | 主機保存操作名稱、帳號 ID 與時間，最多約 90 天；不記錄密碼、錄音、文字或重設碼 |
| 備份 | 本機加密 `.dtbackup`，不含錄音、辨識結果、登入 session、重設碼；尚未完成雲端上傳 |

加密金鑰與資料目前在同一主機，加密不能防止已控制主機的攻擊者。Cloudflare 代理仍會處理傳輸內容；這不是手機到主機的端對端加密。

## 六項進度

| 項目 | 這版已完成 | 尚缺的驗收或條件 |
|---|---|---|
| Pixel 9 實測 | APK 建置與原簽章驗證、Java HTTPS 端到端測試 | 使用者目前不方便接 USB；鍵盤、Keystore、行動網路、Surfshark、背景切換仍未驗收 |
| 結果可靠交付 | 加密結果與扣額度同一 SQLite 交易；重啟仍可取回；0.7.0 收件確認、未確認到期釋放額度；同 ID 不重扣 | 待處理錄音與設定加密保存，重啟恢復佇列；超過一小時或資料不可讀時退款，需手機手動重試 |
| 主機維運 | Windows 每五分鐘檢查、兩次健康失敗後啟動恢復、15 分鐘重啟間隔、每日加密備份 | 只在該 Windows 使用者登入期間運作，不能防斷電／休眠；Quick Tunnel 重啟會換網址，尚無固定入口 |
| 監控與容量 | 管理頁顯示 worker、佇列、24 小時失敗數、備份時間；維護狀態檔 | 尚無外部離線告警、長時間真實負載／斷電演練；不保證可服務多少付費使用者 |
| 帳號與安全 | 管理者核發 15 分鐘一次性重設碼、雜湊保存、重設撤銷全部 session；操作紀錄；schema 版本與新版本拒絕降級 | 人工確認身分；未接信箱／第三方登入；未做獨立安全審查；備份刪除政策仍待完善 |
| Play 與付款 | 發布 APK，保留上架需求與此差距清單；維持免費邀請試用 | 沒有 Play Console 帳號；尚未實作正式 Billing Library、伺服器購買驗證／RTDN／退款同步、AAB 與正式商店揭露，不能收費 |

Google 要求在安全後端驗證購買與確認訂閱，再授予權益；不能用手機回傳「已付款」作依據。見 [官方 Billing 安全文件](https://developer.android.com/google/play/billing/security)。[Cloudflare 官方](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/) 明確指出 Quick Tunnel 用於測試，沒有 uptime SLA。

## 收件確認的界線

0.7.0 帳號模式上傳帶 `X-DreamType-Receipt: 1`。手機解析結果後 POST `/v2/dictations/{id}/receipt`，成功才交給鍵盤。未確認結果尚存時不允許另開新工作，避免利用未確認退款無限使用。15 分鐘內仍可重取；未確認過期轉失敗並釋放額度。已確認代表手機 API 收到文字，不代表已插入其他 App；已確認工作過期後仍扣額度。

0.6.0 舊版沒有回報收件能力，維持舊扣額度行為，但加密結果也能跨重啟保存。建議更新手機。備份恢復不含結果，未確認工作釋放額度。錄音／結果不是永久歷史庫。

## 密碼恢復

管理者在 `/admin` 對指定帳號按「重設密碼」，確認身分後私下提供代碼。使用者開 `/account` → 忘記密碼，輸入代碼與新密碼。代碼僅顯示於本次管理頁；不要貼公開 issue。成功後所有舊登入失效。API 登入／重設合計限制 20 次／分鐘，重啟會重設限流記憶體；不取代完整防濫用服務。

## 備份與雲端

```powershell
.\work\venv\Scripts\python.exe .\outputs\local_voice\backup.py create
```

輸出 `work/backups/*.dtbackup`；解密金鑰為 `work/backup-recovery.key`。金鑰必須另存於安全位置，不能只留在故障硬碟，也不要與備份一同上傳。此版本不自動刪除歷史备份；舊 `.zip` 備份依然未加密，請私下管理，不能認為升級會自動加密舊檔。

選定雲端硬碟、完成其官方同步程式登入後，在私有 `work/backup-config.json` 指定已存在的專用同步資料夾：

```json
{"sync_directory":"D:\\YourCloudSync\\DreamTypeBackups"}
```

維護程式只複製加密備份，不複製金鑰。`last_backup_copy` 只代表已複製到本機同步資料夾，**不是雲端上傳完成的證據**；必須在雲端網頁確認並下載還原一次。沒有設定此檔時只做本機備份。雲端帳號與資料夾仍待使用者指定。

新主機先安裝依賴，不啟動服務，使用空的 `work/beta`：

```powershell
.\work\venv\Scripts\python.exe .\outputs\local_voice\backup.py restore --archive "D:\\Backups\\example.dtbackup" --recovery-key "E:\\Private\\backup-recovery.key"
```

禁止覆蓋既有資料庫；還原撤銷登入與未完成工作。簽章檔與模型不在備份中，須另行保管。已刪除帳號可能仍存在舊備份，還原前必須核對應刪除帳號；目前還沒有跨備份刪除追蹤系統。

## 自動維護

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-maintenance.ps1
.\work\venv\Scripts\python.exe .\outputs\local_voice\readiness.py
```

安裝使用者層級排程 `DreamType Maintenance`，無視窗執行，不會修改 Windows 休眠或其他應用服務。若要刻意停止服務，先停用此排程，否則它會嘗試恢復。狀態在 `work/maintenance-status.json`。通道重新啟動後，管理頁顯示新網址；手機需更新。

## 本次證據

- 27 項 Python 測試通過：跨重啟結果、交易回滾、收件確認隔離／冪等／退款、密碼恢復、備份竄改拒絕、恢復不覆蓋、維護重啟節流等。
- APK 0.7.0 / versionCode 8，同包名與簽章，v2/v3 簽章驗證通過。
- 真實 Cloudflare HTTPS + Android Java 連線類別：登入、偏好、辨識、用量、重取／重送不重扣通過；不是 Pixel 9 實機測試。
- 管理頁與手機尺寸帳號頁瀏覽器測試通過；沒有 JavaScript 錯誤。
- 對目前主機做加密快照，還原至獨立空目錄，帳號與偏好一致，舊 session 撤銷，原主機資料未覆蓋。
- 新增 GitHub Actions 後端測試流程；遠端結果需以 Actions 實際執行為準。
