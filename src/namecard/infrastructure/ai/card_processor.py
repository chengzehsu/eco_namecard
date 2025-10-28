import google.generativeai as genai
from PIL import Image
import io
import json
import structlog
from typing import List, Optional, Dict, Any, Tuple
import base64
import sys
import os
import time
from dataclasses import dataclass
from contextlib import contextmanager
from functools import wraps
import traceback

# 添加項目根目錄到 Python 路徑
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../..'))

from simple_config import settings
from src.namecard.core.models.card import BusinessCard

logger = structlog.get_logger()


@dataclass
class ProcessingConfig:
    """處理配置類別"""
    max_image_size: Tuple[int, int] = (1920, 1920)
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    min_confidence_threshold: float = 0.2  # 降低閾值提高識別率
    min_quality_threshold: float = 0.15   # 降低闾值提高識別率
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout_seconds: int = 30
    

class ProcessingError(Exception):
    """處理錯誤基類"""
    pass


class APIError(ProcessingError):
    """API 錯誤"""
    pass


class ValidationError(ProcessingError):
    """驗證錯誤"""
    pass


class ImageProcessingError(ProcessingError):
    """圖片處理錯誤"""
    pass


def with_error_handling(func):
    """錯誤處理裝飾器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(
                f"Error in {func.__name__}",
                error=str(e),
                traceback=traceback.format_exc()
            )
            raise
    return wrapper


def with_timing(func):
    """執行時間監控裝飾器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(
                f"{func.__name__} completed",
                execution_time=f"{execution_time:.2f}s"
            )
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"{func.__name__} failed",
                execution_time=f"{execution_time:.2f}s",
                error=str(e)
            )
            raise
    return wrapper


