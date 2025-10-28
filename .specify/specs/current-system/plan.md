# 技術計畫：LINE Bot 名片管理系統

## 架構概述

系統採用 Clean Architecture 設計，分為以下層次：
1. **API 層** (src/namecard/api/) - 處理外部請求和回應
2. **應用層** (src/namecard/application/) - 業務邏輯和使用案例
3. **核心層** (src/namecard/core/) - 領域模型和介面
4. **基礎設施層** (src/namecard/infrastructure/) - 外部服務整合

```
┌─────────────────────────────────────────┐
│         LINE Messaging API              │
│     (Webhook: /callback)                │
└───────────────┬─────────────────────────┘
                │
┌───────────────▼─────────────────────────┐
│      API Layer (Flask)                  │
│  - LINE Bot Handler                     │
│  - Webhook Signature Verification       │
│  - Command Parser                       │
└───────────────┬─────────────────────────┘
                │
┌───────────────▼─────────────────────────┐
│    Application Layer                    │
│  - UserService (Batch Processing)       │
│  - SecurityService (Rate Limiting)      │
│  - Session Management                   │
└───────────────┬─────────────────────────┘
                │
┌───────────────▼─────────────────────────┐
│      Core Layer                         │
│  - BusinessCard Model                   │
│  - BatchProcessResult Model             │
│  - ProcessingStatus Model               │
└───────────────┬─────────────────────────┘
                │
┌───────────────▼─────────────────────────┐
│   Infrastructure Layer                  │
│  - CardProcessor (Gemini AI)            │
│  - NotionClient (Notion API)            │
│  - Encryption Service                   │
└─────────────────────────────────────────┘
```

## 元件設計

### 1. LINE Bot Handler
**目的**：處理 LINE webhook 事件和使用者互動
**位置**：`src/namecard/api/line_bot/main.py`
**職責**：
- 驗證 LINE 簽章
- 解析使用者命令（help, 批次, 狀態, 結束批次）
- 處理圖片訊息
- 管理批次模式狀態
- 回傳格式化訊息和 Quick Reply

**介面**：
```python
@app.route("/callback", methods=["POST"])
def callback():
    """LINE webhook 端點"""
    # 1. 驗證簽章
    # 2. 解析事件
    # 3. 路由到對應處理器
    # 4. 回傳 200 OK
```

**相依性**：
- `linebot.v3.webhooks` - LINE SDK
- `SecurityService` - 簽章驗證
- `UserService` - 使用者狀態管理
- `CardProcessor` - 名片辨識
- `NotionClient` - 資料儲存

**關鍵流程**：
1. 接收 webhook 事件
2. 驗證 HMAC-SHA256 簽章
3. 解析訊息類型（文字/圖片）
4. 執行對應命令或處理圖片
5. 更新使用者狀態
6. 回傳結果訊息

### 2. CardProcessor (AI 處理)
**目的**：使用 Google Gemini AI 辨識名片內容
**位置**：`src/namecard/infrastructure/ai/card_processor.py`
**職責**：
- 整合 Google Gemini API
- 多卡片偵測
- 結構化資料擷取
- 信心分數計算
- 台灣地址和電話正規化

**介面**：
```python
class CardProcessor:
    def process_image(self, image_data: bytes) -> List[BusinessCard]:
        """處理名片圖片，回傳辨識結果清單"""

    def _call_gemini_api(self, image_data: bytes, model: str) -> dict:
        """呼叫 Gemini API"""

    def _normalize_taiwan_address(self, address: str) -> str:
        """正規化台灣地址"""

    def _normalize_phone_number(self, phone: str) -> str:
        """正規化電話號碼"""
```

**相依性**：
- `google.generativeai` - Gemini AI SDK
- `PIL` - 圖片處理
- `BusinessCard` - 核心模型

**AI 提示設計**：
```python
PROMPT = """
分析這張圖片中的所有名片，並以 JSON 格式回傳：
{
  "cards": [
    {
      "name": "姓名",
      "company": "公司",
      "title": "職稱",
      "department": "部門",
      ...
      "confidence_score": 85
    }
  ]
}

規則：
1. 優先擷取中文資訊
2. 偵測多張名片時分別回傳
3. 提供信心分數 (0-100)
4. 正規化台灣電話和地址格式
"""
```

**錯誤處理**：
- Primary API 失敗 → 切換至 Fallback API
- Gemini 2.5 失敗 → 降級至 Gemini 1.5
- 安全過濾觸發 → 使用寬鬆設定重試
- JSON 解析失敗 → 記錄並回傳錯誤

### 3. NotionClient (資料儲存)
**目的**：管理 Notion 資料庫操作
**位置**：`src/namecard/infrastructure/storage/notion_client.py`
**職責**：
- 建立名片頁面
- 搜尋名片（按姓名/公司）
- 查詢使用者的所有名片
- 處理 Notion 欄位對應
- 自動建立 Select 選項

