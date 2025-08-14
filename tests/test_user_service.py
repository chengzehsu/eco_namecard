"""用戶服務測試"""

import pytest
from datetime import datetime, timedelta
from src.namecard.core.services.user_service import UserService
from src.namecard.core.models.card import BusinessCard


class TestUserService:
    """用戶服務測試"""
    
    def setup_method(self):
        """每個測試方法前的設置"""
        self.user_service = UserService()
        self.test_user_id = "test_user_123"
    
    def test_get_user_status_new_user(self):
        """測試獲取新用戶狀態"""
        status = self.user_service.get_user_status(self.test_user_id)
        
        assert status.user_id == self.test_user_id
        assert status.daily_usage == 0
        assert not status.is_batch_mode
        assert status.current_batch is None
    
    def test_check_rate_limit(self):
        """測試速率限制檢查"""
        # 新用戶應該通過限制檢查
        assert self.user_service.check_rate_limit(self.test_user_id, 50)
        
        # 模擬達到限制
        status = self.user_service.get_user_status(self.test_user_id)
        status.daily_usage = 50
        
        assert not self.user_service.check_rate_limit(self.test_user_id, 50)
    
    def test_increment_usage(self):
        """測試增加使用次數"""
        initial_usage = self.user_service.get_user_status(self.test_user_id).daily_usage
        
        self.user_service.increment_usage(self.test_user_id)
        
        final_usage = self.user_service.get_user_status(self.test_user_id).daily_usage
        assert final_usage == initial_usage + 1
    
    def test_batch_mode_lifecycle(self):
        """測試批次模式生命週期"""
        # 開始批次模式
        batch_result = self.user_service.start_batch_mode(self.test_user_id)
        
        assert batch_result is not None
        assert batch_result.user_id == self.test_user_id
        assert batch_result.total_cards == 0
        
        status = self.user_service.get_user_status(self.test_user_id)
        assert status.is_batch_mode
        assert status.current_batch is not None
        
        # 結束批次模式
        completed_batch = self.user_service.end_batch_mode(self.test_user_id)
        
        assert completed_batch is not None
        assert completed_batch.completed_at is not None
        
        status = self.user_service.get_user_status(self.test_user_id)
        assert not status.is_batch_mode
        assert status.current_batch is None
    
    def test_add_card_to_batch(self):
        """測試將名片加入批次"""
        # 先開始批次模式
        self.user_service.start_batch_mode(self.test_user_id)
        
        # 建立測試名片
        card = BusinessCard(
            name="測試名片",
            company="測試公司",
            line_user_id=self.test_user_id,
            processed=True
        )
        
        # 加入批次
        success = self.user_service.add_card_to_batch(self.test_user_id, card)
        
        assert success
        
        status = self.user_service.get_user_status(self.test_user_id)
        batch = status.current_batch
        
        assert batch.total_cards == 1
        assert batch.successful_cards == 1
        assert len(batch.cards) == 1
    
    def test_add_card_without_batch_mode(self):
        """測試在非批次模式下加入名片"""
        card = BusinessCard(
            name="測試名片",
            line_user_id=self.test_user_id
        )
        
        # 未開始批次模式，應該失敗
        success = self.user_service.add_card_to_batch(self.test_user_id, card)
        assert not success
    
    def test_get_batch_status(self):
        """測試獲取批次狀態"""
        # 非批次模式應該返回 None
        status_text = self.user_service.get_batch_status(self.test_user_id)
        assert status_text is None
        
        # 開始批次模式
        self.user_service.start_batch_mode(self.test_user_id)
        
        # 應該返回狀態文字
        status_text = self.user_service.get_batch_status(self.test_user_id)
        assert status_text is not None
        assert "批次進度" in status_text
    
    def test_daily_usage_reset(self):
        """測試每日使用量重置"""
        # 設置使用量
        status = self.user_service.get_user_status(self.test_user_id)
        status.daily_usage = 20
        status.usage_reset_date = datetime.now() - timedelta(days=1)  # 昨天
        
        # 重新獲取狀態應該觸發重置
        new_status = self.user_service.get_user_status(self.test_user_id)
        assert new_status.daily_usage == 0
    
    def test_cleanup_inactive_sessions(self):
        """測試清理非活躍會話"""
        # 建立一個舊的會話
        old_status = self.user_service.get_user_status("old_user")
        old_status.last_activity = datetime.now() - timedelta(hours=25)  # 超過 24 小時
        
        # 建立一個活躍的會話
        active_status = self.user_service.get_user_status(self.test_user_id)
        active_status.last_activity = datetime.now()  # 現在
        
        # 清理非活躍會話
        cleaned_count = self.user_service.cleanup_inactive_sessions(hours=24)
        
        assert cleaned_count == 1
        
        # 活躍會話應該仍然存在
        remaining_status = self.user_service.get_user_status(self.test_user_id)
        assert remaining_status.user_id == self.test_user_id