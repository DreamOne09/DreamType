# 可終止的錄音解碼程序

## 問題與修正

0.9.14 的背景工作名額會在請求取消後繼續計入，但 Python thread 無法安全強制結束；若 native codec 卡死，名額可能一直不釋放。另外錄音會先檢查秒數、之後再轉成 Whisper 的 PCM，兩處都需要處理。

目前正式入口的兩處解碼都改由固定 `audio_worker.py` 子程序執行：

- `/v2/dictations` 以獨立程序計算實際音訊秒數，仍限 2 MB／120 秒。
- 私有 `/v1/audio/transcriptions` 以獨立程序轉為 16 kHz、mono、s16 PCM，主程序只把數值轉成原有 float32 輸入。仍限 25 MB／360 秒；PCM 累積超過上限立即拒絕。
- 每個子程序有 12 秒計時終止；父端既有 DecoderBudget 仍在 15 秒外層等待內限制工作數，各階段最多 2 個執行及 2 個短暫等待。取消請求不會提前釋放尚未結束的子程序名額。
- Windows 的 `communicate(input=...)` 可能在寫入 stdin 時阻塞，不能只依賴其一般 timeout。因此使用獨立 Timer 結束同一個 Popen 子程序，並 wait 確認結束後才釋放。
- Windows 使用 Job Object 的 KILL_ON_JOB_CLOSE；Linux worker 使用 parent-death signal 並核對父 PID。父服務突然結束時不留下解碼子程序。Windows 無法設定 job ownership 就拒絕啟動，不退回無管理模式。

音訊透過 stdin／stdout pipe 傳遞，不新增音訊暫存檔，不在命令列放錄音或金鑰。worker 以 `-I` 執行固定程式，請求不能選程式、檔案路徑或參數。PyAV 只允許 pipe protocol，不跟隨播放清單中的 file/http/tcp URL；設定依據見 [FFmpeg protocol_whitelist 文件](https://ffmpeg.org/ffmpeg-protocols.html#Protocol-Options)。

## 驗證

- Windows 真實子程序測試：阻塞於 stdin 前、異常退出、逾時後下一段恢復、取消仍保留名額、父程序強制結束後子程序退出、異常回傳拒絕，以及播放清單不連到隔離 HTTP 測試端點。
- 原始 120 秒及多一個 sample 的計費邊界維持一致；6 分鐘 PCM 上限拒絕過長輸入。12 項子程序／秒數測試通過，既有 9 項接收限制測試也通過。
- [新舊 PCM 比較](evidence/decoder-isolation/pcm-compatibility.json)：以固定 faster-whisper 1.2.1 為參考，四組合成 3 秒音訊（16 kHz mono WAV、48 kHz stereo WAV／FLAC／AAC），取樣數與每個 float32 值完全一致。單次獨立轉換約 0.17–0.21 秒；這不是手機端到端延遲或辨識品質證明。重跑工具為 `scripts/check_pcm_compatibility.py --output work/pcm-compatibility.json`。

Android APK 保持 0.9.14，不需為此更換手機版本；主機更新後 `/health` 的 `audio_decoding` 顯示 `isolated-process`。遠端 CI、整合及部署結果另以實際紀錄為準。

## 仍有的界線

這是程序生命週期隔離，不是低權限安全沙箱或 codec CVE 修補；子程序仍以相同使用者執行。輸入／輸出有大小限制，但未加入每程序 OS 記憶體上限。OS 無法終止程序等異常不在一般逾時測試範圍內。Whisper／LLM 推論本身的卡住問題、全站連線防濫用、Pixel 9 與公開付費上線驗收仍未完成。
