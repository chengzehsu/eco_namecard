import pytest
import os
import sys
from unittest.mock import Mock, patch

# 添加項目根目錄到 Python 路徑
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Mock genai before importing anything else to prevent initialization errors
with patch('src.namecard.infrastructure.ai.card_processor.genai') as mock_genai:
    mock_genai.configure.return_value = None
    mock_model = Mock()
    mock_model.generate_content.return_value = Mock(text='{"cards": []}')
    mock_genai.GenerativeModel.return_value = mock_model
    
    from src.namecard.api.line_bot.main import app
    from src.namecard.core.models.card import BusinessCard
    from datetime import datetime


@pytest.fixture
def client():
    """Flask 測試客戶端"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def sample_business_card():
    """範例名片資料"""
    return BusinessCard(
        name="張三",
        company="測試公司有限公司",
        title="技術總監",
        phone="02-1234-5678",
        email="test@example.com",
        address="台北市信義區信義路五段7號",
        website="https://www.example.com",
        confidence_score=0.95,
        quality_score=0.9,
        line_user_id="test_user_123"
    )


@pytest.fixture
def mock_line_bot_api():
    """模擬 LINE Bot API"""
    with patch('src.namecard.api.line_bot.main.line_bot_api') as mock:
        yield mock


@pytest.fixture
def mock_card_processor():
    """模擬名片處理器"""
    with patch('src.namecard.api.line_bot.main.card_processor') as mock:
        yield mock


@pytest.fixture
def mock_notion_client():
    """模擬 Notion 客戶端"""
    with patch('src.namecard.api.line_bot.main.notion_client') as mock:
        mock.database_url = "https://notion.so/test-database"
        yield mock


@pytest.fixture
def sample_image_data():
    """範例圖片數據"""
    # 返回一個簡單的測試用圖片數據
    return b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'


@pytest.fixture(autouse=True)
def setup_env():
    """設置測試環境變數"""
    test_env = {
        'LINE_CHANNEL_ACCESS_TOKEN': 'test_token',
        'LINE_CHANNEL_SECRET': 'test_secret',
        'GOOGLE_API_KEY': 'test_key',
        'NOTION_API_KEY': 'test_notion_key',
        'NOTION_DATABASE_ID': 'test_database_id',
        'SECRET_KEY': 'test_secret_key',
        'FLASK_ENV': 'testing',
        'DEBUG': 'False'
    }
    
    # 設置環境變數
    original_env = {}
    for key, value in test_env.items():
        original_env[key] = os.environ.get(key)
        os.environ[key] = value
    
    yield
    
    # 恢復原始環境變數
    for key, value in original_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value