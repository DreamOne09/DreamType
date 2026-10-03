# 中英夾雜的常用詞與自動語言診斷

2026-10-03 在目前正式 Turbo 服務呼叫 local-raw，比較 source_language=zh-TW 與 auto，各四段、三種詞庫（無、相關、無關），共 24 次。使用先前已檢視的 ASCEND 第 2、24、26、55 段，相關詞從參考文字挑選，因此是針對已知問題的診斷，不是準確率基準、盲測或台灣代表性樣本。保留當前 hotwords、beam 1、VAD 350ms、condition_on_previous_text=False，沒有格式整理模型參與。

素材雜湊、版本、作者與授權见 [ASCEND 素材說明](../tests/quality/ascend96/README.md)。本頁及 evidence/mixed-vocabulary 的逐字稿與衍生文字沿用 CC BY-SA 4.0；音訊未加入 Git。每段使用既有 manifest 的 SHA-256 核對後送出。

## 觀察與決策

- Python 的中文夾英句，在 zh-TW 加詞庫後保留指定大寫。這只是拼寫差異。
- 第 24 段的英文 department 在 zh-TW 無詞庫時被變成中文；相關詞庫及 auto 能保留英文。
- 第 26 段在 zh-TW 相關詞庫保留英文，但增加了參考沒有的 It's、漏掉中文「對」。auto 無詞庫則把中文部分也改成英文；不能把自動語言視為全面解法。
- 第 55 段參考的 can not 在全部條件都成為 can now。詞庫和自動語言都沒有解決否定誤辨。
- 當次沒有把無關詞 DreamType 或 Cloudflare 插入文字；不代表所有無關詞都不干擾。

因此不更換正式語言預設，也不以詞庫強制回填否定。常用詞確實進入辨識並能影響輸出，但不能保證忠實語意；下一步需要模型路線及更多自然口述驗證。單次延遲包含暖機差異，不用來宣稱更快。

完整輸出：[固定中文](evidence/mixed-vocabulary/zh.json)、[自動語言](evidence/mixed-vocabulary/auto.json)。這批是本機服務，未測手機網路延遲。
