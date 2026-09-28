# 家用 GPU 語音模型比較：2026-09-28

結論：Breeze 值得進入整套服務共存與較自然口述的下一輪測試，尚未替換正式模型。這輪只能證明固定 96 段台灣短句的結果，不能證明整體優於 Typeless。

後續已完成一次 [三模型共存短測試](GPU_COLOAD.md)：請求可完成，但系統可用 RAM 曾只剩約 25.5 MiB，因此仍不切換正式模型。以下保留原本單模型比較的範圍與數據。

在同一台 RTX 4060 Ti 8 GiB／i7-9700 電腦逐一載入 Turbo 與 Breeze，使用既有凍結 extended96 語料（index 36–131、670 個正規化參考字元）。每段 1.584–8.064 秒。兩個權重 SHA-256 及所有音檔雜湊已核對。CUDA int8_float16、beam 1、VAD 350 ms、相同台灣地名提示，不提供參考答案、不呼叫 LLM；每個模型先用第一段暖機一次。

| 指標 | Turbo | Breeze |
|---|---:|---:|
| 字元錯誤數 | 106 | 40 |
| 字元錯誤率 | 15.82% | 5.97% |
| 完全正確短句 | 60 / 96 | 73 / 96 |
| 空輸出 | 0 | 0 |
| 辨識中位時間 | 0.197 秒 | 0.344 秒 |
| 約第 95 百分位 | 0.219 秒 | 0.432 秒 |
| 96 段計時合計 | 22.79 秒 | 33.54 秒 |

Breeze 有 23 段字元錯誤減少、8 段增加、65 段相同。仍把「高榮新榮交流道」辨成「高榮興龍交流道」、「何者正確」辨成「合作正確」，不能把專名準確率視為已解決。

Turbo 的兩個明顯異常輸出（index 39、42）貢獻了總計 66 個錯誤改善中的 45 個。主要表格保留所有案例；**事後敏感度檢查**若排除這兩段，Turbo 為 60/657＝9.13%，Breeze 為 39/657＝5.94%。不得將這個事後子集當獨立盲測。GPU 與先前 CPU 結果不完全相同，不能沿用 CPU CER 當 GPU 證據。

測試前確認無 queued/running 帳號工作，暫停 DreamType 維護排程、卸載三個正式模型程序，保留原 Tunnel 程序；兩個 benchmark 子程序各設 180 秒上限，另設獨立 watchdog。結束後恢復排程及 Turbo／Qwen／TranslateGemma，健康檢查與 Tunnel 通過。準備至恢復約 96 秒，這不是零停機操作。測試期間沒有 Qwen／TranslateGemma 共存，因此尚不能證明 Breeze 與完整服務一起載入的記憶體或延遲。

本輪不包含手機上傳、外部網路、排隊、LLM 整理、自然長口述或中英混說；也未測完整服務共存、峰值 VRAM 或 Pixel 9。模型速度是已暖機的單模型電腦辨識時間，不能當作手機端到端承諾。

## 證據與重跑

[Turbo](evidence/asr-gpu96/turbo-report.json) · [Breeze](evidence/asr-gpu96/breeze-report.json) · [逐句比較](evidence/asr-gpu96/summary.json) · [程序及恢復紀錄](evidence/asr-gpu96/host.json)。報告只有公開 CC0 參考句及辨識結果，沒有私人錄音。

`scripts/compare_gpu_asr.py` 需明確指定 `--model turbo|breeze --model-dir <權重目錄> --audio-dir <凍結音檔目錄> --corpus extended96 --output <報告>`。先加 `--verify-only` 核對檔案；此模式不載入 GPU。正式計時會載入 GPU，**呼叫者必須先安排服務與排程恢復**，腳本本身不停止任何服務。Windows NVIDIA DLL 從執行腳本的 Python 環境尋找。沒有模型或音檔時直接失敗，不在服務停機期間下載。

用 `scripts/summarize_gpu_asr.py --before <Turbo 報告> --after <Breeze 報告> --output <摘要> --hardware <實際硬體>` 重算 CER；會拒絕未完成、語料不同、提示不同或暖機案例不同的比較。
