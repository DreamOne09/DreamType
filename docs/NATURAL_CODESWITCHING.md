# 自然中英夾雜辨識：2026-09-28

新增真人自然對話的比較證據，補充既有台灣 Common Voice 朗讀短句。結果支持繼續評估 Breeze，**尚不足以更換正式預設模型或宣稱勝過 Typeless**。

## 固定素材與方法

[ASCEND](https://huggingface.co/datasets/CAiRE/ASCEND) test 的 373 段 mixed 音訊，依位置等距取 96 段；取樣與腳本已先提交 `1147548`，之後才執行兩個模型。音訊共 405.723 秒，每段 0.89–11.34 秒，兩名說話者。保留原音、不拼接、不用 TTS。這是香港收集的自然對話，**不是台灣代表性樣本，不是自然長口述，也不是獨立盲測**。

素材授權、逐字稿轉換、固定版本、SHA256 及重建方式見 [素材說明](../tests/quality/ascend96/README.md)。本頁引用逐字稿及本目錄 `evidence/ascend96` 中的資料／衍生逐字稿沿用 [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)，作者歸屬同素材說明。

同一台 i7-9700 / 16GB RAM / RTX 4060 Ti 8GB；一次只載入一個 ASR，卸載 Qwen 與 TranslateGemma。兩者 CUDA int8_float16、beam 1、VAD 350 ms、language zh、condition_on_previous_text false、同一正式提示詞、不把參考答案放入 prompt。各先暖機一次。正式服務設定仍是 Turbo。

## 結果

| 指標 | Turbo | Breeze |
|---|---:|---:|
| 字元錯誤率 CER | 24.08%（601/2496） | 14.66%（366/2496） |
| 本專案混合詞元錯誤率 MER | 23.69%（367/1549） | 17.30%（268/1549） |
| 逐字完全相同 | 14/96 | 25/96 |
| 空結果 | 0 | 1 |
| 純辨識時間中位數 | 0.219 秒 | 0.412 秒 |
| 純辨識時間 P95 | 1.249 秒 | 0.743 秒 |

逐段按 CER 比較：48 改善、26 退步、22 同錯誤數。Breeze 空結果那段的參考內容只有「uh呃」，仍納入計分。CER 包含語助詞及重複字；刪除口頭贅詞也可能扣分，不能直接換算成使用者體感或語意正確率。

CER：NFKC、英文小寫、臺→台，忽略標點／空白；參考答案先做與假設文字一致的 OpenCC s2tw 轉換。MER 為本專案定義：每個漢字、連續英文字母、連續數字各一個詞元，忽略其他字元，例如 `what's` 算 `what` 與 `s`；不是 ASCEND 官方論文分數，不能直接跨論文比較。它可避免很長的英文單字在 CER 中占太大比重。

P95 使用排序後 `floor((n-1)*.95)`。兩者少數尾端延遲分布不同，不把這次 P95 視為穩定優勢；時間不含排隊、格式整理、手機傳輸或多模型共載。

## 忠實輸入仍有缺口

- 第 24 段參考以 `from our department` 開頭。Turbo 改成「從我們的部份」，Breeze 保留英文。第 26 段亦發生英文被翻成中文。一般整理模式不能因此被誤認為有意啟用翻譯。
- 第 55 段包含 `can not wear`，Turbo 變成 `can now wear`，Breeze 變成 `can know where`。兩個模型都沒有可靠保留否定，不能只靠後處理保證原話語意。
- 第 94 段 Breeze 在句尾增加 `under the`；第 75 段刪掉重複片語，CER 反而比 Turbo 高。這兩種情況對使用者的影響不同，需要分別檢視。

[Turbo 逐筆](evidence/ascend96/turbo-report.json) · [Breeze 逐筆](evidence/ascend96/breeze-report.json) · [重算統計與變化案例](evidence/ascend96/summary.json) · [服務恢復紀錄](evidence/ascend96/host.json)。比較結束後，Tunnel 程序保留，維護排程恢復，正式 `/health` 驗證 ready、speech_profile turbo，辨識／整理／翻譯皆 ready。

## 下一個決策

Breeze 在台灣短句和此自然中英夾雜樣本都有較低整體錯誤率，但真實 30–60 秒台灣口述、否定／数字／專有名詞，以及 Pixel 9 實機仍缺驗證。先保留原文恢復及人工修改能力；不以 LLM 猜測修補辨識錯誤，也不自動改成較昂貴的雙模型辨識。

重跑：按素材說明準備音訊；在獨立或安全停機的 GPU 環境分別執行 `scripts/compare_gpu_asr.py --model turbo|breeze --corpus ascend96 --model-dir <固定模型目錄> --audio-dir <音訊目錄> --output <報告>`。以 `scripts/summarize_gpu_asr.py` 產生比較；摘要工具核對凍結 manifest、完整 96 筆、共同參數並重新計算錯誤，拒絕兩份報告同時被修改的參考答案。
