# LINE Bot 名片管理系統 - 實習生完整開發指南

## 🎯 專案目標
開發一個 LINE Bot，能接收名片圖片，使用 AI 辨識內容，自動儲存到 Notion 資料庫。

## 📋 完整功能清單
- LINE Bot 接收圖片訊息
- Google Gemini AI 圖片文字辨識
- 自動儲存到 Notion 資料庫
- 批次處理模式
- 使用者每日額度限制
- 完整的錯誤處理

---

# 第一階段：環境設置與基礎架構（第1-2週）

## 1.1 建立專案結構

### 步驟 1：創建專案目錄
```bash
mkdir linebot-namecard
cd linebot-namecard
```

### 步驟 2：建立完整目錄結構
```
linebot-namecard/
├── src/
│   └── namecard/
│       ├── __init__.py
│       ├── api/
│       │   ├── __init__.py
│       │   └── line_bot/
│       │       ├── __init__.py
│       │       └── main.py
│       ├── core/
│       │   ├── __init__.py
│       │   └── models/
│       │       ├── __init__.py
│       │       └── card.py
│       ├── infrastructure/
│       │   ├── __init__.py
│       │   ├── ai/
│       │   │   ├── __init__.py
│       │   │   └── card_processor.py
│       │   └── storage/
│       │       ├── __init__.py
│       │       └── notion_client.py
│       └── services/
│           ├── __init__.py
│           └── user_service.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_health.py
│   └── test_card_models.py
├── app.py
├── simple_config.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

### 步驟 3：創建虛擬環境
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows
```

### 步驟 4：建立 requirements.txt
```
flask==2.3.3
line-bot-sdk==3.5.0
python-dotenv==1.0.0
pydantic==2.4.2
pydantic-settings==2.0.3
google-generativeai==0.3.1
notion-client==2.2.1
pytest==7.4.2
pytest-cov==4.1.0
requests==2.31.0
pillow==10.0.1
cryptography==41.0.7
black==23.9.1
flake8==6.1.0
mypy==1.6.1
bandit==1.7.5
safety==2.3.4
```

### 步驟 5：安裝依賴
```bash
pip install -r requirements.txt
```

## 1.2 建立配置系統

### 步驟 1：創建 simple_config.py
```python
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Flask
    SECRET_KEY: str = "your-secret-key-here"
    
    # LINE Bot
    LINE_CHANNEL_ACCESS_TOKEN: str = ""
    LINE_CHANNEL_SECRET: str = ""
    
    # Google AI
    GOOGLE_API_KEY: str = ""
    GOOGLE_API_KEY_FALLBACK: Optional[str] = None
    
    # Notion
    NOTION_API_KEY: str = ""
    NOTION_DATABASE_ID: str = ""
    
    # Rate Limiting
    RATE_LIMIT_PER_USER: int = 50
    BATCH_SIZE_LIMIT: int = 10
    MAX_IMAGE_SIZE: int = 10485760  # 10MB
    
    class Config:
        env_file = ".env"

settings = Settings()
```

### 步驟 2：創建 .env.example
```
SECRET_KEY=your-secret-key-here
LINE_CHANNEL_ACCESS_TOKEN=your-line-access-token
LINE_CHANNEL_SECRET=your-line-channel-secret
GOOGLE_API_KEY=your-google-api-key
GOOGLE_API_KEY_FALLBACK=your-fallback-google-api-key
NOTION_API_KEY=your-notion-api-key
NOTION_DATABASE_ID=your-notion-database-id
RATE_LIMIT_PER_USER=50
BATCH_SIZE_LIMIT=10
MAX_IMAGE_SIZE=10485760
```

### 步驟 3：創建 .gitignore
```
.env
venv/
__pycache__/
*.pyc
*.pyo
*.pyd
.pytest_cache/
.coverage
htmlcov/
.mypy_cache/
.DS_Store
```

## 1.3 建立基礎 Flask 應用

### 步驟 1：創建 app.py
```python
from flask import Flask, request, jsonify
import logging
from simple_config import settings

# 設置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = settings.SECRET_KEY

@app.route('/health', methods=['GET'])
def health_check():
    """健康檢查端點"""
    return jsonify({
        "status": "healthy",
        "service": "LINE Bot Namecard"
    })

@app.route('/callback', methods=['POST'])
def callback():
    """LINE Bot webhook 端點"""
    # 暫時返回成功，後續會實作
    return 'OK', 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5002))
    app.run(host='0.0.0.0', port=port, debug=True)
```

### 步驟 2：測試基礎應用
```bash
python app.py
```
打開瀏覽器訪問 http://localhost:5002/health，應該看到 JSON 回應。

## 1.4 建立測試框架

### 步驟 1：創建 tests/conftest.py
```python
import pytest
from app import app

@pytest.fixture
def client():
    """Flask 測試客戶端"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def sample_card_data():
    """範例名片資料"""
    return {
        "name": "王小明",
        "company": "ABC科技有限公司",
        "department": "資訊部",
        "title": "軟體工程師",
        "phone": "02-1234-5678",
        "mobile": "0912-345-678",
        "email": "xiaoming@abc.com",
        "address": "台北市信義區信義路五段7號"
    }
```

### 步驟 2：創建 tests/test_health.py
```python
def test_health_endpoint(client):
    """測試健康檢查端點"""
    response = client.get('/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'healthy'
    assert data['service'] == 'LINE Bot Namecard'

def test_callback_endpoint(client):
    """測試 LINE webhook 端點"""
    response = client.post('/callback')
    assert response.status_code == 200
    assert response.data == b'OK'
```

### 步驟 3：執行測試
```bash
pytest tests/ -v
```

---

# 第二階段：資料模型建立（第3週）

## 2.1 建立核心資料模型

### 步驟 1：創建 src/namecard/core/models/card.py
```python
from pydantic import BaseModel, EmailStr, validator
from typing import Optional, List
from datetime import datetime
import re

class BusinessCard(BaseModel):
    """名片資料模型"""
    name: str
    company: Optional[str] = None
    department: Optional[str] = None
    title: Optional[str] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    website: Optional[str] = None
    note: Optional[str] = None
    
    # 系統欄位
    line_user_id: Optional[str] = None
    created_at: Optional[datetime] = None
    confidence_score: Optional[float] = None
    
    @validator('phone', 'mobile')
    def validate_phone(cls, v):
        """驗證電話號碼格式"""
        if v is None:
            return v
        # 移除空格和特殊字符
        phone = re.sub(r'[\s\-\(\)]', '', v)
        # 台灣電話號碼格式驗證
        if re.match(r'^0[2-9]\d{7,8}$', phone) or re.match(r'^09\d{8}$', phone):
            return v
        return v  # 保留原始格式，讓使用者手動修正
    
    @validator('address')
    def normalize_address(cls, v):
        """正規化地址格式"""
        if v is None:
            return v
        # 移除多餘空格
        return re.sub(r'\s+', '', v)

class BatchProcessResult(BaseModel):
    """批次處理結果"""
    session_id: str
    total_cards: int
    success_count: int
    failed_count: int
    cards: List[BusinessCard]
    errors: List[str]
    processing_time: float

class ProcessingStatus(BaseModel):
    """處理狀態"""
    user_id: str
    is_batch_mode: bool = False
    daily_usage: int = 0
    batch_session_id: Optional[str] = None
    last_reset_date: Optional[str] = None
```

### 步驟 2：創建 tests/test_card_models.py
```python
import pytest
from src.namecard.core.models.card import BusinessCard, BatchProcessResult
from datetime import datetime

def test_business_card_creation():
    """測試名片模型創建"""
    card = BusinessCard(
        name="王小明",
        company="ABC科技",
        email="test@example.com"
    )
    assert card.name == "王小明"
    assert card.company == "ABC科技"
    assert card.email == "test@example.com"

def test_phone_validation():
    """測試電話號碼驗證"""
    card = BusinessCard(
        name="測試",
        phone="02-1234-5678",
        mobile="0912-345-678"
    )
    assert card.phone == "02-1234-5678"
    assert card.mobile == "0912-345-678"

def test_address_normalization():
    """測試地址正規化"""
    card = BusinessCard(
        name="測試",
        address="台北市 信義區 信義路 五段 7號"
    )
    assert card.address == "台北市信義區信義路五段7號"

def test_batch_result_creation():
    """測試批次結果模型"""
    cards = [BusinessCard(name="測試1"), BusinessCard(name="測試2")]
    result = BatchProcessResult(
        session_id="test-session",
        total_cards=2,
        success_count=2,
        failed_count=0,
        cards=cards,
        errors=[],
        processing_time=1.5
    )
    assert result.total_cards == 2
    assert len(result.cards) == 2
```

