# App 更新

0.9.5 起，GitHub APK 版的「我的用語與排版 → 連線與更新」提供「更新時包含測試版」選项，預設關閉。選擇儲存在這支手機，與登入帳號分開。Google Play 版本仍只導向 Play 更新頁面。

穩定頻道讀取 GitHub latest；包含測試版時，從最新 100 筆發布中選出數字版本最高、附有有效 APK 的版本。排除草稿，確認檔案網址屬於 DreamOne09/DreamType 的該發布。支援 DreamType.apk 與 DreamType-版本.apk。不會自行下載、安裝或移除舊版。

有新版時開啟該 tag 的發布頁，而不是 releases/latest。開啟下載前提醒先插入或取回上一筆文字，不要解除安裝。沒有新版時，明確顯示已檢查的頻道，不暗示其他頻道也已最新。

## 發布規則

每個可供手機升級的 APK 必須提高 versionCode，並提高三段式 versionName。`-rc1` 是 GitHub tag 的候選版標記，APK 仍使用三段式版本；目前不把同一三段式版本的不同 rc 當成手機升級。不要以相同 versionName 發布需要這個更新器提示的新 APK。候選版維持 prerelease、不取代穩定 latest。

## 0.9.5 驗證

七組 JVM 測試通過，新增案例涵蓋預覽版自願開啟、確切版本網址、數字比較、不提示降版、草稿排除、APK 缺失與其他網址排除、舊版檔名、同版本優先穩定版。實際更新程式於發布前連接公開 GitHub API，取得穩定 v0.8.0 與預覽 v0.9.4-rc1。

候選 APK 完成編譯及原簽章檢查，versionCode 15；發布資產 SHA-256 與本機相符：`a15ff1579e1cab08b5e7aebb452f5e7d8c90c0786d57aebfd9a34bf5faa7eba1`。新增選項、瀏覽器導向及覆蓋安裝尚未在 Pixel 9 實測；不要把 JVM 測試當成 UI 驗收。
