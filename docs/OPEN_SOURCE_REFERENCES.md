# 值得參考的開源專案

以下根據官方 README 與文件整理（2026-09-20），不是已移植到 DreamType 的功能，也不是實測排名。

| 專案 | 已提供的能力 | 建議學習方向 |
|---|---|---|
| [Voice Keyboard](https://github.com/rustemar/voice-keyboard) | 錄音佇列、斷線保存與重送、自訂詞彙 | 優先改善失敗時不用重說。DreamType 可採用明確的手動重送與刪除，而非直接照搬自動重送。 |
| [Deskdrop](https://github.com/SvReenen/Deskdrop) | 結果預覽、重試、複製、捨棄與 Undo，自訂工具列與指令 | 改寫前後比較、容易復原；讓聊天／工作／需求說明等提示詞有清楚的切換入口。 |
| [HeliBoard](https://github.com/HeliBorg/HeliBoard) | 版面與主題、剪貼簿、單手模式、設定備份還原 | 學習鍵盤配置與輸入細節。它不是 AI 語音服務，也不能據此保證繁中輸入體驗。 |
| [Obtainium](https://github.com/ImranR98/Obtainium) | 從 GitHub 等來源安裝更新、版本通知 | 減少手動找 APK 的步驟，可作外部更新工具評估。 |

建議順序：先做斷線不丟錄音、容易修改復原，再做情境提示詞切換及更新流程。引用程式碼前需按來源檔案授權保留相應聲明。

介面方向另參考 [Typeless 官方介紹](https://www.typeless.com/) 的語音輸入流程；DreamType 使用自己的名稱與 logo。