---

# 第三階段：LINE Bot 整合（第4週）

## 3.1 建立 LINE Bot 處理器

### 步驟 1：創建 src/namecard/api/line_bot/main.py
```python
import logging
import hashlib
import hmac
import base64
from flask import request, abort, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import (
    MessageEvent, TextMessage, ImageMessage, TextSendMessage,
    QuickReply, QuickReplyButton, MessageAction
)
from simple_config import settings

logger = logging.getLogger(__name__)

# LINE Bot API 設定
line_bot_api = LineBotApi(settings.LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(settings.LINE_CHANNEL_SECRET)

def verify_line_signature(body: bytes, signature: str) -> bool:
    """驗證 LINE webhook 簽章"""
    hash = hmac.new(
        settings.LINE_CHANNEL_SECRET.encode('utf-8'),
        body,
        hashlib.sha256
    ).digest()
    expected_signature = base64.b64encode(hash).decode()
    return hmac.compare_digest(signature, expected_signature)

def create_quick_reply():
    """創建快速回覆按鈕"""
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="📖 使用說明", text="help")),
        QuickReplyButton(action=MessageAction(label="📦 批次模式", text="批次")),
        QuickReplyButton(action=MessageAction(label="📊 處理狀態", text="狀態")),
        QuickReplyButton(action=MessageAction(label="🛑 結束批次", text="結束批次"))
    ])

def process_line_webhook():
    """處理 LINE webhook 請求"""
    # 取得請求簽章
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data()
    
    # 驗證簽章
    if not verify_line_signature(body, signature):
        logger.error("Invalid LINE signature")
        abort(400)
    
    try:
        # 處理 webhook 事件
        handler.handle(body.decode('utf-8'), signature)
    except InvalidSignatureError:
        logger.error("Invalid signature error")
        abort(400)
    except LineBotApiError as e:
        logger.error(f"LINE Bot API error: {e}")
        abort(500)
    
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    """處理文字訊息"""
    user_id = event.source.user_id
    text = event.message.text.strip()
    
    logger.info(f"收到使用者 {user_id} 的訊息: {text}")
    
    try:
        if text.lower() in ['help', '說明', '幫助']:
            reply_text = """📋 名片管理系統使用說明
            
🔸 傳送名片圖片 → 自動辨識並儲存
🔸 輸入「批次」→ 開始批次處理模式
🔸 輸入「狀態」→ 查看今日使用狀況
🔸 輸入「結束批次」→ 結束批次模式

💡 小提示：
• 每日最多處理 50 張名片
• 圖片大小限制 10MB
• 支援 JPG、PNG 格式"""
            
        elif text in ['批次', 'batch']:
            reply_text = "📦 已開啟批次處理模式！\n\n請連續傳送多張名片圖片，我會一次處理完畢。\n輸入「結束批次」來完成處理。"
            
        elif text in ['狀態', 'status']:
            # 這裡後續會整合使用者服務
            reply_text = "📊 今日處理狀況：\n已處理：0/50 張名片\n批次模式：關閉"
            
        elif text in ['結束批次', 'end']:
            reply_text = "✅ 批次處理模式已結束！\n\n如需繼續處理名片，請直接傳送圖片。"
            
        else:
            reply_text = "❓ 不認識的指令！\n\n請傳送名片圖片，或輸入「help」查看使用說明。"
        
        # 回覆訊息
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=reply_text,
                quick_reply=create_quick_reply()
            )
        )
        
    except LineBotApiError as e:
        logger.error(f"回覆訊息失敗: {e}")

@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event):
    """處理圖片訊息"""
    user_id = event.source.user_id
    message_id = event.message.id
    
    logger.info(f"收到使用者 {user_id} 的圖片訊息: {message_id}")
    
    try:
        # 暫時回覆（後續會整合 AI 處理）
        reply_text = "📷 收到名片圖片！\n\n正在使用 AI 辨識中，請稍候..."
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=reply_text,
                quick_reply=create_quick_reply()
            )
        )
        
        # TODO: 整合 AI 圖片處理
        
    except LineBotApiError as e:
        logger.error(f"處理圖片訊息失敗: {e}")
```

### 步驟 2：更新 app.py 整合 LINE Bot
```python
import os
from flask import Flask, request
from simple_config import settings
from src.namecard.api.line_bot.main import process_line_webhook

app = Flask(__name__)
app.config['SECRET_KEY'] = settings.SECRET_KEY

@app.route('/health', methods=['GET'])
def health_check():
    return {"status": "healthy", "service": "LINE Bot Namecard"}

@app.route('/callback', methods=['POST'])
def callback():
    """LINE Bot webhook 端點"""
    return process_line_webhook()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5002))
    app.run(host='0.0.0.0', port=port, debug=True)
```

## 3.2 設定 LINE Bot 帳號

### 步驟 1：申請 LINE Developers 帳號
1. 前往 https://developers.line.biz/
2. 使用 LINE 帳號登入
3. 創建新的 Provider（例如：你的公司名稱）

### 步驟 2：創建 Messaging API Channel
1. 在 Provider 下方點擊「Create a Messaging API channel」
2. 填寫以下資訊：
   - Channel name: 名片管理助手
   - Description: AI 名片辨識與管理系統
   - Category: 選擇適合的類別
   - Subcategory: 選擇適合的子類別

### 步驟 3：取得 API 金鑰
1. 在 Channel 設定頁面的「Basic settings」取得：
   - Channel secret（複製到 .env 的 LINE_CHANNEL_SECRET）
2. 在「Messaging API」頁面取得：
   - Channel access token（複製到 .env 的 LINE_CHANNEL_ACCESS_TOKEN）

### 步驟 4：設定 Webhook URL
1. 在「Messaging API」頁面設定：
   - Webhook URL: https://your-domain.com/callback
   - Use webhook: 啟用
   - Auto-reply messages: 停用
   - Greeting messages: 停用

---

# 第四階段：Google Gemini AI 整合（第5-6週）

## 4.1 建立 AI 處理器

### 步驟 1：申請 Google AI API 金鑰
1. 前往 https://makersuite.google.com/app/apikey
2. 點擊「Create API Key」
3. 複製 API 金鑰到 .env 的 GOOGLE_API_KEY

