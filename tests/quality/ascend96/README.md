# ASCEND 自然中英夾雜測試素材

來源：[CAiRE/ASCEND](https://huggingface.co/datasets/CAiRE/ASCEND)，版本 `737e9800ae31be9932ba8464c80366559bd28424`，test split。

作者：Holy Lovenia、Samuel Cahyawijaya、Genta Indra Winata 等，〈ASCEND: A Spontaneous Chinese-English Dataset for Code-switching in Multi-turn Conversation〉，LREC 2022，[論文](https://aclanthology.org/2022.lrec-1.788/)。

本目錄的逐字稿及其衍生資料沿用 **[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)**；不是程式碼授權。原始逐字稿保存在 `original_reference`，`reference` 以 OpenCC s2tw 轉為繁體。音訊未隨 repository 散布。

在固定版本 test 的 373 筆 `language == mixed` 中，按原始順序取第 `floor(i*372/95)` 筆，`i=0..95`；未依辨識結果挑選。96 段合計 405.723 秒，只有兩名說話者（3、17），屬香港收集的自然對話片段，**不是台灣代表性樣本，也不是自然長篇測試**。無法排除基礎模型訓練資料重疊，不稱為獨立盲測。

重建：下載上述版本的 `main/test-00000-of-00001.parquet`，安裝測試依賴 `pyarrow==19.0.1`、`opencc-python-reimplemented`，執行：

```sh
python scripts/prepare_ascend.py --parquet work/ascend-source/main/test-00000-of-00001.parquet --audio-dir work/ascend-audio --manifest tests/quality/ascend96/manifest.json
```

腳本先核對整個 parquet SHA256，再輸出未修改的 WAV 及逐檔雜湊。GPU 測試用 `scripts/compare_gpu_asr.py --corpus ascend96`，必須在現有 GPU 使用者安全停止後執行，並自行負責服務恢復。
