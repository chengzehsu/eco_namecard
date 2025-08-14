from typing import Dict, Optional
from datetime import datetime, timedelta
import structlog
from ..models.card import ProcessingStatus, BatchProcessResult

logger = structlog.get_logger()


class UserService:
    """用戶服務管理"""
    
    def __init__(self):
        self._user_sessions: Dict[str, ProcessingStatus] = {}
        self._rate_limits: Dict[str, int] = {}
    
    def get_user_status(self, user_id: str) -> ProcessingStatus:
        """獲取用戶狀態"""
        if user_id not in self._user_sessions:
            self._user_sessions[user_id] = ProcessingStatus(user_id=user_id)
        
        status = self._user_sessions[user_id]
        
        # 檢查是否需要重置每日使用量
        now = datetime.now()
        if now.date() > status.usage_reset_date.date():
            status.daily_usage = 0
            status.usage_reset_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            logger.info("Reset daily usage", user_id=user_id)
        
        return status
    
    def check_rate_limit(self, user_id: str, limit: int = 50) -> bool:
        """檢查用戶是否超過每日限制"""
        status = self.get_user_status(user_id)
        return status.daily_usage < limit
    
    def increment_usage(self, user_id: str) -> None:
        """增加用戶使用次數"""
        status = self.get_user_status(user_id)
        status.daily_usage += 1
        status.last_activity = datetime.now()
        logger.info("User usage incremented", 
                   user_id=user_id, 
                   daily_usage=status.daily_usage)
    
    def start_batch_mode(self, user_id: str) -> BatchProcessResult:
        """開始批次模式"""
        status = self.get_user_status(user_id)
        
        if status.is_batch_mode and status.current_batch:
            # 結束當前批次，開始新的
            self.end_batch_mode(user_id)
        
        batch_result = BatchProcessResult(
            user_id=user_id,
            started_at=datetime.now()
        )
        
        status.is_batch_mode = True
        status.current_batch = batch_result
        
        logger.info("Batch mode started", user_id=user_id)
        return batch_result
    
    def end_batch_mode(self, user_id: str) -> Optional[BatchProcessResult]:
        """結束批次模式"""
        status = self.get_user_status(user_id)
        
        if not status.is_batch_mode or not status.current_batch:
            return None
        
        batch_result = status.current_batch
        batch_result.completed_at = datetime.now()
        
        status.is_batch_mode = False
        status.current_batch = None
        
        logger.info("Batch mode ended", 
                   user_id=user_id,
                   total_cards=batch_result.total_cards,
                   success_rate=batch_result.success_rate)
        
        return batch_result
    
    def add_card_to_batch(self, user_id: str, card) -> bool:
        """將名片加入當前批次"""
        status = self.get_user_status(user_id)
        
        if not status.is_batch_mode or not status.current_batch:
            return False
        
        batch = status.current_batch
        batch.cards.append(card)
        batch.total_cards += 1
        
        if hasattr(card, 'processed') and card.processed:
            batch.successful_cards += 1
        else:
            batch.failed_cards += 1
        
        return True
    
    def get_batch_status(self, user_id: str) -> Optional[str]:
        """獲取批次狀態描述"""
        status = self.get_user_status(user_id)
        
        if not status.is_batch_mode or not status.current_batch:
            return None
        
        batch = status.current_batch
        duration = datetime.now() - batch.started_at
        
        return (f"📊 批次進度: {batch.total_cards} 張名片\n"
               f"✅ 成功: {batch.successful_cards} 張\n"
               f"❌ 失敗: {batch.failed_cards} 張\n"
               f"⏱️ 處理時間: {duration.seconds // 60} 分鐘")
    
    def cleanup_inactive_sessions(self, hours: int = 24) -> int:
        """清理非活躍的用戶會話"""
        cutoff = datetime.now() - timedelta(hours=hours)
        inactive_users = []
        
        for user_id, status in self._user_sessions.items():
            if status.last_activity < cutoff:
                inactive_users.append(user_id)
        
        for user_id in inactive_users:
            del self._user_sessions[user_id]
            logger.info("Cleaned up inactive session", user_id=user_id)
        
        return len(inactive_users)


# 全域用戶服務實例
user_service = UserService()