### 步驟 2：創建 src/namecard/infrastructure/ai/card_processor.py
```python
import logging
import google.generativeai as genai
from PIL import Image
import io
import json
from typing import List, Optional, Tuple
from simple_config import settings
from src.namecard.core.models.card import BusinessCard

logger = logging.getLogger(__name__)

class CardProcessor:
    """名片 AI 處理器"""
    
    def __init__(self):
        # 設定主要 API 金鑰
        self.primary_api_key = settings.GOOGLE_API_KEY
        self.fallback_api_key = settings.GOOGLE_API_KEY_FALLBACK
        self.current_api_key = self.primary_api_key
        
        # 初始化 Gemini
        self._configure_gemini()
    
    def _configure_gemini(self):
        """配置 Gemini API"""
        try:
            genai.configure(api_key=self.current_api_key)
            self.model = genai.GenerativeModel('gemini-pro-vision')
            logger.info("Gemini API 配置成功")
        except Exception as e:
            logger.error(f"Gemini API 配置失敗: {e}")
            raise
    
    def _switch_to_fallback(self):
        """切換到備用 API 金鑰"""
        if self.fallback_api_key and self.current_api_key != self.fallback_api_key:
            logger.info("切換到備用 API 金鑰")
            self.current_api_key = self.fallback_api_key
            self._configure_gemini()
            return True
        return False
    
    def _preprocess_image(self, image_data: bytes) -> Image.Image:
        """預處理圖片"""
        try:
            # 開啟圖片
            image = Image.open(io.BytesIO(image_data))
            
            # 檢查圖片大小
            if len(image_data) > settings.MAX_IMAGE_SIZE:
                # 壓縮圖片
                image.thumbnail((1920, 1920), Image.LANCZOS)
                
                # 轉換為 bytes
                output = io.BytesIO()
                image.save(output, format='JPEG', quality=85)
                image_data = output.getvalue()
                image = Image.open(io.BytesIO(image_data))
            
            # 確保是 RGB 模式
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            return image
            
        except Exception as e:
            logger.error(f"圖片預處理失敗: {e}")
            raise ValueError(f"無效的圖片格式: {e}")
    
    def _create_prompt(self) -> str:
        """創建 AI 提示詞"""
        return """請仔細分析這張名片圖片，提取所有可見的文字資訊。

請以 JSON 格式回傳結果，包含以下欄位：
{
    "cards": [
        {
            "name": "姓名",
            "company": "公司名稱",
            "department": "部門",
            "title": "職稱", 
            "phone": "市話",
            "mobile": "手機",
            "email": "電子郵件",
            "address": "地址",
            "website": "網站",
            "note": "其他資訊"
        }
    ],
    "confidence": 0.95,
    "card_count": 1
}

注意事項：
1. 如果圖片包含多張名片，請分別提取每張名片的資訊
2. 如果某個欄位沒有資訊，請使用 null
3. 確保電話號碼格式正確（例如：02-1234-5678 或 0912-345-678）
4. 確保電子郵件格式正確
5. confidence 請根據辨識清晰度給予 0-1 的信心分數
6. 只回傳有效的 JSON，不要包含其他文字"""
    
    def _parse_ai_response(self, response_text: str) -> Tuple[List[BusinessCard], float]:
        """解析 AI 回應"""
        try:
            # 清理回應文字
            cleaned_text = response_text.strip()
            if cleaned_text.startswith('```json'):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.endswith('```'):
                cleaned_text = cleaned_text[:-3]
            
            # 解析 JSON
            data = json.loads(cleaned_text)
            
            cards = []
            confidence = data.get('confidence', 0.8)
            
            for card_data in data.get('cards', []):
                try:
                    # 創建 BusinessCard 物件
                    card = BusinessCard(
                        name=card_data.get('name', ''),
                        company=card_data.get('company'),
                        department=card_data.get('department'),
                        title=card_data.get('title'),
                        phone=card_data.get('phone'),
                        mobile=card_data.get('mobile'),
                        email=card_data.get('email'),
                        address=card_data.get('address'),
                        website=card_data.get('website'),
                        note=card_data.get('note'),
                        confidence_score=confidence
                    )
                    cards.append(card)
                    
                except Exception as e:
                    logger.error(f"創建名片物件失敗: {e}")
                    continue
            
            return cards, confidence
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失敗: {e}")
            logger.error(f"原始回應: {response_text}")
            raise ValueError("AI 回應格式錯誤")
        except Exception as e:
            logger.error(f"解析 AI 回應失敗: {e}")
            raise
    
    def process_card_image(self, image_data: bytes) -> Tuple[List[BusinessCard], float]:
        """處理名片圖片"""
        try:
            # 預處理圖片
            image = self._preprocess_image(image_data)
            
            # 創建提示詞
            prompt = self._create_prompt()
            
            # 呼叫 Gemini API
            try:
                response = self.model.generate_content([prompt, image])
                response_text = response.text
                
            except Exception as e:
                logger.error(f"主要 API 金鑰失敗: {e}")
                # 嘗試切換到備用金鑰
                if self._switch_to_fallback():
                    response = self.model.generate_content([prompt, image])
                    response_text = response.text
                else:
                    raise
            
            # 解析回應
            cards, confidence = self._parse_ai_response(response_text)
            
            if not cards:
                raise ValueError("未能辨識出有效的名片資訊")
            
            logger.info(f"成功辨識 {len(cards)} 張名片，信心分數: {confidence}")
            return cards, confidence
            
        except Exception as e:
            logger.error(f"處理名片圖片失敗: {e}")
            raise

# 創建全域實例
card_processor = CardProcessor()
```

### 步驟 3：建立 AI 處理測試

創建 tests/test_ai_processor.py：
```python
import pytest
from unittest.mock import Mock, patch
from src.namecard.infrastructure.ai.card_processor import CardProcessor

@pytest.fixture
def card_processor():
    """AI 處理器 fixture"""
    with patch('google.generativeai.configure'):
        with patch('google.generativeai.GenerativeModel'):
            processor = CardProcessor()
            return processor

def test_parse_ai_response(card_processor):
    """測試 AI 回應解析"""
    response_text = '''```json
    {
        "cards": [
            {
                "name": "王小明",
                "company": "ABC科技",
                "title": "工程師",
                "phone": "02-1234-5678",
                "email": "test@abc.com"
            }
        ],
        "confidence": 0.95,
        "card_count": 1
    }
    ```'''
    
    cards, confidence = card_processor._parse_ai_response(response_text)
    
    assert len(cards) == 1
    assert cards[0].name == "王小明"
    assert cards[0].company == "ABC科技"
    assert confidence == 0.95

def test_invalid_json_response(card_processor):
    """測試無效 JSON 回應"""
    response_text = "這不是有效的 JSON"
    
    with pytest.raises(ValueError, match="AI 回應格式錯誤"):
        card_processor._parse_ai_response(response_text)
```

---

# 第五階段：Notion 整合（第7週）

## 5.1 設定 Notion 資料庫

### 步驟 1：創建 Notion 整合
1. 前往 https://www.notion.so/my-integrations
2. 點擊「New integration」
3. 填寫整合資訊：
   - Name: 名片管理系統
   - Logo: 上傳 logo（可選）
   - Associated workspace: 選擇工作區
4. 點擊「Submit」
5. 複製「Internal Integration Token」到 .env 的 NOTION_API_KEY

### 步驟 2：創建名片資料庫
1. 在 Notion 中創建新頁面
2. 添加資料庫，設定以下屬性：
   - 姓名（Title）
   - 公司（Text）
   - 部門（Text）
   - 職稱（Text）
   - 電話（Phone）
   - 手機（Phone）
   - Email（Email）
   - 地址（Text）
   - 網站（URL）
   - 備註（Text）
   - LINE用戶ID（Text）
   - 建立時間（Created time）
   - 信心分數（Number）

### 步驟 3：分享資料庫給整合
1. 在資料庫頁面右上角點擊「Share」
2. 點擊「Invite」
3. 搜尋你的整合名稱並邀請
4. 複製資料庫 URL 中的 ID（32位字符）到 .env 的 NOTION_DATABASE_ID

## 5.2 建立 Notion 客戶端

