# 免費優先的雲端試用方案

查核日期：2026-09-30。使用者每天約 40 分鐘、分散多次輸入，要求繁中整理與多語翻譯。本文是候選方案及整合驗收，沒有啟用新供應商、支付費用或上傳私人錄音。

## 先比較兩條路

| 候選 | 可用資源與成本 | 必須驗證 |
|---|---|---|
| Cloudflare Workers AI | 每帳戶每日共享 10,000 Neurons；Whisper Large v3 Turbo 每音訊分鐘 46.63 Neurons；40 分鐘約 1,865.2 Neurons | 實際帳戶可用額度、錄音格式與大小、台灣地名、繁中和中英混說、手機端總延遲 |
| Groq | Whisper Turbo 官方付費單價每小時 US$0.04；20 小時基本辨識約 US$0.80；另有免費方案限制 | 實際組織配額、每段最低 10 秒計費、文字整理與翻譯另外計算、資料條款 |

Cloudflare 剩餘的 8,134.8 Neurons 並不等於全套功能必定免費：文字整理、翻譯、重試與同帳戶其他 AI 工作共用額度。可先比較 `@cf/qwen/qwen3-30b-a3b-fp8`，官方每百萬輸入／輸出 token 分別約 4,625／30,475 Neurons。這只是候選，不代表已證明繁中品質；tokens 需依供應商實際 usage 累計，不能直接以中文字數推算。免費超限會失敗，不自動轉付費或切到未授權服務。

官方來源：[Workers AI 定價](https://developers.cloudflare.com/workers-ai/platform/pricing/)、[Groq 語音 API](https://console.groq.com/docs/speech-to-text)、[Groq 配額](https://console.groq.com/docs/rate-limits)。免費額度不是永久承諾，也不是每個 DreamType 使用者各有一份。

## 如何真正讓家裡電腦關機

第一階段可以只替換 AI 提供者，但帳號、SQLite、工作佇列與手機入口仍在家中。這階段不應宣稱已完成無家用主機的服務。

第二階段才搬移後端：Cloudflare Worker 作為受驗證的 API 入口，另選資料庫與持久化排程方式；現有 Python／SQLite 程式不能只改網址就直接變成 Workers 服務。需要保留以下行為：

- 登入 session、每帳號提示詞和詞庫隔離，管理路由獨立保護。
- 同 request ID 重送不重複辨識、不重扣額度；收件回執、退款及重啟後恢復。
- 加密暫存錄音與結果的到期清除、刪除帳號與備份墓碑紀錄。
- 模型金鑰僅留後端，不放 APK；實際 provider 與費用記錄不含錄音或辨識全文。
- 配額用完明確告知及保留可重試錄音，供應商切換必須在已授權清單內。

R2 是備份儲存，不提供 Whisper／文字模型推論，也不能代替登入資料庫。R2 備份權杖不授予 Workers AI 權限。固定網域只使用 `dreamone.li`，不得修改 `dreamcube.tw`。

## 合成資料試用驗收

先以同一批無私人資訊的音訊比較本機、Cloudflare、Groq；不可用三批不同音訊宣稱某家更準。保存模型版本、音訊時長、真實帳戶 usage、上傳至可插入的端到端時間及失敗率。

文字驗收覆蓋台灣地名、中英混說、全形標點、智慧分段、`●　` 列點、個人詞庫、否定／條件／你我角色，以及「請幫我寫計畫」必須保持口述句子而非執行。翻譯至少英文、日文、泰文、馬來文；未經母語者檢視，不聲稱全面通過。

第二階段驗收必須在家中主機關閉時，由 Pixel 9、行動網路及 Surfshark 實測登入到文字插入、重試、撤回、翻譯與更新。模型 API 的單次成功不能代替這項要求。

## 不優先採用的省錢方式

Vast.ai 等市場可以租其他主機，但依租用時間、儲存及傳输收費，報價浮動；不能把每月說話 20 小時當作整台 GPU 只需租 20 小時，因為還有隨時待命與冷啟動問題。[Vast 官方計費](https://docs.vast.ai/guides/instances/pricing)

免費 Colab 資源不保證、可能終止，且限制一般服務與繞過 notebook 的用途，不能當正式手機後台。[Colab 官方限制](https://research.google.com/colaboratory/intl/en-GB/faq.html)

Gemini 免費服務的資料使用條件與付費服務不同；官方價格表列出免費資料會用於改善產品，商務錄音試用前須先確認適用條款，不能只因免費就自動接入。[Google 官方價格與資料使用](https://ai.google.dev/gemini-api/docs/pricing)
