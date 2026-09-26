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

工作流程每段完成就保存報告，只有全部完成才有 `complete: true`，失敗或超時不算通過。

## 首次完成結果（2026-09-26）

[Actions 36212997788](https://github.com/DreamOne09/DreamType/actions/runs/36212997788) 的兩個模型均完成全部 36 段；來源提交為 `575f05fb30d6e832000e0b3bc74ee347a751c5da`。完整公開輸出保存於 [Turbo 報告](evidence/asr-model-comparison/turbo-report.json)、[Breeze 報告](evidence/asr-model-comparison/breeze-report.json)，不依賴七天後會過期的 Actions artifact。

| 指標 | Turbo | Breeze |
|---|---:|---:|
| 參考字元 | 247 | 247 |
| 字元錯誤數 | 30 | 27 |
| CER | 12.15% | 10.93% |
| 正規化後完全相符 | 18 / 36 | 23 / 36 |
| 空白辨識 | 1 / 36 | 1 / 36 |
| 單段 CPU 中位數 | 9.513 秒 | 3.725 秒 |
| 全部辨識 CPU 耗時 | 333.844 秒 | 131.800 秒 |

逐段比較有 9 段錯誤數下降、5 段上升、22 段相同。Breeze 正確辨識「臺灣海峽」「文山內湖線」「老坑交流道」，但「常常拿著這份文件」變成「整天拿著這份文件」，「觀音區棒壘球場」變成「歡迎去幫你修長」。兩者對「旗六公路」皆輸出空白。錯誤數相同也不代表意思相同，例如「而且各站都停」在 Breeze 多出「了」。

**決策：保留現有 Turbo，不自動部署 Breeze。** 少三個錯字不足以證明整體更好，新增或改變意思的錯誤仍可能造成實際損失。下一輪應先固定未用於調整的新錄音集，增加長口述、中英夾雜、地名與含否定／數字的內容，再看整體與各類退步，不以這 36 段反覆調參後的高分作為上線依據。

兩個工作跑在不同 GitHub CPU runner，硬體與排程未控制；表中的秒數只記錄這次運算，不能證明 Breeze 在家中 GPU 或手機上比較快。此測試未包含網路、排隊、文字整理與翻譯。

[比較摘要](evidence/asr-model-comparison/summary.json) 由下列命令重算；腳本會核對完整 36 段、逐段參考／雜湊／時長與設定，並重新計算錯誤數，而非信任報告的總計欄位：

```powershell
python scripts/summarize_asr_comparison.py --before docs/evidence/asr-model-comparison/turbo-report.json --after docs/evidence/asr-model-comparison/breeze-report.json --output work/asr-summary.json
```

## 決策界線

這批資料已用於先前診斷，現在是比較／回歸集，不能再稱獨立盲測。它只是連續短句便利抽樣，沒有長口述、中英夾雜的代表性覆蓋，也沒有 Typeless 同音檔對照。CPU runner 的秒數不能當成 Pixel 9 或家中 GPU 的實際延遲。只有品質確實有改善後，才值得評估家用 GPU 記憶體、速度與中文／其他語言路由；本次不自動部署候選模型。


## 擴充比較集：先固定，再推論

新增 `extended96`：同一 CC0 test split 的固定連續索引 36–131，共 96 段、384.672 秒，每段 1.584～8.064 秒。以 `scripts/prepare_extended_asr.py` 在任何本輪模型推論前固定參考文字與 SHA-256；不依模型結果挑選或排除案例，不保存說話者、人口資料或帶簽章的音檔 URL。錄音只放在被 Git 忽略的 work 目錄。與既有 36 段無相同錄音雜湊或參考句。

這不是代表性隨機抽樣，仍是同資料集的短句；也不知道模型訓練是否包含這些公開資料，因此不稱獨立盲測。沒有透過這批新句子改寫提示或建立地名替換規則。固定 manifest 為 `tests/quality/public-taiwan-speech-extended.json`。完成 96 段來源、參考與錄音雜湊的二次核對；後續完整模型結果見下節。

手動工作流程新增 corpus 選項，預設保留 `regression36`；選 `extended96` 會讓兩個隔離 runner 使用完全相同的新 manifest，模型 revision 與辨識參數保持原樣。`summarize_asr_comparison.py` 分別要求完整的 36 或 96 個預定索引，拒絕混用語料或缺段的報告。舊報告沒有 corpus 欄位時，僅按原有 36 段解讀。

本機只準備錄音，不下載或載入候選模型：

```powershell
python scripts/compare_public_asr.py --model turbo --corpus extended96 --prepare-only --output work/unused.json
```


## 擴充 96 段完成結果

[工作 36215097067](https://github.com/DreamOne09/DreamType/actions/runs/36215097067)，來源 `6f2590818d63a1729a74a9cee9ef12abf1bddd9c`，兩個模型均完成固定的 96 段。摘要重算核對相同設定、參考、錄音雜湊與時長：[Turbo](evidence/asr-extended96/turbo-report.json)、[Breeze](evidence/asr-extended96/breeze-report.json)、[比較摘要](evidence/asr-extended96/summary.json)。

| 指標 | Turbo | Breeze |
|---|---:|---:|
| 參考字元 | 670 | 670 |
| 錯誤字元 | 98 | 40 |
| CER | 14.63% | 5.97% |
| 正規化後完全相符 | 61 / 96 | 73 / 96 |
| 空白辨識 | 0 | 0 |
| CPU 單段中位數 | 5.286 秒 | 11.016 秒 |
| CPU 辨識總耗時 | 529.729 秒 | 1060.166 秒 |

Breeze 有 21 段改善、8 段退步、67 段錯誤數相同。「中壢轉接道交流道」「板橋地政事務所」「遠東巨城購物中心」改善，但「高榮新榮交流道」變成「高榮興龍交流道」，「何者正確」變成「合作正確」，仍會改錯地名與意思。

整體差距受兩個嚴重誤辨影響很大：索引 39 的「申報網站」在 Turbo 變成拉丁字母，索引 42 的「對於東海及南海問題」變成不相關英文；兩案合計貢獻 40 個改善字元，占總改善 58 個中的大部分。**正式結果不刪除這兩案**。僅作事後敏感度說明，去除兩案後其餘 94 段分別為 57/657（8.68%）與 39/657（5.94%）；這不是預先設定的評分，也不能當成新的盲測結果。

**決策：Breeze 值得進入家用 GPU 的隔離候選測試，尚不替換正式 Turbo。** 先驗證 CUDA 記憶體、真實單段延遲及現有整理／翻譯並行資源，再擴充自然長口述、中英夾雜與不同口音。兩次 CPU runner 比較的速度排序相反，不能拿其中一次作為使用者手機速度預測。這輪也不能證明整體超過 Typeless。