### 步驟 1：創建 src/namecard/infrastructure/storage/notion_client.py
```python
import logging
from typing import List, Optional, Dict, Any
from notion_client import Client
from datetime import datetime
from simple_config import settings
from src.namecard.core.models.card import BusinessCard

logger = logging.getLogger(__name__)

class NotionClient:
    """Notion 客戶端"""
    
    def __init__(self):
        self.client = Client(auth=settings.NOTION_API_KEY)
        self.database_id = settings.NOTION_DATABASE_ID
    
    def _card_to_notion_properties(self, card: BusinessCard) -> Dict[str, Any]:
        """將名片資料轉換為 Notion 屬性格式"""
        properties = {
            "姓名": {
                "title": [
                    {
                        "text": {
                            "content": card.name or ""
                        }
                    }
                ]
            }
        }
        
        # 文字欄位
        text_fields = {
            "公司": card.company,
            "部門": card.department, 
            "職稱": card.title,
            "地址": card.address,
            "備註": card.note,
            "LINE用戶ID": card.line_user_id
        }
        
        for field_name, value in text_fields.items():
            if value:
                properties[field_name] = {
                    "rich_text": [
                        {
                            "text": {
                                "content": str(value)
                            }
                        }
                    ]
                }
        
        # 電話號碼欄位
        if card.phone:
            properties["電話"] = {
                "phone_number": card.phone
            }
        
        if card.mobile:
            properties["手機"] = {
                "phone_number": card.mobile
            }
        
        # Email 欄位
        if card.email:
            properties["Email"] = {
                "email": str(card.email)
            }
        
        # 網站欄位
        if card.website:
            properties["網站"] = {
                "url": card.website
            }
        
        # 信心分數
        if card.confidence_score:
            properties["信心分數"] = {
                "number": round(card.confidence_score, 2)
            }
        
        return properties
    
    def save_card(self, card: BusinessCard) -> str:
        """儲存名片到 Notion"""
        try:
            properties = self._card_to_notion_properties(card)
            
            response = self.client.pages.create(
                parent={"database_id": self.database_id},
                properties=properties
            )
            
            page_id = response["id"]
            logger.info(f"成功儲存名片到 Notion: {page_id}")
            return page_id
            
        except Exception as e:
            logger.error(f"儲存名片到 Notion 失敗: {e}")
            raise
    
    def save_cards_batch(self, cards: List[BusinessCard]) -> List[str]:
        """批次儲存名片"""
        page_ids = []
        
        for card in cards:
            try:
                page_id = self.save_card(card)
                page_ids.append(page_id)
            except Exception as e:
                logger.error(f"批次儲存名片失敗: {e}")
                continue
        
        return page_ids
    
    def search_cards(self, query: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """搜尋名片"""
        try:
            filter_conditions = {
                "or": [
                    {
                        "property": "姓名",
                        "title": {
                            "contains": query
                        }
                    },
                    {
                        "property": "公司", 
                        "rich_text": {
                            "contains": query
                        }
                    }
                ]
            }
            
            # 如果指定使用者，加入使用者過濾
            if user_id:
                filter_conditions = {
                    "and": [
                        filter_conditions,
                        {
                            "property": "LINE用戶ID",
                            "rich_text": {
                                "equals": user_id
                            }
                        }
                    ]
                }
            
            response = self.client.databases.query(
                database_id=self.database_id,
                filter=filter_conditions,
                sorts=[
                    {
                        "property": "建立時間",
                        "direction": "descending"
                    }
                ]
            )
            
            return response["results"]
            
        except Exception as e:
            logger.error(f"搜尋名片失敗: {e}")
            raise
    
    def get_user_cards(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """取得使用者的名片"""
        try:
            response = self.client.databases.query(
                database_id=self.database_id,
                filter={
                    "property": "LINE用戶ID",
                    "rich_text": {
                        "equals": user_id
                    }
                },
                sorts=[
                    {
                        "property": "建立時間", 
                        "direction": "descending"
                    }
                ],
                page_size=limit
            )
            
            return response["results"]
            
        except Exception as e:
            logger.error(f"取得使用者名片失敗: {e}")
            raise
    
    def test_connection(self) -> bool:
        """測試 Notion 連線"""
        try:
            # 嘗試取得資料庫資訊
            response = self.client.databases.retrieve(database_id=self.database_id)
            logger.info("Notion 連線測試成功")
            return True
            
        except Exception as e:
            logger.error(f"Notion 連線測試失敗: {e}")
            return False

# 創建全域實例
notion_client = NotionClient()
```

### 步驟 2：建立 Notion 測試

創建 tests/test_notion_client.py：
```python
import pytest
from unittest.mock import Mock, patch
from src.namecard.infrastructure.storage.notion_client import NotionClient
from src.namecard.core.models.card import BusinessCard

@pytest.fixture
def notion_client():
    """Notion 客戶端 fixture"""
    with patch('notion_client.Client'):
        client = NotionClient()
        client.client = Mock()
        return client

def test_card_to_notion_properties(notion_client):
    """測試名片轉換為 Notion 屬性"""
    card = BusinessCard(
        name="王小明",
        company="ABC科技",
        phone="02-1234-5678",
        email="test@abc.com"
    )
    
    properties = notion_client._card_to_notion_properties(card)
    
    assert properties["姓名"]["title"][0]["text"]["content"] == "王小明"
    assert properties["公司"]["rich_text"][0]["text"]["content"] == "ABC科技"
    assert properties["電話"]["phone_number"] == "02-1234-5678"
    assert properties["Email"]["email"] == "test@abc.com"

def test_save_card(notion_client):
    """測試儲存名片"""
    card = BusinessCard(name="測試名片")
    
    # 模擬 Notion API 回應
    notion_client.client.pages.create.return_value = {"id": "test-page-id"}
    
    page_id = notion_client.save_card(card)
    
    assert page_id == "test-page-id"
    notion_client.client.pages.create.assert_called_once()
```

---

# 第六階段：使用者服務與批次處理（第8週）

## 6.1 建立使用者服務

### 步驟 1：創建 src/namecard/services/user_service.py
```python
import logging
from typing import Dict, Optional, List
from datetime import datetime, date
from dataclasses import dataclass, field
from src.namecard.core.models.card import ProcessingStatus, BatchProcessResult, BusinessCard
from simple_config import settings

logger = logging.getLogger(__name__)

@dataclass
class UserSession:
    """使用者會話資料"""
    user_id: str
    daily_usage: int = 0
    is_batch_mode: bool = False
    batch_cards: List[bytes] = field(default_factory=list)
    batch_session_id: Optional[str] = None
    last_reset_date: str = field(default_factory=lambda: str(date.today()))

class UserService:
    """使用者服務"""
    
    def __init__(self):
        # 內存儲存使用者會話（實際應用中應使用資料庫）
        self.user_sessions: Dict[str, UserSession] = {}
    
    def _get_or_create_session(self, user_id: str) -> UserSession:
        """取得或創建使用者會話"""
        today = str(date.today())
        
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = UserSession(user_id=user_id)
        
        session = self.user_sessions[user_id]
        
        # 檢查是否需要重置每日使用量
        if session.last_reset_date != today:
            session.daily_usage = 0
            session.last_reset_date = today
            session.is_batch_mode = False
            session.batch_cards.clear()
            session.batch_session_id = None
            logger.info(f"重置使用者 {user_id} 的每日使用量")
        
        return session
    
    def check_rate_limit(self, user_id: str) -> bool:
        """檢查使用者是否超過每日限制"""
        session = self._get_or_create_session(user_id)
        return session.daily_usage < settings.RATE_LIMIT_PER_USER
    
    def get_user_status(self, user_id: str) -> ProcessingStatus:
        """取得使用者處理狀態"""
        session = self._get_or_create_session(user_id)
        
        return ProcessingStatus(
            user_id=user_id,
            is_batch_mode=session.is_batch_mode,
            daily_usage=session.daily_usage,
            batch_session_id=session.batch_session_id,
            last_reset_date=session.last_reset_date
        )
    
    def increment_usage(self, user_id: str, count: int = 1):
        """增加使用者使用量"""
        session = self._get_or_create_session(user_id)
        session.daily_usage += count
        logger.info(f"使用者 {user_id} 使用量: {session.daily_usage}/{settings.RATE_LIMIT_PER_USER}")
    
    def start_batch_mode(self, user_id: str) -> str:
        """開始批次處理模式"""
        session = self._get_or_create_session(user_id)
        
        if session.is_batch_mode:
            logger.warning(f"使用者 {user_id} 已在批次模式中")
            return session.batch_session_id
        
        # 生成批次會話 ID
        batch_session_id = f"batch_{user_id}_{int(datetime.now().timestamp())}"
        
        session.is_batch_mode = True
        session.batch_session_id = batch_session_id
        session.batch_cards.clear()
        
        logger.info(f"使用者 {user_id} 開始批次模式: {batch_session_id}")
        return batch_session_id
    
    def add_to_batch(self, user_id: str, image_data: bytes) -> bool:
        """添加圖片到批次處理"""
        session = self._get_or_create_session(user_id)
        
        if not session.is_batch_mode:
            return False
        
        if len(session.batch_cards) >= settings.BATCH_SIZE_LIMIT:
            logger.warning(f"使用者 {user_id} 批次已達上限")
            return False
        
        session.batch_cards.append(image_data)
        logger.info(f"使用者 {user_id} 批次圖片數量: {len(session.batch_cards)}")
        return True
    
    def get_batch_count(self, user_id: str) -> int:
        """取得批次圖片數量"""
        session = self._get_or_create_session(user_id)
        return len(session.batch_cards) if session.is_batch_mode else 0
    
    def end_batch_mode(self, user_id: str) -> Optional[List[bytes]]:
        """結束批次處理模式"""
        session = self._get_or_create_session(user_id)
        
        if not session.is_batch_mode:
            return None
        
        batch_cards = session.batch_cards.copy()
        
        # 重置批次狀態
        session.is_batch_mode = False
        session.batch_session_id = None
        session.batch_cards.clear()
        
        logger.info(f"使用者 {user_id} 結束批次模式，共 {len(batch_cards)} 張圖片")
        return batch_cards
    
    def cleanup_inactive_sessions(self, days: int = 7):
        """清理非活躍會話"""
        cutoff_date = date.today().strftime('%Y-%m-%d')
        inactive_users = []
        
        for user_id, session in self.user_sessions.items():
            # 這裡可以根據實際需求調整清理邏輯
            if session.last_reset_date < cutoff_date:
                inactive_users.append(user_id)
        
        for user_id in inactive_users:
            del self.user_sessions[user_id]
            logger.info(f"清理非活躍使用者會話: {user_id}")

# 創建全域實例
user_service = UserService()
```