class CardProcessor:
    """Google Gemini AI 名片處理器
    
    提供高效的名片 OCR 識別功能，支援多卡片檢測、品質評估和錯誤恢復。
    使用 Google Gemini AI 進行圖像理解和文字擷取。
    """
    
    def __init__(self, config: Optional[ProcessingConfig] = None) -> None:
        """
        初始化處理器
        
        Args:
            config: 處理配置，預設使用預設配置
        """
        self.config = config or ProcessingConfig()
        self.model = None
        self.fallback_model = None
        self._api_call_count = 0
        self._last_api_call = 0
        self._setup_gemini()
        
        logger.info(
            "CardProcessor initialized",
            config={
                "max_image_size": self.config.max_image_size,
                "min_confidence_threshold": self.config.min_confidence_threshold,
                "max_retries": self.config.max_retries
            }
        )
        
        # 名片識別 prompt 優化版 - 強化電話識別
        self.card_prompt = """
你是一個高精度的名片 OCR 識別系統。請仔細分析這張圖片並提取所有名片資訊。

⚠️ 【最重要】電話號碼是名片的核心資訊，必須優先且仔細識別！

═══════════════════════════════════════════════════
【電話號碼識別指南 - 最高優先級】
═══════════════════════════════════════════════════

步驟 1：掃描所有數字串
- 尋找 8-12 位數字的組合
- 可能包含：空格、括號 ()、破折號 -、加號 +

步驟 2：識別電話標籤（但標籤不是必須的）
常見標籤：Tel, TEL, 電話, Phone, Mobile, 行動, 手機, Cell, M

步驟 3：識別常見台灣電話格式
市話格式（必須識別）：
  ✓ (02) 2345-6789
  ✓ 02-2345-6789
  ✓ 02 2345 6789
  ✓ (02)2345-6789
  ✓ 022345-6789

手機格式（必須識別）：
  ✓ 0912-345-678
  ✓ 0912 345 678
  ✓ 0912345678
  ✓ 09XX-XXX-XXX

國際格式：
  ✓ +886-2-2345-6789
  ✓ +886 2 2345 6789
  ✓ +886 912 345 678

含分機：
  ✓ (02) 2345-6789 ext.123
  ✓ 02-2345-6789 #123

步驟 4：區分電話和傳真
- **只有**明確標示「Fax」、「傳真」、「F:」的才是傳真 → 放入 fax 欄位
- 所有其他電話號碼 → 放入 phone 欄位

步驟 5：處理多個電話號碼
優先順序：手機 (09開頭) > 市話 (02,03,04等) > 其他
選擇最主要的一個放入 phone 欄位

步驟 6：保留原始格式
保留括號、破折號、空格等分隔符，保持原始格式

⛔ 常見錯誤警告：
❌ 不要忽略沒有「Tel」或「電話」標籤的數字串
❌ 不要把郵遞區號（3-5位數）當作電話
❌ 不要把統一編號（8位數）當作電話
❌ 不要遺漏 09 開頭的手機號碼
❌ 不要把所有電話都當作傳真

═══════════════════════════════════════════════════

分析指南：
1. **最優先**：按照上述指南識別電話號碼
2. 系統性掃描整張圖片，識別所有可能的名片區域
3. 提取以下資訊：
   - 個人姓名（中文或英文）
   - 公司/組織名稱
   - 職稱/部門
   - 電子郵件地址
   - 通訊地址（完整地址）
   - 網站/網址
   - LINE ID 或其他社交媒體 ID
   - QR Code 或條碼資訊（如果有）

職稱和部門識別規則：
- **中文優先原則**：如果名片上同時有中文和英文職稱/部門，必須優先使用中文
- 職稱欄位不可包含逗號(,)、斜線(/)、破折號等分隔符號
- 如果職稱有多語言版本（例如：工務協理 Director, EPC BU），只保留中文部分（工務協理）
- 部門同樣遵循中文優先原則
- 範例：「工務協理 Director」→ 只填入「工務協理」
- 範例：「業務部 Sales Department」→ 只填入「業務部」

品質評估標準：
   - confidence_score (0.0-1.0)：基於文字清晰度、版面設計和資訊完整性
   - quality_score (0.0-1.0)：基於圖片解析度、光線條件和可讀性

回傳格式（只返回 JSON，無需其他文字）：
{
  "cards": [
    {
      "name": "姓名",
      "company": "公司名稱",
      "title": "工務協理",
      "department": "業務部",
      "phone": "02-2345-6789",  // ⚠️ 核心欄位！必須優先識別，不可為空
      "email": "電子郵件",
      "address": "完整地址",
      "website": "網站",
      "fax": "02-2345-6788",  // 僅當有「傳真」或「Fax」標示時才填入
      "line_id": "LINE ID",
      "confidence_score": 0.95,
      "quality_score": 0.9
    }
  ],
  "total_cards_detected": 1,
  "overall_quality": 0.9,
  "processing_notes": "詳細說明識別結果，特別註明電話號碼的識別過程"
}

重要規則：
⚠️ **電話號碼是最重要的欄位**：
- 電話號碼必須優先且仔細識別
- 寬鬆識別原則：寧可多識別也不要漏掉
- 保留電話原始格式（包括括號、破折號、空格等分隔符）
- 正確區分：只有標示「傳真」「Fax」的才放 fax 欄位，其他放 phone 欄位
- 即使沒有「Tel」標籤，看到符合電話格式的數字串也要識別

其他規則：
- 職稱和部門必須是純中文（如果有中文的話），不含英文、逗號或其他分隔符號
- 地址必須完整（郵遞區號 + 縣市 + 區域 + 詳細地址）
- Email 必須包含 @ 和域名
- 無資訊欄位設為 null
- confidence_score 考量文字清晰度和資訊完整性
- quality_score 考量圖片品質和排版設計
- processing_notes 必須詳細說明電話號碼的識別過程和任何問題
- 絕對只返回 JSON 格式，不要任何額外文字或說明

🎯 最終提醒：
電話是名片最核心的資訊，務必全力識別！
如果名片上有任何看起來像電話號碼的數字串，都必須嘗試識別並放入 phone 欄位。
"""
    
    def _setup_gemini(self) -> None:
        """設置 Gemini API 並初始化模型
        
        Raises:
            APIError: 當主要和備用 API 金鑰都失敗時
        """
        api_keys = [settings.google_api_key]
        if settings.google_api_key_fallback:
            api_keys.append(settings.google_api_key_fallback)
        
        for i, api_key in enumerate(api_keys):
            if not api_key:
                continue
                
            try:
                genai.configure(api_key=api_key)

                # 主要模型：gemini-2.5-flash（速度快，成本低）
                self.model = genai.GenerativeModel('gemini-2.5-flash')

                # Fallback 模型：gemini-2.0-flash（當 2.5 被安全過濾器阻擋時使用）
                self.fallback_model = genai.GenerativeModel('gemini-2.0-flash')

                # 測試 API 連接
                _ = self.model.generate_content("test")

                key_type = "primary" if i == 0 else "fallback"
                logger.info(f"Gemini API configured successfully using {key_type} key")

                # 記錄成功的 API 配置
                logger.info(
                    "Gemini API configured successfully",
                    key_type=key_type,
                    api_index=i,
                    primary_model="gemini-2.5-flash",
                    fallback_model="gemini-2.0-flash",
                    operation="api_setup",
                    status="success"
                )
                return
                
            except Exception as e:
                key_type = "primary" if i == 0 else "fallback"
                logger.warning(f"Failed to configure {key_type} Gemini API", error=str(e))
                
                # 記錄 API 配置失敗
                logger.warning(
                    f"Failed to configure {key_type} Gemini API",
                    key_type=key_type,
                    error=str(e),
                    api_index=i,
                    operation="api_setup",
                    status="failed"
                )
                continue
        
        raise APIError("All Gemini API keys failed to initialize")
    
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
            # 記錄處理開始
            logger.info(
                "Starting card processing",
                image_size=len(image_data),
                user_id=user_id,
                operation="ai_processing"
            )
            
            # 轉換圖片格式
            image = Image.open(io.BytesIO(image_data))
            
            # 圖片預處理
            image = self._preprocess_image(image)
            
            # 使用 Gemini 分析
            response = self._analyze_with_gemini(image)
            
            # 解析結果
            cards = self._parse_response(response, user_id)
            
            # 記錄成功事件和業務指標
            logger.info(
                "Card processing completed successfully",
                user_id=user_id,
                cards_count=len(cards),
                image_size=len(image_data),
                api_calls=self._api_call_count,
                success_rate=len(cards) > 0,
                operation="card_processing",
                status="success"
            )
            
            # 檢查識別品質並發出警告
            low_confidence_cards = [c for c in cards if c.confidence_score < 0.5]
            if low_confidence_cards:
                logger.warning(
                    "Low confidence cards detected",
                    user_id=user_id,
                    low_confidence_count=len(low_confidence_cards),
                    total_cards=len(cards),
                    avg_confidence=sum(c.confidence_score for c in cards) / len(cards) if cards else 0,
                    operation="quality_check",
                    issue="low_confidence"
                )
            
            logger.info("Card processing completed", 
                       user_id=user_id, 
                       cards_count=len(cards))
            
            return cards
            
        except Exception as e:
            # 記錄異常詳情
            logger.error(
                "Card processing failed with exception",
                user_id=user_id,
                error=str(e),
                error_type=type(e).__name__,
                image_size=len(image_data),
                api_call_count=self._api_call_count,
                operation="card_processing",
                traceback=traceback.format_exc()
            )
            
            logger.error("Card processing failed", 
                        user_id=user_id, 
                        error=str(e))
            return []
    
    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """圖片預處理和優化
        
        Args:
            image: 原始圖片物件
            
        Returns:
            優化後的圖片物件
            
        Raises:
            ImageProcessingError: 當圖片處理失敗時
        """
        try:
            original_size = image.size
            
            # 轉換為 RGB 格式
            if image.mode not in ('RGB', 'L'):
                image = image.convert('RGB')
                logger.debug("Image converted to RGB")
            
            # 智能尺寸調整
            max_size = self.config.max_image_size
            if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
                # 計算縮放比例，保持長寬比
                ratio = min(max_size[0] / image.size[0], max_size[1] / image.size[1])
                new_size = (
                    int(image.size[0] * ratio),
                    int(image.size[1] * ratio)
                )
                
                image = image.resize(new_size, Image.Resampling.LANCZOS)
                
                logger.info(
                    "Image resized for optimization",
                    original_size=original_size,
                    new_size=new_size,
                    compression_ratio=f"{ratio:.2f}"
                )
            
            # 簡單的品質評估
            if image.size[0] < 300 or image.size[1] < 300:
                logger.warning(
                    "Image resolution may be too low for optimal OCR",
                    size=image.size
                )
            
            return image
            
        except Exception as e:
            logger.error("Image preprocessing failed", error=str(e))
            raise ImageProcessingError(f"Failed to preprocess image: {str(e)}")
    
    @with_timing
    @with_error_handling
    def _analyze_with_gemini(self, image: Image.Image) -> str:
        """使用 Gemini 分析圖片
        
        Args:
            image: 預處理後的圖片物件
            
        Returns:
            Gemini 回應的 JSON 字串
            
        Raises:
            APIError: 當 API 呼叫失敗時
        """
        if not self.model:
            raise APIError("Gemini model not initialized")
        
        # 記錄 API 呼叫
        self._api_call_count += 1
        self._last_api_call = time.time()
        
        # 實施簡單的 rate limiting
        time_since_last_call = time.time() - self._last_api_call
        if time_since_last_call < 0.1:  # 限制每秒最多 10 次請求
            time.sleep(0.1 - time_since_last_call)
        
        try:
            logger.debug(
                "Calling Gemini API",
                api_call_count=self._api_call_count,
                model="gemini-2.5-flash",
                operation="ai_processing"
            )

            # 配置安全設定：名片是專業文件，需要寬鬆的安全過濾設定
            safety_settings = [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_NONE"
                }
            ]

            # 生成內容
            response = self.model.generate_content(
                [self.card_prompt, image],
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,  # 低溫度確保一致性
                    max_output_tokens=2048,
                    response_mime_type="application/json"
                ),
                safety_settings=safety_settings
            )

            # 檢查 finish_reason
            if response.candidates and response.candidates[0].finish_reason == 2:
                # 記錄詳細的安全過濾資訊
                safety_ratings = response.candidates[0].safety_ratings if hasattr(response.candidates[0], 'safety_ratings') else []
                logger.warning(
                    "Gemini 2.5-flash blocked by safety filter, triggering fallback to 2.0-flash",
                    api_call_count=self._api_call_count,
                    finish_reason=response.candidates[0].finish_reason,
                    safety_ratings=[{
                        "category": rating.category,
                        "probability": rating.probability
                    } for rating in safety_ratings] if safety_ratings else "unavailable",
                    operation="fallback_trigger"
                )

                # 使用 fallback 模型重試
                if self.fallback_model:
                    try:
                        logger.info(
                            "Retrying with fallback model gemini-2.0-flash",
                            api_call_count=self._api_call_count,
                            operation="fallback_retry"
                        )

                        fallback_response = self.fallback_model.generate_content(
                            [self.card_prompt, image],
                            generation_config=genai.types.GenerationConfig(
                                temperature=0.1,
                                max_output_tokens=2048,
                                response_mime_type="application/json"
                            ),
                            safety_settings=safety_settings
                        )

                        if not fallback_response.text:
                            raise APIError("Fallback model returned empty response")

                        logger.info(
                            "Fallback model succeeded",
                            api_call_count=self._api_call_count,
                            model="gemini-2.0-flash",
                            response_length=len(fallback_response.text),
                            operation="fallback_success"
                        )

                        return fallback_response.text.strip()

                    except Exception as fallback_error:
                        logger.error(
                            "Fallback model also failed",
                            api_call_count=self._api_call_count,
                            error=str(fallback_error),
                            operation="fallback_failure"
                        )
                        raise APIError(f"兩個模型都無法處理此圖片：{str(fallback_error)}")
                else:
                    raise APIError("圖片處理被阻擋且無 fallback 模型可用")

            if not response.text:
                # 記錄空回應錯誤
                logger.error(
                    "Empty response from Gemini API",
                    api_call_count=self._api_call_count,
                    operation="gemini_api",
                    error_type="empty_response"
                )
                raise APIError("Empty response from Gemini")
            
            # 記錄成功的 API 調用
            logger.info(
                "Gemini API call successful",
                api_call_count=self._api_call_count,
                response_length=len(response.text),
                response_preview=response.text[:100] + "..." if len(response.text) > 100 else response.text,
                operation="gemini_api",
                status="success"
            )
            
            logger.info(
                "Gemini analysis completed",
                api_call_count=self._api_call_count,
                response_length=len(response.text)
            )
            
            return response.text.strip()
            
        except Exception as e:
            # 記錄 API 調用失敗
            logger.error(
                "Gemini API call failed",
                error=str(e),
                error_type=type(e).__name__,
                api_call_count=self._api_call_count,
                operation="gemini_api",
                error_category="api_failure"
            )
            
            logger.error(
                "Gemini analysis failed",
                error=str(e),
                api_call_count=self._api_call_count
            )
            raise APIError(f"Gemini API call failed: {str(e)}")
    
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
                        department=card_data.get('department'),
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
                                   title=card.title,
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
        """驗證名片品質和完整性
        
        Args:
            card: 待驗證的名片物件
            
        Returns:
            是否通過品質檢查
        """
        # 信心度閾值檢查
        if card.confidence_score < self.config.min_confidence_threshold:
            logger.debug(
                "Card rejected due to low confidence",
                confidence=card.confidence_score,
                threshold=self.config.min_confidence_threshold
            )
            return False
        
        # 品質分數檢查
        if card.quality_score < self.config.min_quality_threshold:
            logger.debug(
                "Card rejected due to low quality",
                quality=card.quality_score,
                threshold=self.config.min_quality_threshold
            )
            return False
        
        # 核心資訊檢查：至少要有姓名或公司名稱
        if not (card.name and card.name.strip()) and not (card.company and card.company.strip()):
            logger.debug("Card rejected due to missing name and company")
            return False
        
        # 聯絡方式檢查：至少要有一種有效的聯絡方式
        contact_methods = [
            card.phone and card.phone.strip(),
            card.email and card.email.strip() and '@' in card.email,
            card.address and card.address.strip()
        ]
        
        if not any(contact_methods):
            logger.debug("Card rejected due to missing valid contact information")
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