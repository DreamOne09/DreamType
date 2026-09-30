# 雲端辨識單段試測

`scripts/cloud_asr_probe.py` 可對相同的非私人測試 WAV 分別呼叫 Cloudflare 或 Groq，使用各自的 Whisper Large v3 Turbo。這是獨立試測工具，沒有接入手機／帳號的正式 provider，也沒有搬移資料庫或改動本機模型。

## 預設只檢查，不上傳

使用現有 Python 環境與 httpx。音訊限單聲道、16 kHz、PCM16 WAV，0.01 至 60 秒、檔案小於 2 MB；工具檢查實際 frame 資料，拒絕截斷檔案。需先準備已確認可以交給指定供應商的合成或非私人音訊。

```powershell
python scripts/cloud_asr_probe.py --provider groq --audio work/test-clip.wav
python scripts/cloud_asr_probe.py --provider cloudflare --account-id YOUR_ACCOUNT_ID --audio work/test-clip.wav
```

此時只有 `dry_run` 報告，`requests=0`，不讀憑證、不連網。報告包含音訊 SHA-256、時長、大小及模型；以同 SHA 的輸入比較兩家，避免不同音檔造成不公平比較。

## 明確授權後才上傳一次

在上述命令加上 `--upload`，才會以不回顯的 getpass 讀取該供應商的 API 憑證並送出一個請求。憑證不儲存，不接受命令列金鑰。Cloudflare 需要 Workers AI 權限，R2 權杖不能代用。請先確認帳戶方案和剩餘額度；本工具不能從一個成功回應判定該次免費。

`--include-transcript` 才會把回傳文字加入標準輸出，用於已審核的合成音訊品質檢視。預設不輸出文字，也不輸出原始檔名、API 錯誤內容或金鑰。保存結果請放私有 `work/`；人工審核後才將合成資料結果加入公開證據。

固定官方 HTTPS endpoint，拒絕轉址，不自動重試或切換供應商；最多等待 60 秒，回應限制 1 MB。429 回報 `quota_or_rate_limit`、401／403 回報 `authentication`，其他故障使用固定代碼。`requests=1` 表示嘗試次數，不是已計費次數；逾時不代表對方未處理，`actual_charge` 保持 null，實際用量需另查供應商帳單／控制台。

空字串回報 `empty_transcription`，不把它算成成功辨識；非空文字也不代表一定含真實語音，靜音幻覺仍需單獨驗收。此工具只測中文 ASR，不整理、不翻譯。`request_seconds` 是單次 HTTP 辨識往返，不包含手機上傳至 DreamType、排隊、排版及插入，不能當完整鍵盤延遲。

## 已有驗證及待辦

11 項離線 HTTP 傳輸替身及 CLI 測試通過，涵蓋兩家請求格式、錯誤、無重試／轉址、逾時、回應大小、壞音訊、缺省零上傳及輸出遮蔽。尚無真實 API 憑證或供應商測試結果，不能聲稱雲端接通或比本機更準。

格式依據（2026-09-30）：[Cloudflare 模型 schema](https://developers.cloudflare.com/workers-ai/models/whisper-large-v3-turbo/)、[Cloudflare REST](https://developers.cloudflare.com/workers-ai/get-started/rest-api/)、[Groq 語音 API](https://console.groq.com/docs/speech-to-text)。完整搬移驗收另見免費雲端方案；試測成功不等於家中主機可關機。
