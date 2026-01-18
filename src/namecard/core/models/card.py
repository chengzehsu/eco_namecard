from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
import re

# 導入電話正規化工具
try:
    from src.namecard.core.utils.phone_utils import normalize_phone, is_valid_phone
    PHONE_UTILS_AVAILABLE = True
except ImportError:
    PHONE_UTILS_AVAILABLE = False


class BusinessCard(BaseModel):
    """名片資料模型"""
    
    name: Optional[str] = Field(None, description="姓名")
    company: Optional[str] = Field(None, description="公司名稱")
    title: Optional[str] = Field(None, description="職稱")
    department: Optional[str] = Field(None, description="部門")
    phone: Optional[str] = Field(None, description="電話號碼（正規化後）")
    phone_raw: Optional[str] = Field(None, description="原始電話號碼")
    mobile: Optional[str] = Field(None, description="手機號碼（正規化後）")
    mobile_raw: Optional[str] = Field(None, description="原始手機號碼")
    email: Optional[str] = Field(None, description="電子郵件")
    address: Optional[str] = Field(None, description="地址")
    website: Optional[str] = Field(None, description="網站")
    fax: Optional[str] = Field(None, description="傳真")
    line_id: Optional[str] = Field(None, description="LINE ID")
    
    # AI 分析相關
    confidence_score: float = Field(0.0, description="識別信心度", ge=0.0, le=1.0)
    quality_score: float = Field(0.0, description="資料品質分數", ge=0.0, le=1.0)
    extracted_at: datetime = Field(default_factory=datetime.now, description="提取時間")
    
    # 圖片相關
    image_url: Optional[str] = Field(None, description="名片圖片 URL")

    # 用戶相關
    line_user_id: str = Field(..., description="LINE 用戶 ID")
    processed: bool = Field(False, description="是否已處理")
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if v and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
            return None  # 無效 email 設為 None
        return v
    
    @field_validator('phone', 'mobile', mode='before')
    @classmethod
    def normalize_phone_number(cls, v):
        """正規化電話號碼為國際格式"""
        if not v:
            return None
        
        if PHONE_UTILS_AVAILABLE:
            # 使用進階正規化
            normalized = normalize_phone(v, default_region="TW", format_type="e164")
            return normalized if normalized else v
        else:
            # 基本正規化
            return cls._basic_phone_normalize(v)
    
    @field_validator('fax', mode='before')
    @classmethod
    def normalize_fax_number(cls, v):
        """正規化傳真號碼"""
        if not v:
            return None
        
        if PHONE_UTILS_AVAILABLE:
            normalized = normalize_phone(v, default_region="TW", format_type="e164")
            return normalized if normalized else v
        else:
            return cls._basic_phone_normalize(v)
    
    @staticmethod
    def _basic_phone_normalize(phone: str) -> Optional[str]:
        """基本電話正規化（不依賴 phonenumbers）"""
        if not phone:
            return None
        
        # 移除所有非數字和 + 號
        cleaned = re.sub(r'[^\d+]', '', phone)
        
        if not cleaned:
            return None
        
        # 長度檢查
        digits_only = re.sub(r'[^\d]', '', cleaned)
        if len(digits_only) < 8 or len(digits_only) > 15:
            return None
        
        # 處理台灣手機號碼
        if cleaned.startswith('09') and len(digits_only) == 10:
            return f"+886{cleaned[1:]}"
        
        # 處理 886 開頭
        if cleaned.startswith('886') and not cleaned.startswith('+'):
            return f"+{cleaned}"
        
        # 處理台灣市話
        if re.match(r'^0[2-8]', cleaned) and 9 <= len(digits_only) <= 10:
            return f"+886{cleaned[1:]}"
        
        # 如果已經是 + 開頭，保持不變
        if cleaned.startswith('+'):
            return cleaned
        
        return cleaned

    @field_validator('name')
    @classmethod
    def clean_name(cls, v):
        """清理名字中的多餘空白（特別是中文名字）"""
        if v:
            v = v.strip()
            # 移除中文字元之間的空白
            v = re.sub(r'(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])', '', v)
            # 移除多重空白（保留英文名字的單一空白）
            v = re.sub(r'\s+', ' ', v)
        return v

    @field_validator('address')
    @classmethod
    def normalize_address(cls, v):
        if v:
            # 台灣地址正規化
            address_mapping = {
                '台北': '台北市',
                '新北': '新北市',
                '桃園': '桃園市',
                '台中': '台中市',
                '台南': '台南市',
                '高雄': '高雄市',
            }
            for old, new in address_mapping.items():
                if v.startswith(old) and not v.startswith(new):
                    v = v.replace(old, new, 1)
        return v


class BatchProcessResult(BaseModel):
    """批次處理結果"""
    
    user_id: str
    total_cards: int = 0
    successful_cards: int = 0
    failed_cards: int = 0
    cards: List[BusinessCard] = []
    started_at: datetime
    completed_at: Optional[datetime] = None
    errors: List[str] = []
    
    @property
    def success_rate(self) -> float:
        if self.total_cards == 0:
            return 0.0
        return self.successful_cards / self.total_cards


class ProcessingStatus(BaseModel):
    """處理狀態"""
    
    user_id: str
    is_batch_mode: bool = False
    current_batch: Optional[BatchProcessResult] = None
    last_activity: datetime = Field(default_factory=datetime.now)
    daily_usage: int = 0
    usage_reset_date: datetime = Field(default_factory=lambda: datetime.now().replace(hour=0, minute=0, second=0, microsecond=0))