from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import structlog
import json
from ..models.card import ProcessingStatus, BatchProcessResult

logger = structlog.get_logger()


class UserService:
    """用戶服務管理 (支援 Redis 持久化)"""

    def __init__(self, redis_client=None, use_redis: bool = True):
        """
        初始化用戶服務

        Args:
            redis_client: Redis 客戶端實例，如果為 None 則使用記憶體存儲
            use_redis: 是否使用 Redis（即使提供了 client）
        """
        self.redis_client = redis_client if use_redis else None
        self.use_redis = use_redis and redis_client is not None

        # Fallback to in-memory storage if Redis is not available
        self._user_sessions: Dict[str, ProcessingStatus] = {}
        self._rate_limits: Dict[str, int] = {}

        logger.info("UserService initialized",
                   use_redis=self.use_redis,
                   storage_backend="Redis" if self.use_redis else "Memory")
    
    def _get_redis_key(self, user_id: str, key_type: str = "status") -> str:
        """生成 Redis key"""
        return f"namecard:user:{user_id}:{key_type}"

    def _save_status_to_redis(self, user_id: str, status: ProcessingStatus) -> None:
        """儲存用戶狀態到 Redis"""
        if not self.use_redis:
            return

        try:
            key = self._get_redis_key(user_id, "status")
            # 使用 Pydantic 的 model_dump_json 來序列化
            status_json = status.model_dump_json()
            # 設定 24 小時過期
            self.redis_client.setex(key, 86400, status_json)
        except Exception as e:
            logger.error("Failed to save status to Redis",
                        user_id=user_id, error=str(e))

    def _load_status_from_redis(self, user_id: str) -> Optional[ProcessingStatus]:
        """從 Redis 載入用戶狀態"""
        if not self.use_redis:
            return None

        try:
            key = self._get_redis_key(user_id, "status")
            status_json = self.redis_client.get(key)

            if status_json:
                # 使用 Pydantic 的 model_validate_json 來反序列化
                return ProcessingStatus.model_validate_json(status_json)
            return None
        except Exception as e:
            logger.error("Failed to load status from Redis",
                        user_id=user_id, error=str(e))
            return None

    def get_user_status(self, user_id: str) -> ProcessingStatus:
        """獲取用戶狀態（優先從 Redis 讀取）"""
        # 嘗試從 Redis 載入
        if self.use_redis:
            status = self._load_status_from_redis(user_id)
            if status:
                # 更新記憶體快取
                self._user_sessions[user_id] = status
            else:
                # Redis 中不存在，檢查記憶體或創建新的
                if user_id not in self._user_sessions:
                    status = ProcessingStatus(user_id=user_id)
                    self._user_sessions[user_id] = status
                    self._save_status_to_redis(user_id, status)
                else:
                    status = self._user_sessions[user_id]
        else:
            # 僅使用記憶體存儲
            if user_id not in self._user_sessions:
                self._user_sessions[user_id] = ProcessingStatus(user_id=user_id)
            status = self._user_sessions[user_id]

        # 檢查是否需要重置每日使用量
        now = datetime.now()
        if now.date() > status.usage_reset_date.date():
            status.daily_usage = 0
            status.usage_reset_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            logger.info("Reset daily usage", user_id=user_id)
            # 重置後儲存到 Redis
            if self.use_redis:
                self._save_status_to_redis(user_id, status)

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

        # 儲存到 Redis
        if self.use_redis:
            self._save_status_to_redis(user_id, status)

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

        # 儲存到 Redis
        if self.use_redis:
            self._save_status_to_redis(user_id, status)

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

        # 儲存到 Redis
        if self.use_redis:
            self._save_status_to_redis(user_id, status)

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

        # 儲存到 Redis
        if self.use_redis:
            self._save_status_to_redis(user_id, status)

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

        if self.use_redis:
            # 從 Redis 清理
            try:
                # 掃描所有用戶狀態 keys
                pattern = self._get_redis_key("*", "status")
                keys = list(self.redis_client.scan_iter(match=pattern))

                for key in keys:
                    try:
                        status_json = self.redis_client.get(key)
                        if status_json:
                            status = ProcessingStatus.model_validate_json(status_json)
                            if status.last_activity < cutoff:
                                self.redis_client.delete(key)
                                inactive_users.append(status.user_id)
                                logger.info("Cleaned up inactive session from Redis",
                                          user_id=status.user_id)
                    except Exception as e:
                        logger.error("Error cleaning up Redis key",
                                   key=key, error=str(e))
            except Exception as e:
                logger.error("Failed to cleanup Redis sessions", error=str(e))
        else:
            # 從記憶體清理
            for user_id, status in list(self._user_sessions.items()):
                if status.last_activity < cutoff:
                    inactive_users.append(user_id)

            for user_id in inactive_users:
                del self._user_sessions[user_id]
                logger.info("Cleaned up inactive session from memory",
                          user_id=user_id)

        return len(inactive_users)


def create_user_service(redis_client=None, use_redis: bool = True) -> UserService:
    """
    工廠函數：創建 UserService 實例

    Args:
        redis_client: Redis 客戶端（可選）
        use_redis: 是否使用 Redis

    Returns:
        UserService 實例
    """
    return UserService(redis_client=redis_client, use_redis=use_redis)


# 全域用戶服務實例（默認使用記憶體存儲，需要手動初始化 Redis）
user_service = UserService(redis_client=None, use_redis=False)