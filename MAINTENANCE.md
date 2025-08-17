# LINE Bot 名片識別系統 - 維護指南

## 🎉 恭喜！您的系統成功運作了！

這份指南專為「只懂 for 迴圈」的使用者設計，用最簡單的方式教您維護系統。

## 📖 系統簡介

### 系統就像一條生產線
```
用戶上傳名片照片 → AI 自動識別 → 存入 Notion 資料庫 → 回覆處理結果
```

### 目前狀態
- ✅ LINE Bot 正常運作
- ✅ AI 識別功能正常
- ✅ Notion 資料庫連接正常
- ✅ 自動填寫 10 個欄位，3 個留給人工輸入

## 📁 重要檔案說明

### 🔧 您最可能需要修改的檔案

#### 1. `simple_config.py` - 系統設定檔
**作用：** 存放所有密鑰和基本設定
**何時修改：** 要換環境變數或調整限制時
```python
# 範例：改每日使用限制
rate_limit_per_user: int = Field(default=50)  # 改成你要的數字
```

#### 2. `src/namecard/api/line_bot/main.py` - LINE Bot 主程式
**作用：** 控制所有回覆訊息的內容
**何時修改：** 要改回覆文字時

**常用修改點：**
- 改 help 訊息內容
- 改成功/失敗訊息
- 改使用說明

#### 3. `src/namecard/infrastructure/storage/notion_client.py` - Notion 對接程式
**作用：** 控制如何存入 Notion 資料庫
**何時修改：** 要改欄位映射或判斷邏輯時

## 🔧 常見維護需求

### 1. 修改 LINE Bot 回覆訊息

**檔案位置：** `src/namecard/api/line_bot/main.py`

#### 修改 help 說明訊息
找到 `create_help_message()` 函數：
```python
def create_help_message() -> TextSendMessage:
    help_text = """🎯 名片識別系統

📱 上傳名片照片 → 自動識別存入資料庫
📦 輸入「批次」→ 批次處理模式
📊 輸入「狀態」→ 查看進度

⚡ 支援多張名片同時識別
📋 每日限制：50 張"""
```
**修改方法：** 直接改引號內的文字內容

#### 修改成功訊息
找到這段：
```python
response_text = f"✅ 成功 {success_count}/{len(cards)} 張\n\n"
```
**修改方法：** 改 "✅ 成功" 為你想要的文字

### 2. 調整 Notion 欄位映射

**檔案位置：** `src/namecard/infrastructure/storage/notion_client.py`

#### 修改決策影響力判斷
找到 `_prepare_card_properties()` 函數中的這段：
```python
if card.title:
    if any(title in card.title for title in ["董事長", "CEO", "執行長", "總經理"]):
        influence = "最終決策者"
    elif any(title in card.title for title in ["副總", "經理", "協理"]):
        influence = "關鍵影響者"
```

**要加新職稱：**
```python
# 在方括號內加新職稱
["副總", "經理", "協理", "新職稱"]
```

**要改分類：**
```python
# 改等號後面的文字
influence = "你想要的分類"
```

#### 修改備註欄位內容
找到這段：
```python
notes = []
if card.fax:
    notes.append(f"傳真: {card.fax}")
```

**要加新項目：**
```python
# 照這個格式加在後面
if card.新欄位:
    notes.append(f"新標籤: {card.新欄位}")
```

### 3. 調整每日使用限制

**檔案位置：** `simple_config.py`
```python
# 找到這行，改數字
rate_limit_per_user: int = Field(default=50)  # 改成你要的數字
```

## 🚀 更新部署流程

### 每次修改後的標準步驟：

1. **加入修改到版本控制**
```bash
git add .
```

2. **記錄修改內容**
```bash
git commit -m "說明你改了什麼，例如：修改 help 訊息內容"
```

3. **上傳更新**
```bash
git push origin main
```

4. **等待自動部署**
- 等 2-3 分鐘
- 系統會自動更新

5. **測試是否正常**
- 發送「help」測試回覆
- 上傳名片測試功能

## 🆘 故障排除

### 問題 1：LINE Bot 沒有回應

**檢查步驟：**
1. 開啟 `https://namecard-app.zeabur.app/health`
2. 看是否顯示 `"status": "healthy"`
3. 如果不是，可能是部署失敗

**解決方法：**
- 檢查最後一次的程式修改是否有語法錯誤
- 重新 push 一次試試

### 問題 2：無法存入 Notion

**檢查步驟：**
1. 開啟 `https://namecard-app.zeabur.app/debug/notion`
2. 檢查是否顯示所有欄位
3. 確認 Notion 資料庫欄位沒有被改動

**解決方法：**
- 如果欄位有變，需要修改程式碼對應
- 確認 Notion API 權限正常

### 問題 3：AI 識別錯誤

**說明：** AI 識別準確度無法 100%，這是正常現象

**建議：**
- 在回覆訊息中提醒用戶拍攝清晰照片
- 建議用戶檢查 Notion 中的資料並手動修正

## 📋 維護檢查清單

### 每月檢查（5 分鐘）
- [ ] 發送「help」測試 LINE Bot 回應
- [ ] 上傳一張名片測試完整流程
- [ ] 檢查 Notion 資料庫是否正常儲存
- [ ] 查看 `https://namecard-app.zeabur.app/health` 是否正常

### 有新需求時
- [ ] 先想清楚要改什麼
- [ ] 小步修改（一次只改一個地方）
- [ ] 修改後立即測試
- [ ] 記錄修改內容（commit message）
- [ ] 推送到線上環境
- [ ] 等幾分鐘後測試是否正常

## 💡 給初學者的建議

### 1. 安全修改原則
- **小步修改**：每次只改一點點
- **立即測試**：改完就測試，不要累積
- **記錄變更**：每次 commit 都寫清楚改了什麼
- **備份重要部分**：改之前先複製檔案備份

### 2. 出錯不要慌
- 大部分錯誤都可以復原
- 查看錯誤訊息，通常會提示問題在哪
- 可以回到之前的版本：`git reset --hard HEAD~1`

### 3. 學習資源
- 遇到不懂的 Python 語法，可以問 ChatGPT
- Git 基本指令：`add`, `commit`, `push` 就夠用了
- 保持程式碼格式整齊，容易閱讀

## 🔗 快速連結

- **系統健康檢查**：https://namecard-app.zeabur.app/health
- **Notion 欄位檢查**：https://namecard-app.zeabur.app/debug/notion
- **系統設定檢查**：https://namecard-app.zeabur.app/test
- **GitHub 專案**：https://github.com/chengzehsu/eco_namecard
- **線上服務**：https://namecard-app.zeabur.app

## 📞 需要幫助？

如果遇到無法解決的問題：
1. 記錄錯誤訊息的完整內容
2. 說明修改了什麼
3. 提供錯誤發生的時間
4. 尋求技術支援

---

**記住：這個系統已經成功運作了，大部分時候都不需要修改。維護主要是小幅調整，不用擔心！** 🎉