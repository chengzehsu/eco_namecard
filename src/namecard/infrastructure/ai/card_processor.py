import google.generativeai as genai
from PIL import Image
import io
import json
import structlog
from typing import List, Optional
import base64
import sys
import os

# 添加項目根目錄到 Python 路徑
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../..'))

from simple_config import settings
from src.namecard.core.models.card import BusinessCard

logger = structlog.get_logger()


class CardProcessor:
    """Google Gemini AI 名片處理器"""
    
    def __init__(self):
        self._setup_gemini()
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        
        # 名片識別 prompt
        self.card_prompt = """
你是一個專業的名片 OCR 識別系統。請分析這張圖片並提取所有名片資訊。

分析要求：
1. 檢測圖片中所有的名片（可能有多張）
2. 對每張名片提取完整資訊
3. 評估每張名片的識別信心度（0-1）
4. 提供整體品質評分

請以JSON格式回傳，結構如下：
{
  "cards": [
    {
      "name": "姓名",
      "company": "公司名稱", 
      "title": "職稱",
      "phone": "電話號碼",
      "email": "電子郵件",
      "address": "地址",
      "website": "網站",
      "fax": "傳真",
      "line_id": "LINE ID",
      "confidence_score": 0.95,
      "quality_score": 0.9
    }
  ],
  "total_cards_detected": 1,
  "overall_quality": 0.9,
  "processing_notes": "圖片清晰，識別度高"
}

重要規則：
- 如果某個欄位沒有資訊，請設為 null
- 電話號碼保留原始格式
- 地址要完整，包含縣市區
- confidence_score 是對該名片識別準確度的評估
- quality_score 是對該名片圖片品質的評估
- 如果圖片模糊或無法識別名片，請在processing_notes說明
- 只回傳JSON，不要其他文字
"""
    
    def _setup_gemini(self):
        """設置 Gemini API"""
        try:
            genai.configure(api_key=settings.google_api_key)
            logger.info("Gemini API configured successfully")
        except Exception as e:
            logger.error("Failed to configure Gemini API", error=str(e))
            if settings.google_api_key_fallback:
                try:
                    genai.configure(api_key=settings.google_api_key_fallback)
                    logger.info("Using fallback Gemini API key")
                except Exception as e2:
                    logger.error("Fallback API key also failed", error=str(e2))
                    raise
            else:
                raise
    
    def process_image(self, image_data: bytes, user_id: str) -> List[BusinessCard]:
        """
        處理名片圖片
        
        Args:
            image_data: 圖片二進制數據
            user_id: LINE 用戶 ID
            
        Returns:
            識別到的名片列表
        """
        try:
            # 轉換圖片格式
            image = Image.open(io.BytesIO(image_data))
            
            # 圖片預處理
            image = self._preprocess_image(image)
            
            # 使用 Gemini 分析
            response = self._analyze_with_gemini(image)
            
            # 解析結果
            cards = self._parse_response(response, user_id)
            
            logger.info("Card processing completed", 
                       user_id=user_id, 
                       cards_count=len(cards))
            
            return cards
            
        except Exception as e:
            logger.error("Card processing failed", 
                        user_id=user_id, 
                        error=str(e))
            return []
    
    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """圖片預處理"""
        try:
            # 轉換為 RGB 格式
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # 限制圖片大小以節省 API 配額
            max_size = (1920, 1920)
            if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
                image.thumbnail(max_size, Image.Resampling.LANCZOS)
                logger.info("Image resized", original_size=image.size, new_size=image.size)
            
            return image
            
        except Exception as e:
            logger.error("Image preprocessing failed", error=str(e))
            raise
    
    def _analyze_with_gemini(self, image: Image.Image) -> str:
        """使用 Gemini 分析圖片"""
        try:
            # 生成內容
            response = self.model.generate_content([
                self.card_prompt,
                image
            ])
            
            if not response.text:
                raise Exception("Empty response from Gemini")
            
            return response.text.strip()
            
        except Exception as e:
            logger.error("Gemini analysis failed", error=str(e))
            
            # 嘗試使用備用 API Key
            if settings.google_api_key_fallback:
                try:
                    genai.configure(api_key=settings.google_api_key_fallback)
                    response = self.model.generate_content([
                        self.card_prompt,
                        image
                    ])
                    logger.info("Used fallback API key successfully")
                    return response.text.strip()
                except Exception as e2:
                    logger.error("Fallback API also failed", error=str(e2))
            
            raise
    
    def _parse_response(self, response_text: str, user_id: str) -> List[BusinessCard]:
        """解析 Gemini 回應"""
        try:
            # 清理回應文字（移除可能的 markdown 標記）
            response_text = response_text.replace('```json', '').replace('```', '').strip()
            
            # 解析 JSON
            data = json.loads(response_text)
            
            cards = []
            cards_data = data.get('cards', [])
            
            for card_data in cards_data:
                try:
                    # 建立名片物件
                    card = BusinessCard(
                        name=card_data.get('name'),
                        company=card_data.get('company'),
                        title=card_data.get('title'),
                        phone=card_data.get('phone'),
                        email=card_data.get('email'),
                        address=card_data.get('address'),
                        website=card_data.get('website'),
                        fax=card_data.get('fax'),
                        line_id=card_data.get('line_id'),
                        confidence_score=float(card_data.get('confidence_score', 0.0)),
                        quality_score=float(card_data.get('quality_score', 0.0)),
                        line_user_id=user_id
                    )
                    
                    # 品質檢查
                    if self._validate_card_quality(card):
                        cards.append(card)
                        logger.info("Card extracted successfully", 
                                   name=card.name, 
                                   company=card.company,
                                   confidence=card.confidence_score)
                    else:
                        logger.warning("Card quality too low, skipped", 
                                     confidence=card.confidence_score,
                                     quality=card.quality_score)
                
                except Exception as e:
                    logger.error("Failed to create card object", error=str(e))
                    continue
            
            # 記錄整體處理結果
            total_detected = data.get('total_cards_detected', len(cards))
            overall_quality = data.get('overall_quality', 0.0)
            processing_notes = data.get('processing_notes', '')
            
            logger.info("Response parsed successfully",
                       total_detected=total_detected,
                       valid_cards=len(cards),
                       overall_quality=overall_quality,
                       notes=processing_notes)
            
            return cards
            
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON response", 
                        error=str(e), 
                        response=response_text[:500])
            return []
        except Exception as e:
            logger.error("Failed to parse response", error=str(e))
            return []
    
    def _validate_card_quality(self, card: BusinessCard) -> bool:
        """驗證名片品質"""
        # 基本信心度檢查
        if card.confidence_score < 0.3:
            return False
        
        # 至少要有姓名或公司名稱其中一個
        if not card.name and not card.company:
            return False
        
        # 至少要有一個聯絡方式
        if not any([card.phone, card.email, card.address]):
            return False
        
        return True
    
    def get_processing_suggestions(self, cards: List[BusinessCard]) -> List[str]:
        """獲取處理建議"""
        suggestions = []
        
        if not cards:
            suggestions.append("🔍 建議：確認圖片包含清晰的名片")
            suggestions.append("💡 提示：光線充足且名片平整效果更佳")
            return suggestions
        
        low_confidence_cards = [c for c in cards if c.confidence_score < 0.7]
        if low_confidence_cards:
            suggestions.append(f"⚠️ {len(low_confidence_cards)} 張名片信心度較低，建議重新拍攝")
        
        incomplete_cards = [c for c in cards if not all([c.name, c.company, c.phone or c.email])]
        if incomplete_cards:
            suggestions.append(f"📝 {len(incomplete_cards)} 張名片資訊不完整，請檢查原始名片")
        
        if len(cards) > 1:
            suggestions.append(f"🎯 檢測到 {len(cards)} 張名片，已分別處理")
        
        return suggestions