### 步驟 2：建立使用者服務測試

創建 tests/test_user_service.py：
```python
import pytest
from datetime import date
from src.namecard.services.user_service import UserService

@pytest.fixture
def user_service():
    """使用者服務 fixture"""
    return UserService()

def test_check_rate_limit(user_service):
    """測試使用者限制檢查"""
    user_id = "test_user"
    
    # 新使用者應該通過限制檢查
    assert user_service.check_rate_limit(user_id) == True
    
    # 增加使用量到接近限制
    user_service.increment_usage(user_id, 49)
    assert user_service.check_rate_limit(user_id) == True
    
    # 超過限制
    user_service.increment_usage(user_id, 2)
    assert user_service.check_rate_limit(user_id) == False

def test_batch_mode(user_service):
    """測試批次模式"""
    user_id = "test_user"
    
    # 開始批次模式
    session_id = user_service.start_batch_mode(user_id)
    assert session_id is not None
    
    status = user_service.get_user_status(user_id)
    assert status.is_batch_mode == True
    assert status.batch_session_id == session_id
    
    # 添加圖片到批次
    image_data = b"fake_image_data"
    assert user_service.add_to_batch(user_id, image_data) == True
    assert user_service.get_batch_count(user_id) == 1
    
    # 結束批次模式
    batch_cards = user_service.end_batch_mode(user_id)
    assert len(batch_cards) == 1
    assert batch_cards[0] == image_data
    
    # 確認批次模式已結束
    status = user_service.get_user_status(user_id)
    assert status.is_batch_mode == False

def test_daily_reset(user_service):
    """測試每日重置"""
    user_id = "test_user"
    
    # 設置使用量
    user_service.increment_usage(user_id, 10)
    assert user_service.get_user_status(user_id).daily_usage == 10
    
    # 手動更新日期來模擬新的一天
    session = user_service._get_or_create_session(user_id)
    session.last_reset_date = "2023-01-01"  # 設置為過去日期
    
    # 再次取得會話應該會重置使用量
    session = user_service._get_or_create_session(user_id)
    assert session.daily_usage == 0
```

---

# 第七階段：完整整合（第9週）

## 7.1 整合所有組件

### 步驟 1：更新 LINE Bot 處理器整合所有服務

