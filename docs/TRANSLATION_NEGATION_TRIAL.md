# 翻譯候選：否定與角色驗收未通過

2026-10-03 使用既有本機 Qwen 4B，在專用測試請求中比較中文指令及引用資料包裝；未改正式翻譯路由。新增 12 件文字案例見 `tests/quality/translation-role-holdout.json`。該組在第一輪前固定，第二輪依第一輪結果調整提示，因此第二輪不能視為全新保留集。

[引用包裝候選](evidence/translation-negation/quoted-candidate.json) 能保留多數角色與拒絕執行來源指令，但 `only-next-week` 將「不是下週以前都可以」翻成「it can be anytime before next week」，直接翻轉否定。`wait-recipient` 的 notify me about the payment 也弱化了「通知我付款」的動作；`quote-own` 的 no follow-up 擴大了不用催款的範圍。

[增加逐項否定提醒](evidence/translation-negation/negation-reminder.json) 沒有修好：同一案變成「it can be anytime after next week」，仍捏造時間許可。兩個候選都不符合部署條件。

這些輸出是合成文字的本機推論，沒有測語音辨識、手機、其他語言或母語者驗收。單次延遲不是效能基準。接下來的候選必須同時通過既有 translation-roles 與本組，且新增未用來調提示的案例；不能只以修好單一錯句宣稱準確。正式流程維持專用 TranslateGemma，但其既有語意缺口仍存在，不能宣稱正式流程已驗收。

逐子句候選亦未通過：[完整輸出](evidence/translation-negation/clause-candidate.json)。`only-next-week` 仍漏掉否定；`wait-own` 把「再付款」翻成再次付款並把付款重複放入前子句；`quote-own` 重複後半句；`quote-breakout` 的譯文陣列少了一項。11/12 格式正確並不等於語意正確，因此未部署。
