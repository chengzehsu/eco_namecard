"""AI 名片處理器測試"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from PIL import Image
import io
import json
from src.namecard.infrastructure.ai.card_processor import CardProcessor
from src.namecard.core.models.card import BusinessCard


class TestCardProcessor:
    """CardProcessor 測試"""
    
    def setup_method(self):
        """每個測試方法前的設置"""
        self.processor = CardProcessor()
        self.test_user_id = "test_user_123"
    
    def create_test_image(self) -> bytes:
        """建立測試圖片"""
        image = Image.new('RGB', (100, 100), color='white')
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        return img_byte_arr.getvalue()
    
    @patch('src.namecard.infrastructure.ai.card_processor.genai')
    def test_setup_gemini_success(self, mock_genai):
        """測試 Gemini API 設置成功"""
        mock_genai.configure.return_value = None
        
        processor = CardProcessor()
        mock_genai.configure.assert_called_once()
    
    @patch('src.namecard.infrastructure.ai.card_processor.genai')
    def test_setup_gemini_fallback(self, mock_genai):
        """測試 Gemini API 使用備用金鑰"""
        # 主要金鑰失敗，備用金鑰成功
        mock_genai.configure.side_effect = [Exception("API Error"), None]
        
        with patch('src.namecard.infrastructure.ai.card_processor.settings') as mock_settings:
            mock_settings.google_api_key = "primary_key"
            mock_settings.google_api_key_fallback = "fallback_key"
            
            processor = CardProcessor()
            assert mock_genai.configure.call_count == 2
    
    def test_preprocess_image_rgb_conversion(self):
        """測試圖片格式轉換"""
        # 建立 RGBA 圖片
        image = Image.new('RGBA', (100, 100), color='white')
        
        processed = self.processor._preprocess_image(image)
        
        assert processed.mode == 'RGB'
        assert processed.size == (100, 100)
    
    def test_preprocess_image_resize(self):
        """測試圖片尺寸限制"""
        # 建立超大圖片
        large_image = Image.new('RGB', (3000, 3000), color='white')
        
        processed = self.processor._preprocess_image(large_image)
        
        # 應該被縮小到最大尺寸
        assert processed.size[0] <= 1920
        assert processed.size[1] <= 1920
    
    @patch.object(CardProcessor, '_analyze_with_gemini')
    @patch.object(CardProcessor, '_preprocess_image')
    def test_process_image_success(self, mock_preprocess, mock_analyze):
        """測試成功處理圖片"""
        # 設置 mock 回傳值
        mock_preprocess.return_value = Image.new('RGB', (100, 100))
        mock_analyze.return_value = json.dumps({
            "cards": [{
                "name": "張三",
                "company": "測試公司",
                "phone": "02-1234-5678",
                "email": "test@example.com",
                "confidence_score": 0.9,
                "quality_score": 0.8
            }],
            "total_cards_detected": 1,
            "overall_quality": 0.8
        })
        
        image_data = self.create_test_image()
        cards = self.processor.process_image(image_data, self.test_user_id)
        
        assert len(cards) == 1
        assert cards[0].name == "張三"
        assert cards[0].company == "測試公司"
        assert cards[0].line_user_id == self.test_user_id
    
    @patch.object(CardProcessor, '_analyze_with_gemini')
    def test_parse_response_valid_json(self, mock_analyze):
        """測試解析有效 JSON 回應"""
        response_text = json.dumps({
            "cards": [{
                "name": "測試名片",
                "company": "測試公司",
                "confidence_score": 0.95,
                "quality_score": 0.9
            }]
        })
        
        cards = self.processor._parse_response(response_text, self.test_user_id)
        
        assert len(cards) == 1
        assert cards[0].name == "測試名片"
    
    def test_parse_response_invalid_json(self):
        """測試解析無效 JSON 回應"""
        invalid_json = "這不是有效的 JSON"
        
        cards = self.processor._parse_response(invalid_json, self.test_user_id)
        
        assert len(cards) == 0
    
    def test_parse_response_with_markdown(self):
        """測試解析帶有 markdown 標記的回應"""
        response_with_markdown = """```json
        {
            "cards": [{
                "name": "Markdown 測試",
                "confidence_score": 0.8,
                "quality_score": 0.7
            }]
        }
        ```"""
        
        cards = self.processor._parse_response(response_with_markdown, self.test_user_id)
        
        assert len(cards) == 1
        assert cards[0].name == "Markdown 測試"
    
    def test_validate_card_quality_high_confidence(self):
        """測試高信心度名片品質驗證"""
        card = BusinessCard(
            name="高品質名片",
            company="優質公司",
            phone="02-1234-5678",
            confidence_score=0.9,
            line_user_id=self.test_user_id
        )
        
        is_valid = self.processor._validate_card_quality(card)
        assert is_valid
    
    def test_validate_card_quality_low_confidence(self):
        """測試低信心度名片品質驗證"""
        card = BusinessCard(
            name="低品質名片",
            confidence_score=0.2,  # 低於門檻
            line_user_id=self.test_user_id
        )
        
        is_valid = self.processor._validate_card_quality(card)
        assert not is_valid
    
    def test_validate_card_quality_missing_essential_info(self):
        """測試缺少必要資訊的名片"""
        card = BusinessCard(
            confidence_score=0.9,  # 高信心度但缺少姓名和公司
            line_user_id=self.test_user_id
        )
        
        is_valid = self.processor._validate_card_quality(card)
        assert not is_valid
    
    def test_validate_card_quality_no_contact_info(self):
        """測試缺少聯絡資訊的名片"""
        card = BusinessCard(
            name="測試名片",
            company="測試公司",
            confidence_score=0.9,
            line_user_id=self.test_user_id
            # 缺少 phone, email, address
        )
        
        is_valid = self.processor._validate_card_quality(card)
        assert not is_valid
    
    def test_get_processing_suggestions_no_cards(self):
        """測試無名片時的建議"""
        suggestions = self.processor.get_processing_suggestions([])
        
        assert len(suggestions) > 0
        assert any("確認圖片包含清晰的名片" in s for s in suggestions)
    
    def test_get_processing_suggestions_low_confidence(self):
        """測試低信心度名片的建議"""
        low_confidence_card = BusinessCard(
            name="測試",
            company="測試",
            phone="123456789",
            confidence_score=0.5,  # 低信心度
            line_user_id=self.test_user_id
        )
        
        suggestions = self.processor.get_processing_suggestions([low_confidence_card])
        
        assert any("信心度較低" in s for s in suggestions)
    
    def test_get_processing_suggestions_multiple_cards(self):
        """測試多張名片的建議"""
        cards = [
            BusinessCard(name="卡片1", company="公司1", phone="123", 
                        confidence_score=0.9, line_user_id=self.test_user_id),
            BusinessCard(name="卡片2", company="公司2", phone="456", 
                        confidence_score=0.8, line_user_id=self.test_user_id)
        ]
        
        suggestions = self.processor.get_processing_suggestions(cards)
        
        assert any("檢測到 2 張名片" in s for s in suggestions)
    
    @patch.object(CardProcessor, 'model')
    def test_analyze_with_gemini_success(self, mock_model):
        """測試 Gemini 分析成功"""
        mock_response = Mock()
        mock_response.text = json.dumps({"cards": []})
        mock_model.generate_content.return_value = mock_response
        
        image = Image.new('RGB', (100, 100))
        result = self.processor._analyze_with_gemini(image)
        
        assert result == json.dumps({"cards": []})
        mock_model.generate_content.assert_called_once()
    
    @patch.object(CardProcessor, 'model')
    @patch('src.namecard.infrastructure.ai.card_processor.genai')
    def test_analyze_with_gemini_fallback(self, mock_genai, mock_model):
        """測試 Gemini 分析備用 API"""
        # 第一次調用失敗，第二次成功
        mock_model.generate_content.side_effect = [
            Exception("API Error"),
            Mock(text=json.dumps({"cards": []}))
        ]
        
        with patch('src.namecard.infrastructure.ai.card_processor.settings') as mock_settings:
            mock_settings.google_api_key_fallback = "fallback_key"
            
            image = Image.new('RGB', (100, 100))
            result = self.processor._analyze_with_gemini(image)
            
            # 應該調用備用 API
            mock_genai.configure.assert_called_with(api_key="fallback_key")
    
    @patch.object(CardProcessor, '_analyze_with_gemini')
    def test_process_image_exception_handling(self, mock_analyze):
        """測試圖片處理異常處理"""
        mock_analyze.side_effect = Exception("處理失敗")
        
        image_data = self.create_test_image()
        cards = self.processor.process_image(image_data, self.test_user_id)
        
        assert len(cards) == 0  # 異常時應該返回空列表