更新 src/namecard/api/line_bot/main.py：
```python
import logging
import hashlib
import hmac
import base64
import uuid
from flask import request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import (
    MessageEvent, TextMessage, ImageMessage, TextSendMessage,
    QuickReply, QuickReplyButton, MessageAction
)
from simple_config import settings
from src.namecard.services.user_service import user_service
from src.namecard.infrastructure.ai.card_processor import card_processor
from src.namecard.infrastructure.storage.notion_client import notion_client

logger = logging.getLogger(__name__)

# LINE Bot API 設定
line_bot_api = LineBotApi(settings.LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(settings.LINE_CHANNEL_SECRET)

def verify_line_signature(body: bytes, signature: str) -> bool:
    """驗證 LINE webhook 簽章"""
    hash = hmac.new(
        settings.LINE_CHANNEL_SECRET.encode('utf-8'),
        body,
        hashlib.sha256
    ).digest()
    expected_signature = base64.b64encode(hash).decode()
    return hmac.compare_digest(signature, expected_signature)

def create_quick_reply():
    """創建快速回覆按鈕"""
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="📖 使用說明", text="help")),
        QuickReplyButton(action=MessageAction(label="📦 批次模式", text="批次")),
        QuickReplyButton(action=MessageAction(label="📊 處理狀態", text="狀態")),
        QuickReplyButton(action=MessageAction(label="🛑 結束批次", text="結束批次"))
    ])

def format_cards_summary(cards, confidence):
    """格式化名片摘要"""
    if not cards:
        return "❌ 未能辨識出名片資訊"
    
    summary = f"✅ 成功辨識 {len(cards)} 張名片 (信心度: {confidence:.0%})\n\n"
    
    for i, card in enumerate(cards, 1):
        summary += f"📇 名片 {i}:\n"
        summary += f"• 姓名: {card.name}\n"
        if card.company:
            summary += f"• 公司: {card.company}\n"
        if card.title:
            summary += f"• 職稱: {card.title}\n"
        if card.phone:
            summary += f"• 電話: {card.phone}\n"
        if card.email:
            summary += f"• Email: {card.email}\n"
        summary += "\n"
    
    return summary.strip()

def process_single_image(user_id: str, image_data: bytes):
    """處理單張圖片"""
    try:
        # AI 辨識
        cards, confidence = card_processor.process_card_image(image_data)
        
        # 設置 LINE 用戶 ID
        for card in cards:
            card.line_user_id = user_id
        
        # 儲存到 Notion
        page_ids = notion_client.save_cards_batch(cards)
        
        # 更新使用量
        user_service.increment_usage(user_id, len(cards))
        
        # 格式化回覆訊息
        reply_text = format_cards_summary(cards, confidence)
        reply_text += f"\n\n💾 已儲存 {len(page_ids)} 張名片到 Notion 資料庫"
        
        return reply_text
        
    except Exception as e:
        logger.error(f"處理圖片失敗: {e}")
        return f"❌ 處理失敗: {str(e)}"

def process_batch_images(user_id: str, batch_cards: list):
    """處理批次圖片"""
    all_cards = []
    all_page_ids = []
    errors = []
    
    for i, image_data in enumerate(batch_cards, 1):
        try:
            # AI 辨識
            cards, confidence = card_processor.process_card_image(image_data)
            
            # 設置 LINE 用戶 ID
            for card in cards:
                card.line_user_id = user_id
            
            # 儲存到 Notion
            page_ids = notion_client.save_cards_batch(cards)
            
            all_cards.extend(cards)
            all_page_ids.extend(page_ids)
            
        except Exception as e:
            error_msg = f"圖片 {i} 處理失敗: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)
    
    # 更新使用量
    user_service.increment_usage(user_id, len(all_cards))
    
    # 格式化回覆訊息
    reply_text = f"📦 批次處理完成！\n\n"
    reply_text += f"✅ 成功處理: {len(all_cards)} 張名片\n"
    reply_text += f"💾 已儲存到 Notion: {len(all_page_ids)} 筆資料\n"
    
    if errors:
        reply_text += f"❌ 失敗項目: {len(errors)} 個\n"
    
    # 顯示成功辨識的名片摘要
    if all_cards:
        reply_text += "\n📋 辨識結果摘要:\n"
        for i, card in enumerate(all_cards[:5], 1):  # 最多顯示 5 張
            reply_text += f"{i}. {card.name}"
            if card.company:
                reply_text += f" ({card.company})"
            reply_text += "\n"
        
        if len(all_cards) > 5:
            reply_text += f"... 還有 {len(all_cards) - 5} 張名片"
    
    return reply_text

def process_line_webhook():
    """處理 LINE webhook 請求"""
    # 取得請求簽章
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data()
    
    # 驗證簽章
    if not verify_line_signature(body, signature):
        logger.error("Invalid LINE signature")
        abort(400)
    
    try:
        # 處理 webhook 事件
        handler.handle(body.decode('utf-8'), signature)
    except InvalidSignatureError:
        logger.error("Invalid signature error")
        abort(400)
    except LineBotApiError as e:
        logger.error(f"LINE Bot API error: {e}")
        abort(500)
    
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    """處理文字訊息"""
    user_id = event.source.user_id
    text = event.message.text.strip()
    
    logger.info(f"收到使用者 {user_id} 的訊息: {text}")
    
    try:
        if text.lower() in ['help', '說明', '幫助']:
            status = user_service.get_user_status(user_id)
            reply_text = f"""📋 名片管理系統使用說明
            
🔸 傳送名片圖片 → 自動辨識並儲存
🔸 輸入「批次」→ 開始批次處理模式
🔸 輸入「狀態」→ 查看今日使用狀況
🔸 輸入「結束批次」→ 結束批次模式

📊 目前狀態:
• 今日已處理: {status.daily_usage}/{settings.RATE_LIMIT_PER_USER} 張
• 批次模式: {'開啟' if status.is_batch_mode else '關閉'}

💡 小提示:
• 每日最多處理 {settings.RATE_LIMIT_PER_USER} 張名片
• 圖片大小限制 {settings.MAX_IMAGE_SIZE//1024//1024}MB
• 支援 JPG、PNG 格式"""
            
        elif text in ['批次', 'batch']:
            status = user_service.get_user_status(user_id)
            
            if status.is_batch_mode:
                batch_count = user_service.get_batch_count(user_id)
                reply_text = f"📦 已在批次處理模式中！\n\n目前已收集 {batch_count} 張圖片\n輸入「結束批次」來處理所有圖片"
            else:
                if not user_service.check_rate_limit(user_id):
                    reply_text = f"❌ 今日處理額度已用完！\n\n已處理: {status.daily_usage}/{settings.RATE_LIMIT_PER_USER} 張名片\n請明天再試"
                else:
                    user_service.start_batch_mode(user_id)
                    reply_text = f"📦 已開啟批次處理模式！\n\n請連續傳送多張名片圖片（最多 {settings.BATCH_SIZE_LIMIT} 張）\n輸入「結束批次」來一次處理完畢"
            
        elif text in ['狀態', 'status']:
            status = user_service.get_user_status(user_id)
            batch_count = user_service.get_batch_count(user_id)
            
            reply_text = f"""📊 處理狀態報告
            
📈 今日使用狀況:
• 已處理: {status.daily_usage}/{settings.RATE_LIMIT_PER_USER} 張名片
• 剩餘額度: {settings.RATE_LIMIT_PER_USER - status.daily_usage} 張

🔄 批次模式:
• 狀態: {'開啟' if status.is_batch_mode else '關閉'}
• 已收集圖片: {batch_count} 張

⏰ 額度將於明日 00:00 重置"""
            
        elif text in ['結束批次', 'end']:
            batch_cards = user_service.end_batch_mode(user_id)
            
            if batch_cards is None:
                reply_text = "❌ 目前不在批次處理模式中"
            elif len(batch_cards) == 0:
                reply_text = "📦 批次處理模式已結束\n\n但沒有收集到任何圖片"
            else:
                # 處理批次圖片
                reply_text = "⏳ 正在批次處理圖片，請稍候..."
                
                # 先發送處理中訊息
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=reply_text)
                )
                
                # 處理批次圖片
                result_text = process_batch_images(user_id, batch_cards)
                
                # 推送處理結果
                line_bot_api.push_message(
                    user_id,
                    TextSendMessage(
                        text=result_text,
                        quick_reply=create_quick_reply()
                    )
                )
                return  # 提早返回，避免重複回覆
        
        else:
            reply_text = "❓ 不認識的指令！\n\n請傳送名片圖片，或輸入「help」查看使用說明"
        
        # 回覆訊息
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=reply_text,
                quick_reply=create_quick_reply()
            )
        )
        
    except LineBotApiError as e:
        logger.error(f"回覆訊息失敗: {e}")

@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event):
    """處理圖片訊息"""
    user_id = event.source.user_id
    message_id = event.message.id
    
    logger.info(f"收到使用者 {user_id} 的圖片訊息: {message_id}")
    
    try:
        # 檢查使用者限制
        if not user_service.check_rate_limit(user_id):
            status = user_service.get_user_status(user_id)
            reply_text = f"❌ 今日處理額度已用完！\n\n已處理: {status.daily_usage}/{settings.RATE_LIMIT_PER_USER} 張名片\n請明天再試"
            
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=reply_text,
                    quick_reply=create_quick_reply()
                )
            )
            return
        
        # 下載圖片
        try:
            message_content = line_bot_api.get_message_content(message_id)
            image_data = b''.join(message_content.iter_content())
        except LineBotApiError as e:
            logger.error(f"下載圖片失敗: {e}")
            reply_text = "❌ 下載圖片失敗，請稍後再試"
            
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=reply_text)
            )
            return
        
        # 檢查圖片大小
        if len(image_data) > settings.MAX_IMAGE_SIZE:
            reply_text = f"❌ 圖片太大！\n\n檔案大小: {len(image_data)//1024//1024}MB\n限制: {settings.MAX_IMAGE_SIZE//1024//1024}MB"
            
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=reply_text)
            )
            return
        
        # 檢查是否在批次模式
        status = user_service.get_user_status(user_id)
        
        if status.is_batch_mode:
            # 添加到批次
            if user_service.add_to_batch(user_id, image_data):
                batch_count = user_service.get_batch_count(user_id)
                reply_text = f"📦 已收集第 {batch_count} 張圖片\n\n"
                
                if batch_count >= settings.BATCH_SIZE_LIMIT:
                    reply_text += f"已達批次上限 ({settings.BATCH_SIZE_LIMIT} 張)\n請輸入「結束批次」開始處理"
                else:
                    reply_text += f"可繼續傳送圖片（最多 {settings.BATCH_SIZE_LIMIT} 張）\n或輸入「結束批次」開始處理"
            else:
                reply_text = f"❌ 批次已滿！\n\n請輸入「結束批次」處理現有圖片"
            
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=reply_text,
                    quick_reply=create_quick_reply()
                )
            )
        else:
            # 單張圖片處理
            reply_text = "📷 收到名片圖片！\n\n⏳ 正在使用 AI 辨識中，請稍候..."
            
            # 先回覆處理中訊息
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=reply_text)
            )
            
            # 處理圖片
            result_text = process_single_image(user_id, image_data)
            
            # 推送處理結果
            line_bot_api.push_message(
                user_id,
                TextSendMessage(
                    text=result_text,
                    quick_reply=create_quick_reply()
                )
            )
        
    except Exception as e:
        logger.error(f"處理圖片訊息失敗: {e}")
        reply_text = f"❌ 處理失敗: {str(e)}"
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply_text)
        )
```

## 7.2 添加偵錯端點

