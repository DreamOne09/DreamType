# 主機 ASR 設定與 Breeze 完整 API 測試

主機可在啟動時用 `DREAMTYPE_ASR_MODEL` 選擇 `turbo` 或 `breeze`。未設定時固定使用 Turbo；未知名稱、網址或路徑會明確失敗，不會猜測下載模型，也不會默默改用其他模型。

| 值 | 相對於 work/ 的本機目錄 | 狀態 |
|---|---|---|
| turbo | models/whisper-turbo | 現有預設 |
| breeze | models/breeze-asr-25/int8_float16 | 候選模型，尚未正式切換 |

`/health` 的 `speech_profile` 會顯示目前設定，配合 `speech_ready`／`status` 確認載入完成。設定在服務啟動時讀取；只改環境變數但未重啟，不會影響已執行的程序。手機不能藉由請求 header 指定本機模型路徑。現有安裝腳本仍下載 Turbo；Breeze 必須先準備已核對的候選檔案，不能在停機期間等自動下載。

## 2026-09-28 三輪混合負載

明確驗證 gateway 為 Breeze 後，以三個隔離帳號送入 5 秒中文整理、30 秒日文翻譯、60 秒英文翻譯，每輪交換提交順序，三輪共 9 筆。帳號 API 與 SQLite 在暫時目錄，實際 ASR／Qwen／TranslateGemma 由家中 gateway 處理；沒有建立真實用戶帳號。Qwen 已使用省 RAM 的 `--load-mode none`。

- 9/9 完成，0 筆 warning；18 次跨帳號讀取均拒絕。
- 每筆重複送兩次回執，三個帳號最終用量分別是 15／90／180 秒，沒有重複計費或剩餘預留用量。
- 5 秒短整理，第一順位共 0.956／2.034 秒；排在 60 秒翻譯後為 9.183 秒，等待 provider 前已耗時 8.324 秒。
- 30 秒日文翻譯共 6.036–14.831 秒，60 秒英文翻譯共 8.559–17.889 秒，均包含本機排隊。
- 90 次資源取樣：GPU 最高 7,545 MiB，系統可用 RAM 最低 858,521,600 bytes，約 819 MiB。完整流程的 RAM 餘裕比孤立短測低，仍需長時間驗證。

[逐筆結果](evidence/breeze-api/mixed.json) · [profile、資源與恢復紀錄](evidence/breeze-api/host.json)。結束後驗證 profile 已恢復 Turbo，排程及 Tunnel 健康；正式手機服務沒有永久切換候選模型。

音訊由凍結的公開短片段重複拼接／裁切，**不是自然長口述品質測試**。這是封閉批次，上一輪完成才送下一輪，不是無間斷到達或飽和容量測試。傳輸為隔離 ASGI 帳號層至 localhost 推論，不含 Pixel 9、外部行動網路或 Surfshark。計時與前次 Turbo 測試不是嚴格同時受控 A/B，不應直接宣稱整體速度更好。

另已完成 [96 段自然中英夾雜比較](NATURAL_CODESWITCHING.md)：Breeze CER 較低，但有 26 段退步，且只有兩名香港語境說話者。下一步仍需處理長翻譯擋住短整理的等待，以及自然長口述／台灣中英混說品質；未達成前，不能因為這次 9 筆完成就對外承諾服務容量或更換預設模型。