**介面**：
```python
class NotionClient:
    def create_card(self, card: BusinessCard) -> str:
        """建立名片頁面，回傳頁面 ID"""

    def search_by_name(self, name: str) -> List[dict]:
        """按姓名搜尋"""

    def search_by_company(self, company: str) -> List[dict]:
        """按公司搜尋"""

    def get_user_cards(self, user_id: str) -> List[dict]:
        """取得使用者的所有名片"""
```

**相依性**：
- `notion_client` - Notion SDK
- `BusinessCard` - 核心模型

**欄位對應**：
```python
PROPERTY_MAPPING = {
    "name": "姓名",      # Title (優先中文)
    "company": "公司",   # Text
    "title": "職稱",     # Select (自動建立選項)
    "department": "部門", # Select (自動建立選項)
    "phone": "電話",     # Phone
    "email": "Email",    # Email
    "address": "地址",   # Text
    "website": "網站",   # URL
    "line_id": "LINE ID", # Text
    "fax": "傳真"        # Text
}
```

**重試機制**：
- 最多重試 3 次
- 指數退避（1s, 2s, 4s）
- 記錄每次重試

### 4. UserService (批次處理)
**目的**：管理使用者會話和批次處理
**位置**：`src/namecard/application/user_service.py`
**職責**：
- 追蹤批次模式狀態
- 計算處理統計
- 實施每日速率限制
- 清理過期會話

**介面**：
```python
class UserService:
    def start_batch_mode(self, user_id: str) -> bool:
        """開始批次模式"""

    def end_batch_mode(self, user_id: str) -> BatchProcessResult:
        """結束批次模式並回傳摘要"""

    def get_status(self, user_id: str) -> ProcessingStatus:
        """取得使用者處理狀態"""

    def check_rate_limit(self, user_id: str) -> bool:
        """檢查是否達到每日限制"""

    def cleanup_inactive_sessions(self):
        """清理 24 小時未活動的會話"""
```

**相依性**：
- `ProcessingStatus` - 核心模型
- `BatchProcessResult` - 核心模型

**會話儲存**：
```python
# 記憶體儲存（可改用 Redis）
user_sessions: Dict[str, ProcessingStatus] = {}

class ProcessingStatus:
    user_id: str
    batch_mode: bool
    cards_processed_today: int
    successful_cards: int
    failed_cards: int
    last_activity: datetime
```

### 5. SecurityService (安全服務)
**目的**：處理認證、授權和輸入驗證
**位置**：`src/namecard/application/security_service.py`
**職責**：
- LINE 簽章驗證
- 輸入淨化
- 速率限制檢查
- 敏感資料加密

**介面**：
```python
class SecurityService:
    def verify_line_signature(
        self,
        body: bytes,
        signature: str
    ) -> bool:
        """驗證 LINE webhook 簽章"""

    def sanitize_input(self, text: str) -> str:
        """淨化使用者輸入"""

    def encrypt_sensitive_data(self, data: str) -> str:
        """加密敏感資料"""

    def decrypt_sensitive_data(self, encrypted: str) -> str:
        """解密敏感資料"""
```

**簽章驗證**：
```python
# HMAC-SHA256 驗證
hash = hmac.new(
    channel_secret.encode('utf-8'),
    body,
    hashlib.sha256
).digest()
signature = base64.b64encode(hash).decode('utf-8')
```

## 資料模型變更

### 核心模型

```python
# src/namecard/core/models/card.py
class BusinessCard(BaseModel):
    """名片資料模型"""
    name: str
    company: Optional[str] = None
    title: Optional[str] = None
    department: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    website: Optional[HttpUrl] = None
    line_id: Optional[str] = None
    fax: Optional[str] = None
    confidence_score: int = Field(ge=0, le=100)
    user_id: str

    @validator('phone')
    def normalize_phone(cls, v):
        """正規化電話號碼"""
        if v:
            return normalize_taiwan_phone(v)
        return v

    @validator('address')
    def normalize_address(cls, v):
        """正規化地址"""
        if v:
            return normalize_taiwan_address(v)
        return v

class BatchProcessResult(BaseModel):
    """批次處理結果"""
    total_processed: int
    successful: int
    failed: int
    start_time: datetime
    end_time: datetime
    duration_seconds: float

class ProcessingStatus(BaseModel):
    """使用者處理狀態"""
    user_id: str
    batch_mode: bool = False
    cards_processed_today: int = 0
    successful_cards: int = 0
    failed_cards: int = 0
    last_activity: datetime
    daily_limit: int = 50
```

## API 設計

### Webhook 端點

#### POST /callback
**描述**：LINE webhook 端點
**請求**：
```json
{
  "events": [
    {
      "type": "message",
      "message": {
        "type": "text|image",
        "text": "help",
        "id": "message_id"
      },
      "source": {
        "userId": "U123456"
      }
    }
  ]
}
```

**回應**：`200 OK`（立即回傳，避免超時）

**處理流程**：
1. 驗證簽章
2. 解析事件類型
3. 非同步處理（如果需要）
4. 回傳 200 OK