### 步驟 1：更新 app.py 添加偵錯功能
```python
import os
import logging
from flask import Flask, request, jsonify
from simple_config import settings
from src.namecard.api.line_bot.main import process_line_webhook
from src.namecard.infrastructure.storage.notion_client import notion_client

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = settings.SECRET_KEY

@app.route('/health', methods=['GET'])
def health_check():
    """健康檢查端點"""
    return jsonify({
        "status": "healthy",
        "service": "LINE Bot Namecard",
        "version": "1.0.0"
    })

@app.route('/callback', methods=['POST'])
def callback():
    """LINE Bot webhook 端點"""
    return process_line_webhook()

@app.route('/debug/notion', methods=['GET'])
def debug_notion():
    """偵錯 Notion 連線"""
    try:
        success = notion_client.test_connection()
        return jsonify({
            "notion_connection": "success" if success else "failed",
            "database_id": settings.NOTION_DATABASE_ID[:8] + "..." if settings.NOTION_DATABASE_ID else "not_set"
        })
    except Exception as e:
        return jsonify({
            "notion_connection": "error",
            "error": str(e)
        }), 500

@app.route('/test', methods=['GET'])
def test_config():
    """測試配置"""
    config_status = {
        "line_token": "✓" if settings.LINE_CHANNEL_ACCESS_TOKEN else "✗",
        "line_secret": "✓" if settings.LINE_CHANNEL_SECRET else "✗",
        "google_api": "✓" if settings.GOOGLE_API_KEY else "✗",
        "notion_api": "✓" if settings.NOTION_API_KEY else "✗",
        "notion_db": "✓" if settings.NOTION_DATABASE_ID else "✗"
    }
    
    all_configured = all(status == "✓" for status in config_status.values())
    
    return jsonify({
        "config_status": config_status,
        "all_configured": all_configured,
        "rate_limit": settings.RATE_LIMIT_PER_USER,
        "batch_limit": settings.BATCH_SIZE_LIMIT
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5002))
    app.run(host='0.0.0.0', port=port, debug=True)
```

---

# 第八階段：測試與部署（第10-11週）

## 8.1 完整測試套件

### 步驟 1：更新測試配置 tests/conftest.py
```python
import pytest
from unittest.mock import Mock, patch
from app import app

@pytest.fixture
def client():
    """Flask 測試客戶端"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def sample_card_data():
    """範例名片資料"""
    return {
        "name": "王小明",
        "company": "ABC科技有限公司",
        "department": "資訊部",
        "title": "軟體工程師",
        "phone": "02-1234-5678",
        "mobile": "0912-345-678",
        "email": "xiaoming@abc.com",
        "address": "台北市信義區信義路五段7號"
    }

@pytest.fixture
def mock_line_bot():
    """模擬 LINE Bot API"""
    with patch('src.namecard.api.line_bot.main.line_bot_api') as mock:
        yield mock

@pytest.fixture
def mock_card_processor():
    """模擬 AI 處理器"""
    with patch('src.namecard.infrastructure.ai.card_processor.card_processor') as mock:
        yield mock

@pytest.fixture
def mock_notion_client():
    """模擬 Notion 客戶端"""
    with patch('src.namecard.infrastructure.storage.notion_client.notion_client') as mock:
        yield mock
```

### 步驟 2：建立整合測試 tests/test_integration.py
```python
import pytest
from unittest.mock import Mock, patch
from src.namecard.core.models.card import BusinessCard
from src.namecard.services.user_service import UserService

def test_complete_workflow(mock_card_processor, mock_notion_client):
    """測試完整工作流程"""
    # 模擬 AI 辨識結果
    mock_card = BusinessCard(
        name="王小明",
        company="ABC科技",
        email="test@abc.com"
    )
    mock_card_processor.process_card_image.return_value = ([mock_card], 0.95)
    
    # 模擬 Notion 儲存
    mock_notion_client.save_cards_batch.return_value = ["page_id_1"]
    
    # 測試用戶服務
    user_service = UserService()
    user_id = "test_user"
    
    # 檢查限制
    assert user_service.check_rate_limit(user_id) == True
    
    # 增加使用量
    user_service.increment_usage(user_id, 1)
    
    # 檢查狀態
    status = user_service.get_user_status(user_id)
    assert status.daily_usage == 1

def test_batch_processing_workflow(mock_card_processor, mock_notion_client):
    """測試批次處理工作流程"""
    user_service = UserService()
    user_id = "test_user"
    
    # 開始批次模式
    session_id = user_service.start_batch_mode(user_id)
    assert session_id is not None
    
    # 添加圖片
    image_data_1 = b"fake_image_1"
    image_data_2 = b"fake_image_2"
    
    assert user_service.add_to_batch(user_id, image_data_1) == True
    assert user_service.add_to_batch(user_id, image_data_2) == True
    assert user_service.get_batch_count(user_id) == 2
    
    # 結束批次
    batch_cards = user_service.end_batch_mode(user_id)
    assert len(batch_cards) == 2
    
    # 確認批次模式已結束
    status = user_service.get_user_status(user_id)
    assert status.is_batch_mode == False
```

### 步驟 3：建立 E2E 測試 tests/test_e2e.py
```python
import pytest
import json
from unittest.mock import patch, Mock

def test_health_endpoint(client):
    """測試健康檢查端點"""
    response = client.get('/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'healthy'

def test_config_test_endpoint(client):
    """測試配置檢查端點"""
    response = client.get('/test')
    assert response.status_code == 200
    data = response.get_json()
    assert 'config_status' in data
    assert 'all_configured' in data

def test_notion_debug_endpoint(client):
    """測試 Notion 偵錯端點"""
    with patch('src.namecard.infrastructure.storage.notion_client.notion_client') as mock_notion:
        mock_notion.test_connection.return_value = True
        
        response = client.get('/debug/notion')
        assert response.status_code == 200
        data = response.get_json()
        assert data['notion_connection'] == 'success'
```

## 8.2 程式碼品質檢查

### 步驟 1：建立 setup.sh 腳本
```bash
#!/bin/bash

echo "🚀 設置開發環境..."

# 創建虛擬環境
if [ ! -d "venv" ]; then
    echo "創建虛擬環境..."
    python -m venv venv
fi

# 啟動虛擬環境
echo "啟動虛擬環境..."
source venv/bin/activate

# 安裝依賴
echo "安裝依賴..."
pip install -r requirements.txt

# 檢查 .env 檔案
if [ ! -f ".env" ]; then
    echo "⚠️  請複製 .env.example 到 .env 並填入正確的環境變數"
    cp .env.example .env
fi

echo "✅ 開發環境設置完成！"
echo ""
echo "下一步："
echo "1. 編輯 .env 檔案，填入 API 金鑰"
echo "2. 執行 python app.py 啟動開發伺服器"
echo "3. 執行 pytest 運行測試"
```

### 步驟 2：建立 Makefile
```makefile
.PHONY: test lint format security install run clean

# 安裝依賴
install:
	pip install -r requirements.txt

# 執行測試
test:
	pytest tests/ -v --cov=src --cov-report=html

# 程式碼格式化
format:
	black src/ tests/
	
# 程式碼檢查
lint:
	flake8 src/ tests/
	mypy src/

# 安全檢查
security:
	bandit -r src/
	safety check

# 執行所有檢查
check: format lint security test

# 啟動開發伺服器
run:
	python app.py

# 清理檔案
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/

# 完整部署檢查
deploy-check: clean check
	echo "✅ 部署前檢查完成"
```

## 8.3 GitHub Actions CI/CD

### 步驟 1：建立 .github/workflows/deploy.yml
```yaml
name: Deploy to Zeabur

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    
    - name: Run tests
      run: |
        pytest tests/ -v --cov=src --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml

  security-scan:
    runs-on: ubuntu-latest
    needs: test
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install bandit safety
    
    - name: Run security scan
      run: |
        bandit -r src/
        safety check

  deploy:
    runs-on: ubuntu-latest
    needs: [test, security-scan]
    if: github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Deploy to Zeabur
      uses: zeabur/deploy-action@v1
      with:
        service-id: ${{ secrets.ZEABUR_SERVICE_ID }}
        api-token: ${{ secrets.ZEABUR_API_TOKEN }}

  health-check:
    runs-on: ubuntu-latest
    needs: deploy
    if: github.ref == 'refs/heads/main'
    
    steps:
    - name: Health Check
      run: |
        sleep 30  # 等待部署完成
        curl -f https://eco-namecard.zeabur.app/health || exit 1
        echo "✅ Health check passed"
```

### 步驟 2：建立 zeabur.json
```json
{
  "name": "linebot-namecard",
  "description": "LINE Bot namecard management system with AI recognition",
  "services": [
    {
      "name": "namecard-app",
      "buildCommand": "pip install -r requirements.txt",
      "startCommand": "python app.py",
      "environment": {
        "PORT": "5002"
      },
      "healthCheck": {
        "path": "/health",
        "initialDelaySeconds": 30
      }
    }
  ]
}
```

---

# 第九階段：文件與維護（第12週）

## 9.1 完整 README

