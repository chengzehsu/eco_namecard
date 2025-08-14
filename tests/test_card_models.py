"""名片模型測試"""

import pytest
from datetime import datetime
from src.namecard.core.models.card import BusinessCard, BatchProcessResult, ProcessingStatus


class TestBusinessCard:
    """名片模型測試"""
    
    def test_create_valid_card(self):
        """測試建立有效名片"""
        card = BusinessCard(
            name="張三",
            company="測試公司",
            title="工程師",
            phone="02-1234-5678",
            email="test@example.com",
            address="台北市信義區",
            confidence_score=0.9,
            quality_score=0.8,
            line_user_id="user123"
        )
        
        assert card.name == "張三"
        assert card.company == "測試公司"
        assert card.confidence_score == 0.9
        assert card.line_user_id == "user123"
        assert not card.processed
    
    def test_email_validation(self):
        """測試 email 驗證"""
        # 有效 email
        card = BusinessCard(
            name="測試",
            email="valid@example.com",
            line_user_id="user123"
        )
        assert card.email == "valid@example.com"
        
        # 無效 email 應該被設為 None
        card = BusinessCard(
            name="測試",
            email="invalid-email",
            line_user_id="user123"
        )
        assert card.email is None
    
    def test_phone_validation(self):
        """測試電話號碼驗證"""
        # 有效電話
        card = BusinessCard(
            name="測試",
            phone="02-1234-5678",
            line_user_id="user123"
        )
        assert card.phone == "02-1234-5678"
        
        # 過短電話應該被設為 None
        card = BusinessCard(
            name="測試",
            phone="123",
            line_user_id="user123"
        )
        assert card.phone is None
    
    def test_address_normalization(self):
        """測試地址正規化"""
        card = BusinessCard(
            name="測試",
            address="台北信義區信義路",
            line_user_id="user123"
        )
        assert card.address == "台北市信義區信義路"
        
        card = BusinessCard(
            name="測試",
            address="新北中和區中山路",
            line_user_id="user123"
        )
        assert card.address == "新北市中和區中山路"
    
    def test_confidence_score_range(self):
        """測試信心度分數範圍"""
        with pytest.raises(ValueError):
            BusinessCard(
                name="測試",
                confidence_score=1.5,  # 超出範圍
                line_user_id="user123"
            )
        
        with pytest.raises(ValueError):
            BusinessCard(
                name="測試",
                confidence_score=-0.1,  # 低於範圍
                line_user_id="user123"
            )


class TestBatchProcessResult:
    """批次處理結果測試"""
    
    def test_create_batch_result(self):
        """測試建立批次結果"""
        batch = BatchProcessResult(
            user_id="user123",
            started_at=datetime.now()
        )
        
        assert batch.user_id == "user123"
        assert batch.total_cards == 0
        assert batch.successful_cards == 0
        assert batch.failed_cards == 0
        assert batch.success_rate == 0.0
    
    def test_success_rate_calculation(self):
        """測試成功率計算"""
        batch = BatchProcessResult(
            user_id="user123",
            total_cards=10,
            successful_cards=8,
            failed_cards=2,
            started_at=datetime.now()
        )
        
        assert batch.success_rate == 0.8


class TestProcessingStatus:
    """處理狀態測試"""
    
    def test_create_processing_status(self):
        """測試建立處理狀態"""
        status = ProcessingStatus(user_id="user123")
        
        assert status.user_id == "user123"
        assert not status.is_batch_mode
        assert status.current_batch is None
        assert status.daily_usage == 0
    
    def test_batch_mode_toggle(self):
        """測試批次模式切換"""
        status = ProcessingStatus(user_id="user123")
        
        # 開始批次
        batch = BatchProcessResult(
            user_id="user123",
            started_at=datetime.now()
        )
        status.is_batch_mode = True
        status.current_batch = batch
        
        assert status.is_batch_mode
        assert status.current_batch is not None