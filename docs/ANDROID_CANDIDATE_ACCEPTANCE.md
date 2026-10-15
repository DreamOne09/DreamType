# Android 候選驗證（2026-10-16）

候選 PR：#82；應用程式版本原始碼 `ce4f99f`，尚未正式發布。

GitHub Android emulator probe [38816135939](https://github.com/DreamOne09/DreamType/actions/runs/38816135939) 成功，已下載並檢查逐項 JSON 與重啟結果：

- Android API 36 模擬器能在外部編輯器顯示鍵盤、錄音、插入結果；密碼欄停用語音，回到一般欄位重新啟用。
- 使用隔離的 beta API、SQLite 與 HTTPS 橋接，登入表單拒絕錯誤密碼後可正常登入。
- 完成結果確認後清除保留錄音，額度依解碼後音訊時長計算。
- 注入輪詢及收件回應遺失時，音訊只上傳一次、provider 只呼叫一次，收件確認重試兩次後成功，沒有重複計費。
- Keystore 與保留錄音通過強制終止程序後的重新讀取檢查，原請求及語言設定保持一致。

這是一次性測試簽章 APK，沒有 Play Billing SDK；不是正式簽章更新驗證。AI provider 為合成輸出，不測辨識準確度，也不代表 Pixel 9、Surfshark、行動網路、TalkBack、真實裝置換機或 Google Play 付款通過。

另外將原本未納入 CI 的十組帳號／恢復 JVM 測試接到既有 runner，完整 21 組在本機通過。正式 Java 程式先對 Android SDK 編譯，測試 fixture 再使用桌面 JSON；Context/Base64 橋接只限 JVM 測試，不能放入 APK。