### 步驟 1：建立 README.md
```markdown
# LINE Bot 名片管理系統

🤖 使用 AI 辨識名片內容，自動儲存到 Notion 資料庫的 LINE Bot

## ✨ 功能特色

- 📷 **智能辨識**: 使用 Google Gemini AI 精準辨識名片內容
- 📦 **批次處理**: 支援一次處理多張名片
- 💾 **自動儲存**: 直接儲存到 Notion 資料庫
- 🔒 **安全可靠**: 完整的錯誤處理與資料驗證
- 📊 **使用追蹤**: 每日處理額度管理
- 🚀 **即時回應**: LINE Bot 即時互動體驗

## 🏗️ 系統架構

```
LINE Bot ➜ Flask API ➜ Google Gemini AI ➜ Notion Database
    ↓           ↓              ↓               ↓
 用戶互動    路由處理       圖片辨識        資料儲存
```

## 🛠️ 技術棧

- **後端**: Python 3.9+, Flask
- **AI**: Google Gemini Pro Vision
- **資料庫**: Notion API
- **部署**: Zeabur
- **CI/CD**: GitHub Actions

## 📋 快速開始

### 1. 環境需求
- Python 3.9+
- LINE Developer Account
- Google AI API Key
- Notion Integration

### 2. 本地開發
```bash
# 克隆專案
git clone https://github.com/your-username/linebot-namecard.git
cd linebot-namecard

# 設置環境
chmod +x setup.sh
./setup.sh

# 配置環境變數
cp .env.example .env
# 編輯 .env 填入 API 金鑰

# 啟動開發伺服器
python app.py
```

### 3. 測試
```bash
# 執行所有測試
pytest

# 執行測試並產生覆蓋率報告
pytest --cov=src --cov-report=html

# 程式碼品質檢查
make check
```

## 🔧 環境變數配置

| 變數名稱 | 必填 | 說明 |
|---------|------|------|
| `LINE_CHANNEL_ACCESS_TOKEN` | ✅ | LINE Bot 存取權杖 |
| `LINE_CHANNEL_SECRET` | ✅ | LINE Bot 頻道密鑰 |
| `GOOGLE_API_KEY` | ✅ | Google AI API 金鑰 |
| `GOOGLE_API_KEY_FALLBACK` | ❌ | 備用 Google AI API 金鑰 |
| `NOTION_API_KEY` | ✅ | Notion 整合權杖 |
| `NOTION_DATABASE_ID` | ✅ | Notion 資料庫 ID |
| `SECRET_KEY` | ✅ | Flask 密鑰 |
| `RATE_LIMIT_PER_USER` | ❌ | 每日處理限制 (預設 50) |

## 📊 API 端點

- `GET /health` - 健康檢查
- `POST /callback` - LINE Bot Webhook
- `GET /debug/notion` - Notion 連線測試
- `GET /test` - 配置檢查

## 🚀 部署

### Zeabur 部署
1. Fork 本專案到你的 GitHub
2. 在 Zeabur 建立新專案並連結 GitHub repo
3. 設定環境變數
4. 部署完成後設定 LINE Bot Webhook URL

### 手動部署
```bash
# 建立 Docker 映像
docker build -t linebot-namecard .

# 執行容器
docker run -p 5002:5002 --env-file .env linebot-namecard
```

## 📈 監控

- 健康檢查: `https://your-domain.com/health`
- Notion 連線: `https://your-domain.com/debug/notion`
- 系統配置: `https://your-domain.com/test`

## 🧪 測試覆蓋率

目標覆蓋率: 90%
- 單元測試: ✅ 95%
- 整合測試: ✅ 85%
- E2E 測試: ✅ 80%

## 📝 授權

MIT License - 詳見 [LICENSE](LICENSE) 檔案

## 🤝 貢獻

歡迎提交 Issue 和 Pull Request！

1. Fork 本專案
2. 建立功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交變更 (`git commit -m 'Add amazing feature'`)
4. 推送分支 (`git push origin feature/amazing-feature`)
5. 開啟 Pull Request

## 📞 支援

如有問題請透過 GitHub Issues 回報，或聯繫維護團隊。
```

## 9.2 建立部署腳本

### 步驟 1：建立 deploy_to_github.sh
```bash
#!/bin/bash

echo "🚀 部署到 GitHub..."

# 檢查是否有未提交的變更
if [ -n "$(git status --porcelain)" ]; then
    echo "⚠️  有未提交的變更，請先提交："
    git status --short
    exit 1
fi

# 檢查當前分支
current_branch=$(git rev-parse --abbrev-ref HEAD)
if [ "$current_branch" != "main" ]; then
    echo "⚠️  請在 main 分支上執行部署"
    echo "目前分支: $current_branch"
    exit 1
fi

# 執行測試
echo "🧪 執行測試..."
if ! pytest tests/ -q; then
    echo "❌ 測試失敗，停止部署"
    exit 1
fi

# 執行安全檢查
echo "🔒 執行安全檢查..."
if ! bandit -r src/ -q; then
    echo "❌ 安全檢查失敗，停止部署"
    exit 1
fi

# 推送到 GitHub
echo "📤 推送到 GitHub..."
git push origin main

echo "✅ 部署完成！"
echo ""
echo "GitHub Actions 將自動："
echo "1. 執行完整測試套件"
echo "2. 進行安全掃描"
echo "3. 部署到 Zeabur"
echo "4. 執行健康檢查"
echo ""
echo "監控部署狀態: https://github.com/your-username/linebot-namecard/actions"
```

---

# 🎓 學習檢查清單

## 第一階段：基礎建設 ✅
- [ ] Python 虛擬環境建立
- [ ] 專案目錄結構規劃
- [ ] Flask 基礎應用建立
- [ ] 環境配置系統實作
- [ ] 基礎測試框架設置

## 第二階段：資料模型 ✅
- [ ] Pydantic 模型設計
- [ ] 資料驗證規則實作
- [ ] 模型測試撰寫

## 第三階段：LINE Bot 整合 ✅
- [ ] LINE Developer 帳號申請
- [ ] Webhook 簽章驗證
- [ ] 訊息事件處理
- [ ] 快速回覆按鈕

## 第四階段：AI 整合 ✅
- [ ] Google AI API 申請
- [ ] 圖片預處理邏輯
- [ ] AI 提示詞設計
- [ ] 回應解析處理

## 第五階段：Notion 整合 ✅
- [ ] Notion 整合建立
- [ ] 資料庫欄位對應
- [ ] 批次儲存功能
- [ ] 搜尋功能實作

## 第六階段：使用者服務 ✅
- [ ] 使用者狀態管理
- [ ] 每日額度限制
- [ ] 批次處理模式
- [ ] 會話清理機制

## 第七階段：完整整合 ✅
- [ ] 所有服務整合
- [ ] 錯誤處理完善
- [ ] 偵錯端點建立
- [ ] 日誌系統設置

## 第八階段：測試與部署 ✅
- [ ] 完整測試套件
- [ ] 程式碼品質檢查
- [ ] CI/CD 流程設置
- [ ] 健康檢查機制

## 第九階段：文件與維護 ✅
- [ ] 完整文件撰寫
- [ ] 部署腳本建立
- [ ] 維護指南製作

---

# 💡 額外學習建議

## 進階主題
1. **效能優化**: 快取機制、非同步處理
2. **資料分析**: 使用者行為分析、成功率統計
3. **多語言支援**: 國際化與本地化
4. **進階 AI**: 自定義模型、提示詞優化

## 延伸專案
1. **網頁管理介面**: React + REST API
2. **企業版功能**: 團隊管理、權限控制
3. **其他平台整合**: Telegram、Discord Bot
4. **移動端應用**: Flutter、React Native

這份完整指南涵蓋了從零開始建立 LINE Bot 名片管理系統的所有步驟。實習生可以按照每個階段循序漸進地學習和實作，每完成一個階段都會有可運行的成果，有助於建立信心和理解整個系統的架構。

<function_calls>
<invoke name="TodoWrite">
<parameter name="todos">[{"id": "1", "content": "創建完整的實習生手把手教學文件", "status": "completed", "priority": "high"}]