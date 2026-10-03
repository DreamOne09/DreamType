# 長錄音的詞庫提示

辨識原本使用 `condition_on_previous_text=False` 與 `initial_prompt`。已安裝的 faster-whisper 在每個解碼視窗後重設歷史 token，因此初始提示不會傳到後續視窗。改為 `hotwords`，沿用原有 200 token 上限，不同時提供 initial_prompt，避免提示重複。

`scripts/check_speech_hint_windows.py` 使用已安裝套件的真正 generate_segments/get_prompt 流程、合成解碼輸出，不載入模型或 GPU。三段的提示存在情形由 `[true,false,false]` 變成 `[true,true,true]`。這是傳遞測試，不是語音準確率測試。

實際主機另以 CC0 公開台灣語音樣本 0 到 6，依序串接並重複一次（67.008 秒）測試。詞庫是「東華大學、聯外道路、新店端」，刻意包含參考答案，因此不能當作無提示辨識基準。來源與各原始音訊 SHA-256 見 tests/quality/public-taiwan-speech.json；音訊未加入 Git。

[舊輸出](evidence/continuous-vocabulary/before.json) 第二次出現「聯外道路」時變成「連外道路」；[新輸出](evidence/continuous-vocabulary/after.json) 兩次皆保留「聯外道路」。仍有「急速／極速」和「是內建／室內建」誤辨，未宣稱全面改善。這是串接短句，不等於自然長口述或使用者問題重現；延遲單次數值也不能證明速度提升。

25 組個人化回歸測試通過。本機服務已載入此修正，不需更新手機 APK。仍待更多自然音訊、無關詞干擾與使用者實例驗證。
