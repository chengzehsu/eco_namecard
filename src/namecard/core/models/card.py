from typing import Optional, List
from pydantic import BaseModel, Field, validator
from datetime import datetime
import re


class BusinessCard(BaseModel):
    """名片資料模型"""
    
    name: Optional[str] = Field(None, description="姓名")
    company: Optional[str] = Field(None, description="公司名稱")
    title: Optional[str] = Field(None, description="職稱")
    phone: Optional[str] = Field(None, description="電話號碼")
    email: Optional[str] = Field(None, description="電子郵件")
    address: Optional[str] = Field(None, description="地址")
    website: Optional[str] = Field(None, description="網站")
    fax: Optional[str] = Field(None, description="傳真")
    line_id: Optional[str] = Field(None, description="LINE ID")
    
    # AI 分析相關
    confidence_score: float = Field(0.0, description="識別信心度", ge=0.0, le=1.0)
    quality_score: float = Field(0.0, description="資料品質分數", ge=0.0, le=1.0)
    extracted_at: datetime = Field(default_factory=datetime.now, description="提取時間")
    
    # 用戶相關
    line_user_id: str = Field(..., description="LINE 用戶 ID")
    processed: bool = Field(False, description="是否已處理")
    
    @validator('email')
    def validate_email(cls, v):
        if v and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
            return None  # 無效 email 設為 None
        return v
    
    @validator('phone')
    def validate_phone(cls, v):
        if v:
            # 移除所有非數字字符
            phone_digits = re.sub(r'[^\d]', '', v)
            if len(phone_digits) < 8 or len(phone_digits) > 15:
                return None
        return v
    
    @validator('address')
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