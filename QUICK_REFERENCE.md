# 快速參考卡 - LINE Bot 維護

## 🚨 緊急檢查（30 秒）

```bash
# 1. 檢查系統是否正常
curl https://namecard-app.zeabur.app/health

# 2. 測試 LINE Bot
發送「help」到 LINE Bot

# 3. 測試名片功能
上傳一張名片照片
```

## 🔧 常用修改位置

### 改回覆訊息 → `src/namecard/api/line_bot/main.py`
```python
# help 訊息
def create_help_message():
    help_text = """在這裡改文字"""

# 成功訊息  
response_text = f"✅ 成功 {success_count}/{len(cards)} 張"
```

### 改 Notion 判斷邏輯 → `src/namecard/infrastructure/storage/notion_client.py`
```python
# 決策影響力
if any(title in card.title for title in ["董事長", "CEO"]):
    influence = "最終決策者"

# 備註內容
if card.fax:
    notes.append(f"傳真: {card.fax}")
```

### 改系統設定 → `simple_config.py`
```python
# 每日限制
rate_limit_per_user: int = Field(default=50)
```

## 📤 部署流程（3 步驟）

```bash
git add .
git commit -m "描述修改內容"
git push origin main
```

等 2-3 分鐘 → 測試功能

## 🆘 出錯復原

```bash
# 回到上一個版本
git reset --hard HEAD~1
git push -f origin main
```

## 🔗 重要連結

- 健康檢查: https://namecard-app.zeabur.app/health
- Notion 欄位: https://namecard-app.zeabur.app/debug/notion  
- 系統設定: https://namecard-app.zeabur.app/test
- 完整指南: 看 MAINTENANCE.md

---
**記住：小步修改，立即測試！** 🎯