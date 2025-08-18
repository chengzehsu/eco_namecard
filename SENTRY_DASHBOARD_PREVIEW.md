# 🎯 Sentry Dashboard 預覽指南

基於我們剛剛執行的測試情境，這是您在 Sentry Dashboard 中會看到的具體內容。

## 📊 Dashboard 概覽

### Issues 頁面會顯示

#### 1. **🔍 錯誤分組 (按 Release)**
```
Release: 1.0.0+2fb11780 (最新)
├── 🚨 ConnectionError: Google Gemini API 連線逾時
├── 🔒 PermissionError: Notion API 權限不足  
├── ⚠️ ValueError: LINE Webhook 簽章驗證失敗
└── 🤖 AI 識別信心度過低警告
```

#### 2. **📈 錯誤詳細資訊範例**

**ConnectionError (AI 處理錯誤)**
```
Error Message: Google Gemini API 連線逾時 - 這是測試錯誤
Release: 1.0.0+2fb11780
Environment: production
User: test_user_001

Stack Trace:
  File "create_sentry_test_scenarios.py", line 86
    raise ConnectionError("Google Gemini API 連線逾時 - 這是測試錯誤")
  
Tags:
  - test_scenario: namecard_processing
  - git_commit: 2fb11780
  - version: 1.0.0
  - component: linebot-namecard

Context:
  namecard_processing:
    image_size: "2.5MB"
    image_format: "JPEG" 
    processing_time: 3.2
    confidence_threshold: 0.3

Breadcrumbs:
  1. 開始處理名片圖片 (image_size: 2.5MB)
  2. Google Gemini API 呼叫 (api: gemini-1.5-flash)
  3. ConnectionError 發生
```

#### 3. **🔒 安全警報範例**
```
Level: FATAL
Message: 安全警報：偵測到暴力破解攻擊
Release: 1.0.0+2fb11780

Context:
  security_event:
    source_ip: "192.168.1.100"
    user_agent: "suspicious_bot_v1.0"
    failed_attempts: 10
    time_window: "5_minutes"

Tags:
  - security_risk: high
  - security_issue: brute_force
  - auto_detected: true
```

## 📈 Performance 頁面會顯示

### 事務監控
```
Operation: slow_image_processing
Duration: 2.00s ⚠️ (超過閾值)
Success Rate: 0% (失敗)
User: test_user_003

Performance Issues:
- 圖片處理耗時過長
- 建議優化或增加超時設定
```

### 效能趨勢圖
```
📊 API 回應時間趨勢:
├── /health: 0.5s
├── /version: 0.3s  
├── slow_image_processing: 2.0s ⚠️
└── notion_save_card: 1.2s
```

## 🏷️ Releases 頁面會顯示

### Release 資訊
```
Release: 1.0.0+2fb11780
Environment: production
Deploy Time: 2025-08-18 13:41:55
Commits: 
  - 2fb1178: feat: add Sentry MCP server integration

Health:
  ❌ 3 Errors
  ⚠️ 2 Warnings  
  ✅ 3 Info Events

Issues Introduced:
  - ConnectionError (AI Processing)
  - PermissionError (Data Storage)
  - ValueError (LINE Bot)

Performance Impact:
  - slow_image_processing: 平均 2.0s
  - 建議關注 API 超時設定
```

### 版本比較
```
📊 Release 健康度比較:
├── 1.0.0+2fb11780 (當前): 60% healthy
├── 1.0.0+ce87104 (前一版): 85% healthy  
└── 1.0.0+42a530c (更早): 90% healthy

回歸分析:
⚠️ 新版本引入了 3 個新錯誤類型
📈 效能有輕微下降趨勢
```

## 🎯 User Impact 分析

### 受影響用戶
```
Users Affected: 4 users
├── test_user_001: AI 處理失敗
├── test_user_002: 批次儲存失敗
├── test_user_003: 效能問題
└── U1234567890abcdef: Webhook 錯誤

Impact Distribution:
- High: 1 user (security threat)
- Medium: 2 users (functionality broken)
- Low: 1 user (performance issue)
```

## 📧 Alert 通知

您會收到的 Email 通知：
```
Subject: [Sentry] New Issues in linebot-namecard

🚨 3 new errors detected in release 1.0.0+2fb11780

High Priority:
- FATAL: 安全警報：偵測到暴力破解攻擊

Medium Priority:  
- ERROR: Google Gemini API 連線逾時
- ERROR: Notion API 權限不足

View in Dashboard: https://sentry.io/...
```

## 🔍 詳細搜索功能

在 Sentry 中您可以使用這些搜尋：

### 按 Release 搜索
```
release:1.0.0+2fb11780
```

### 按錯誤類型搜索
```
error.type:ConnectionError
error.type:PermissionError
```

### 按用戶搜索
```
user.id:test_user_001
```

### 按標籤搜索
```
test_scenario:namecard_processing
security_issue:brute_force
```

### 複合搜索
```
release:1.0.0+2fb11780 AND level:error
environment:production AND category:ai_processing
```

## 📊 Business Intelligence

### 錯誤趨勢分析
```
📈 本週錯誤統計:
├── AI Processing: 35% (增加 ↗️)
├── Data Storage: 25% (穩定 →)  
├── LINE Bot: 20% (減少 ↘️)
├── Security: 15% (新增 🚨)
└── Performance: 5% (穩定 →)
```

### 用戶行為分析
```
👥 用戶使用模式:
├── 批次處理: 增加 400% 📈
├── 單張處理: 穩定 →
├── 錯誤重試: 增加 50% ⚠️
└── 服務放棄: 增加 20% 🚨
```

## 🔧 建議的 Dashboard 設定

### 必看的 Saved Searches
```
1. "高優先級錯誤": level:error OR level:fatal
2. "AI 相關問題": category:ai_processing
3. "安全事件": category:security
4. "效能問題": tag:performance_issue
5. "新版本問題": release:1.0.0+2fb11780
```

### Alert Rules 建議
```
1. 新錯誤類型: 立即通知
2. 錯誤率 > 5%: 15分鐘後通知  
3. 安全事件: 立即通知
4. 效能 > 5秒: 30分鐘後通知
5. 用戶影響 > 10人: 立即通知
```

## 🎉 測試成功的指標

如果設定正確，您應該在 Sentry 中看到：

✅ **Issues 頁面**: 8個測試事件，按 release 分組  
✅ **Performance 頁面**: 效能指標和慢操作警告  
✅ **Releases 頁面**: 1.0.0+2fb11780 release 資訊  
✅ **搜索功能**: 可以按各種條件篩選  
✅ **Source Context**: 點擊錯誤能看到程式碼  
✅ **User Context**: 每個錯誤都有用戶資訊  
✅ **Environment Tags**: production/test 環境區分  
✅ **Git Integration**: 每個錯誤都關聯到 commit  

## 🚀 下一步

1. **設定真實的 SENTRY_DSN** 環境變數在 Zeabur
2. **配置 Alert Rules** 根據您的需求
3. **設定 Email 通知** 接收重要警報
4. **建立 Dashboard** 監控關鍵指標
5. **整合 Slack** (可選) 團隊通知

當服務重新部署完成後，執行 `python3 create_sentry_test_scenarios.py` 就能在真實的 Sentry Dashboard 中看到這些效果！