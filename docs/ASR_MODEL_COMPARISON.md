# 台灣華語 ASR 模型隔離比較

## 為什麼做這個比較

目前公開真人短句基準仍有地名、同音字與漏辨；增加文字整理規則不能代替改善語音辨識。[MediaTek Breeze ASR 25](https://huggingface.co/MediaTek-Research/Breeze-ASR-25) 是基於 Whisper large-v2、針對台灣華語和中英夾雜優化的模型，模型卡標示 Apache-2.0。但發布者的成績不等於 DreamType 的實際改善。

2026-09-26 檢查家用主機，可用記憶體當時約 1.4 GiB，可用磁碟約 5.3 GiB；不額外在運作中的主機載入另一個大型模型。比較改在手動觸發的 GitHub Actions 隔離 CPU runner 進行，沒有更換正式模型、沒有傳送私人錄音或服務金鑰。

## 可重現設定

- 工作流程：`Public Taiwan ASR comparison`，只可手動觸發，不在每次 push 自動下載模型。
- 腳本：`scripts/compare_public_asr.py`。
- Turbo：`mobiuslabsgmbh/faster-whisper-large-v3-turbo`，revision `0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf`。
- Breeze：使用 [轉換者發布的 CTranslate2 版本](https://huggingface.co/shdennlin/breeze-asr-25-ct2)，revision `70660216b01a6f6b7b8c5690767a4763df61755f`，`int8_float16` 子目錄。這是第三方量化轉換，不冒充 MediaTek 原始權重檔。
- 兩者使用相同 CPU int8 設定、最多四執行緒、beam 1、350 ms VAD 靜音門檻，不沿用前段文字。台灣提示以各自 tokenizer 的同一預算產生，報告保留實際提示，參考答案不進提示。
- 資料是既有 CC0 test split 索引 0–35，36 段公開音檔。下載時核對每段參考文字及 SHA-256；內容變更就停止，不悄悄換資料。只保存公開參考／辨識文字，音檔、模型與說話者資料不進 Git 或 Actions artifact。
- CER 與既有基準相同：NFKC、小寫、忽略標點與空白、臺→台。這不是完整語意分數。

已在本機完成 36 段下載來源與雜湊核對；首次模型運算的實際結果仍須以 Actions 報告為準。工作流程每段完成就保存報告，只有全部完成才有 `complete: true`，失敗或超時不算通過。

## 決策界線

這批資料已用於先前診斷，現在是比較／回歸集，不能再稱獨立盲測。它只是連續短句便利抽樣，沒有長口述、中英夾雜的代表性覆盖，也沒有 Typeless 同音檔對照。CPU runner 的秒數不能當成 Pixel 9 或家中 GPU 的實際延遲。只有品質確實有改善後，才值得評估家用 GPU 記憶體、速度與中文／其他語言路由；本次不自動部署候選模型。