### 健康檢查端點

#### GET /health
**描述**：系統健康檢查
**回應**：
```json
{
  "status": "healthy",
  "timestamp": "2025-10-28T10:00:00Z",
  "services": {
    "line": "ok",
    "gemini": "ok",
    "notion": "ok"
  }
}
```

#### GET /test
**描述**：系統設定檢查
**回應**：顯示環境變數設定狀態

#### GET /debug/notion
**描述**：Notion 資料庫欄位驗證
**回應**：顯示資料庫結構和欄位對應

## 外部服務整合

### LINE Messaging API
- **端點**: `https://api.line.me/v2/bot/message`
- **認證**: Bearer Token
- **功能**:
  - 回覆訊息 (reply_message)
  - 推送訊息 (push_message)
  - 取得訊息內容 (get_message_content)
- **速率限制**: 遵循 LINE 平台限制

### Google Gemini AI
- **主要模型**: `gemini-2.5-flash-preview-0514`
- **備援模型**: `gemini-1.5-flash`
- **認證**: API Key
- **安全設定**:
  ```python
  safety_settings = {
      HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
      HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
      HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
      HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
  }
  ```

### Notion API
- **版本**: v1
- **端點**: `https://api.notion.com/v1`
- **認證**: Bearer Token (Integration Token)
- **重要 Headers**:
  - `Notion-Version: 2022-06-28`
  - `Content-Type: application/json`

## 測試策略

### 單元測試
- **CardProcessor**: 模擬 Gemini API 回應
- **NotionClient**: 模擬 Notion API
- **UserService**: 測試批次處理邏輯
- **SecurityService**: 測試簽章驗證
- **BusinessCard**: 測試資料驗證和正規化

### 整合測試
- **test_health.py**: API 端點健康檢查
- **test_card_models.py**: Pydantic 模型驗證
- **test_user_service.py**: 批次處理和速率限制

### 覆蓋率目標
- 核心業務邏輯：90%+
- 整體覆蓋率：70%+

## 安全性考量

### 認證與授權
- LINE Webhook 簽章驗證（HMAC-SHA256）
- Notion Integration Token 管理
- Google API Key 安全儲存

### 輸入驗證
- 圖片大小限制（10MB）
- 圖片格式檢查
- 文字內容淨化
- Email 和 URL 格式驗證

### 速率限制
- 每位使用者每日 50 張名片
- 批次大小限制 10 張
- 會話超時 30 分鐘

### 資料加密
- Fernet 對稱加密敏感資料
- 環境變數儲存機密資訊
- 日誌中遮罩敏感資訊

## 部署計畫

### 前置條件
- Zeabur 專案和服務設定
- 環境變數配置
- LINE Bot Channel 設定
- Notion Integration 和資料庫設定

### CI/CD 流程

```yaml
# .github/workflows/deploy.yml
stages:
  1. test:
     - pytest with coverage
     - coverage report

  2. security-scan:
     - bandit (Python security)
     - safety check (dependencies)

  3. deploy:
     - trigger Zeabur deployment
     - wait for deployment

  4. performance-test:
     - health check
     - endpoint response time test
```

### 部署策略
- **零停機部署**: Zeabur 自動處理
- **回退計畫**: Git revert + 重新部署
- **健康檢查**: `/health` 端點驗證

### 監控與告警
- **Sentry**: 錯誤追蹤和告警
- **應用日誌**: 記錄關鍵操作和錯誤
- **GitHub Actions**: CI/CD 狀態監控

## 風險評估

### 技術風險

1. **風險：Gemini API 配額不足**
   - **緩解措施**：使用備援 API 金鑰、監控使用量
   - **應變計畫**：實作請求佇列、降級服務

2. **風險：Notion API 速率限制**
   - **緩解措施**：實作重試機制和指數退避
   - **應變計畫**：暫存待處理請求、分批處理

3. **風險：會話資料記憶體溢位**
   - **緩解措施**：定期清理過期會話
   - **應變計畫**：遷移至 Redis

### 營運風險

1. **風險：LINE Webhook 超時**
   - **緩解措施**：立即回傳 200 OK，非同步處理
   - **應變計畫**：優化處理流程、增加超時時間

2. **風險：資料庫欄位不匹配**
   - **緩解措施**：啟動時驗證 Notion 欄位
   - **應變計畫**：提供 /debug/notion 端點診斷

## 時程估計

已完成的系統，此為現況文件。

## 改進建議

### 短期（1-3 個月）
1. 實作 Redis 會話儲存
2. 新增名片去重功能
3. 改善錯誤訊息的上下文資訊
4. 新增使用統計儀表板

### 中期（3-6 個月）
1. 名片匯出功能（Excel、PDF）
2. 名片編輯介面
3. 進階搜尋功能
4. 批次匯入歷史名片

### 長期（6-12 個月）
1. 團隊協作功能
2. AI 輔助名片分類
3. 自動化後續追蹤提醒
4. 與 CRM 系統整合
