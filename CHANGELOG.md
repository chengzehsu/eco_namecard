# 更新日誌

所有重要的專案變更都會記錄在此文件中。

格式基於 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.0.0/)，
並且本專案遵循 [語義化版本](https://semver.org/lang/zh-TW/)。

## [1.2.1] - 2026-01-19

### 新增
- 🔄 **彈性配額重置機制**
  - 支援三種重置週期：每日 (daily)、每週 (weekly)、每月 (monthly)
  - 可在租戶層級配置重置週期和重置日
  - 每日模式：每日凌晨自動重置
  - 每週模式：可選週一至週日的任一天重置
  - 每月模式：可選 1-28 號的任一天重置（預設 1 號）
  - 用戶訊息根據重置週期顯示正確的等待時間
  - 管理後台新增重置週期設定介面

- 📈 **每日名片上限提高**
  - `daily_card_limit` 最大值從 1000 提升至 10000
  - 支援新客戶大量匯入歷史名片

---

## [1.2.0] - 2026-01-18

### 新增
- 📱 **電話號碼正規化** - 使用 Google libphonenumber 庫
  - 支援台灣手機（0912-345-678 → +886912345678）
  - 支援台灣市話（02-1234-5678 → +886212345678）
  - 支援國際電話（+1-123-456-7890 → +11234567890）
  - 自動正規化為 E.164 國際格式
  - AI 識別優先提取手機號碼

- 🔧 **Worker 穩定性改善**
  - 獨立 RQ Worker 進程（透過 honcho/Procfile 管理）
  - 同步上傳 Fallback（當 Redis 不可用時）
  - 新增 `/admin/worker/status` 監控端點
  - 新增 `/admin/worker/failed-tasks` 查看失敗任務
  - 新增 `/admin/worker/retry-all` 重試所有失敗任務

### 新增依賴
- `phonenumbers>=8.13.0` - 電話號碼解析和正規化

### 新增檔案
- `src/namecard/core/utils/phone_utils.py` - 電話號碼正規化工具

---

## [1.0.0] - 2024-08-14

### 新增
- 🎯 初始版本的 LINE Bot 名片管理系統
- 🤖 Google Gemini AI 名片識別功能
- 📄 Notion 資料庫自動存儲
- 📦 批次處理模式
- 🔍 多名片檢測功能
- 🗺️ 台灣地址正規化
- 🔐 完整的安全性和錯誤處理機制
- 🚀 GitHub Actions CI/CD 自動部署
- ☁️ Zeabur 雲端部署配置
- 🧪 完整的測試套件 (pytest)
- 📊 健康檢查和監控端點
- 📝 結構化日誌系統 (structlog)
- 🛡️ Sentry 錯誤監控整合 (可選)

### 功能特色
- ✅ LINE Bot 掃描名片
- ✅ AI 智能識別 (90% 準確率)
- ✅ 自動存入 Notion 資料庫
- ✅ 批次處理支援
- ✅ 多名片同時檢測
- ✅ 地址標準化
- ✅ API 備用機制
- ✅ Rate Limiting (50張/日/用戶)
- ✅ 圖片格式和大小驗證
- ✅ 用戶會話管理

### 技術架構
- **後端**: Python 3.11 + Flask
- **AI 引擎**: Google Gemini AI
- **資料庫**: Notion Database
- **部署**: Zeabur + GitHub Actions
- **測試**: pytest + 覆蓋率報告
- **日誌**: structlog + Sentry

### 開發工具
- **代碼品質**: Black + Flake8 + MyPy
- **安全性**: Bandit + Safety
- **容器化**: Docker
- **CI/CD**: GitHub Actions

### API 端點
- `POST /callback` - LINE Webhook
- `GET /health` - 健康檢查
- `GET /test` - 服務測試

### 安全性
- LINE Webhook 簽名驗證
- 輸入資料清理和驗證
- 速率限制和防濫用
- 敏感資料加密
- 安全事件記錄

## [即將推出]

### 計劃功能
- 🔍 重複名片檢測
- 🌐 多語言支援 (英文)
- 🎨 LINE Rich Menu 設計
- 📊 資料分析儀表板
- 🔗 CRM 系統整合
- 📱 進階搜尋功能
- ⚡ 效能優化和快取

---

## 版本說明

### 版本號格式
- **主版本號**: 不相容的 API 修改
- **次版本號**: 向後相容的功能性新增
- **修訂號**: 向後相容的問題修正

### 更新類型
- **新增**: 新功能
- **修改**: 現有功能的變更
- **棄用**: 即將移除的功能
- **移除**: 已移除的功能  
- **修復**: 錯誤修復
- **安全性**: 安全性相關修復