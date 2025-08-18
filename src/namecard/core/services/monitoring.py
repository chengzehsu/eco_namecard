"""
Sentry 監控服務
提供全面的錯誤追蹤、業務邏輯監控和效能分析
"""

import time
import traceback
from typing import Dict, Any, Optional, Union, List
from enum import Enum
from dataclasses import dataclass, asdict
from datetime import datetime
import structlog

try:
    import sentry_sdk
    from sentry_sdk import capture_exception, capture_message, set_tag, set_context, set_user
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False

logger = structlog.get_logger()


class MonitoringLevel(Enum):
    """監控級別"""
    CRITICAL = "critical"
    ERROR = "error" 
    WARNING = "warning"
    INFO = "info"
    DEBUG = "debug"


class EventCategory(Enum):
    """事件分類"""
    AI_PROCESSING = "ai_processing"
    DATA_STORAGE = "data_storage"
    LINE_BOT = "line_bot"
    SECURITY = "security"
    USER_BEHAVIOR = "user_behavior"
    SYSTEM_PERFORMANCE = "system_performance"
    BUSINESS_LOGIC = "business_logic"


@dataclass
class MonitoringEvent:
    """監控事件資料結構"""
    category: EventCategory
    level: MonitoringLevel
    message: str
    user_id: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None
    tags: Optional[Dict[str, str]] = None
    timestamp: Optional[datetime] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass 
class PerformanceMetric:
    """效能指標"""
    operation: str
    duration: float
    success: bool
    user_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: Optional[datetime] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class SentryMonitoringService:
    """Sentry 監控服務"""
    
    def __init__(self):
        self.is_enabled = SENTRY_AVAILABLE
        self._performance_cache: List[PerformanceMetric] = []
        self._event_counters: Dict[str, int] = {}
        
        if not self.is_enabled:
            logger.warning("Sentry SDK not available, monitoring disabled")
        else:
            logger.info("Sentry monitoring service initialized")
    
    def capture_event(self, event: MonitoringEvent) -> None:
        """
        捕獲監控事件
        
        Args:
            event: 監控事件物件
        """
        try:
            # 更新事件計數器
            counter_key = f"{event.category.value}_{event.level.value}"
            self._event_counters[counter_key] = self._event_counters.get(counter_key, 0) + 1
            
            # 記錄到結構化日誌
            logger.bind(
                category=event.category.value,
                level=event.level.value,
                user_id=event.user_id,
                extra_data=event.extra_data,
                tags=event.tags,
                event_count=self._event_counters[counter_key]
            ).info(event.message)
            
            # 如果 Sentry 可用，發送到 Sentry
            if self.is_enabled:
                self._send_to_sentry(event)
                
        except Exception as e:
            logger.error("Failed to capture monitoring event", error=str(e))
    
    def capture_exception_with_context(
        self, 
        exception: Exception, 
        category: EventCategory,
        user_id: Optional[str] = None,
        extra_context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        捕獲異常並添加業務上下文
        
        Args:
            exception: 異常物件
            category: 事件分類
            user_id: 用戶ID
            extra_context: 額外上下文資訊
        """
        try:
            # 準備上下文資訊
            context = {
                "category": category.value,
                "timestamp": datetime.now().isoformat(),
                "stack_trace": traceback.format_exc()
            }
            
            if extra_context:
                context.update(extra_context)
            
            # 記錄到結構化日誌
            logger.error(
                "Exception captured with context",
                exception_type=type(exception).__name__,
                exception_message=str(exception),
                category=category.value,
                user_id=user_id,
                context=context
            )
            
            # 發送到 Sentry
            if self.is_enabled:
                if user_id:
                    set_user({"id": user_id})
                
                set_context("business_context", context)
                set_tag("category", category.value)
                
                capture_exception(exception)
                
        except Exception as e:
            logger.error("Failed to capture exception with context", error=str(e))
    
    def track_performance(self, metric: PerformanceMetric) -> None:
        """
        追蹤效能指標
        
        Args:
            metric: 效能指標物件
        """
        try:
            # 記錄到效能快取
            self._performance_cache.append(metric)
            
            # 保持快取大小
            if len(self._performance_cache) > 1000:
                self._performance_cache = self._performance_cache[-500:]
            
            # 記錄到日誌
            logger.info(
                "Performance metric tracked",
                operation=metric.operation,
                duration=metric.duration,
                success=metric.success,
                user_id=metric.user_id,
                metadata=metric.metadata
            )
            
            # 發送到 Sentry (如果啟用效能監控)
            if self.is_enabled and metric.duration > 0:
                with sentry_sdk.configure_scope() as scope:
                    scope.set_tag("operation", metric.operation)
                    scope.set_tag("success", str(metric.success))
                    if metric.user_id:
                        scope.set_user({"id": metric.user_id})
                    
                    # 如果操作時間過長，發送警告
                    if metric.duration > 5.0:  # 5秒閾值
                        capture_message(
                            f"Slow operation detected: {metric.operation} took {metric.duration:.2f}s",
                            level="warning"
                        )
                        
        except Exception as e:
            logger.error("Failed to track performance metric", error=str(e))
    
    def set_user_context(self, user_id: str, additional_info: Optional[Dict[str, Any]] = None) -> None:
        """
        設定用戶上下文
        
        Args:
            user_id: 用戶ID
            additional_info: 額外用戶資訊
        """
        try:
            user_data = {"id": user_id}
            if additional_info:
                user_data.update(additional_info)
            
            if self.is_enabled:
                set_user(user_data)
            
            logger.debug("User context set", user_id=user_id, user_data=user_data)
            
        except Exception as e:
            logger.error("Failed to set user context", error=str(e))
    
    def add_breadcrumb(self, message: str, category: str, data: Optional[Dict[str, Any]] = None) -> None:
        """
        添加麵包屑追蹤
        
        Args:
            message: 麵包屑訊息
            category: 分類
            data: 相關資料
        """
        try:
            if self.is_enabled:
                sentry_sdk.add_breadcrumb(
                    message=message,
                    category=category,
                    data=data or {},
                    level="info"
                )
            
            logger.debug("Breadcrumb added", message=message, category=category, data=data)
            
        except Exception as e:
            logger.error("Failed to add breadcrumb", error=str(e))
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """
        獲取效能摘要統計
        
        Returns:
            效能統計摘要
        """
        try:
            if not self._performance_cache:
                return {"message": "No performance data available"}
            
            # 計算統計資訊
            total_operations = len(self._performance_cache)
            successful_operations = sum(1 for m in self._performance_cache if m.success)
            success_rate = (successful_operations / total_operations) * 100
            
            durations = [m.duration for m in self._performance_cache]
            avg_duration = sum(durations) / len(durations)
            max_duration = max(durations)
            min_duration = min(durations)
            
            # 按操作類型分組
            operation_stats = {}
            for metric in self._performance_cache:
                if metric.operation not in operation_stats:
                    operation_stats[metric.operation] = {
                        "count": 0,
                        "success_count": 0,
                        "total_duration": 0.0,
                        "max_duration": 0.0
                    }
                
                stats = operation_stats[metric.operation]
                stats["count"] += 1
                if metric.success:
                    stats["success_count"] += 1
                stats["total_duration"] += metric.duration
                stats["max_duration"] = max(stats["max_duration"], metric.duration)
            
            # 計算每個操作的平均值
            for operation, stats in operation_stats.items():
                stats["avg_duration"] = stats["total_duration"] / stats["count"]
                stats["success_rate"] = (stats["success_count"] / stats["count"]) * 100
            
            return {
                "total_operations": total_operations,
                "success_rate": success_rate,
                "avg_duration": avg_duration,
                "max_duration": max_duration,
                "min_duration": min_duration,
                "operation_breakdown": operation_stats,
                "event_counters": self._event_counters
            }
            
        except Exception as e:
            logger.error("Failed to get performance summary", error=str(e))
            return {"error": str(e)}
    
    def _send_to_sentry(self, event: MonitoringEvent) -> None:
        """
        發送事件到 Sentry
        
        Args:
            event: 監控事件
        """
        try:
            # 設定標籤
            if event.tags:
                for key, value in event.tags.items():
                    set_tag(key, value)
            
            set_tag("category", event.category.value)
            set_tag("monitoring_level", event.level.value)
            
            # 設定用戶
            if event.user_id:
                set_user({"id": event.user_id})
            
            # 設定上下文
            if event.extra_data:
                set_context("event_data", event.extra_data)
            
            # 根據級別選擇發送方式
            sentry_level = self._get_sentry_level(event.level)
            
            if event.level in [MonitoringLevel.CRITICAL, MonitoringLevel.ERROR]:
                capture_message(event.message, level=sentry_level)
            else:
                # 對於 info/debug 級別，添加為麵包屑
                sentry_sdk.add_breadcrumb(
                    message=event.message,
                    category=event.category.value,
                    level=sentry_level,
                    data=event.extra_data or {}
                )
                
        except Exception as e:
            logger.error("Failed to send event to Sentry", error=str(e))
    
    def _get_sentry_level(self, level: MonitoringLevel) -> str:
        """
        轉換監控級別到 Sentry 級別
        
        Args:
            level: 監控級別
            
        Returns:
            Sentry 級別字串
        """
        mapping = {
            MonitoringLevel.CRITICAL: "fatal",
            MonitoringLevel.ERROR: "error",
            MonitoringLevel.WARNING: "warning", 
            MonitoringLevel.INFO: "info",
            MonitoringLevel.DEBUG: "debug"
        }
        return mapping.get(level, "info")


# 全域監控服務實例
monitoring_service = SentryMonitoringService()


# 方便的裝飾器
def monitor_performance(operation_name: str):
    """
    效能監控裝飾器
    
    Args:
        operation_name: 操作名稱
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            success = False
            user_id = None
            error = None
            
            try:
                # 嘗試從參數中提取 user_id
                if args and hasattr(args[0], 'user_id'):
                    user_id = getattr(args[0], 'user_id', None)
                elif 'user_id' in kwargs:
                    user_id = kwargs['user_id']
                
                result = func(*args, **kwargs)
                success = True
                return result
                
            except Exception as e:
                error = e
                monitoring_service.capture_exception_with_context(
                    e, 
                    EventCategory.SYSTEM_PERFORMANCE,
                    user_id=user_id,
                    extra_context={"operation": operation_name}
                )
                raise
                
            finally:
                duration = time.time() - start_time
                
                # 記錄效能指標
                metric = PerformanceMetric(
                    operation=operation_name,
                    duration=duration,
                    success=success,
                    user_id=user_id,
                    metadata={
                        "function_name": func.__name__,
                        "module": func.__module__,
                        "error": str(error) if error else None
                    }
                )
                
                monitoring_service.track_performance(metric)
        
        return wrapper
    return decorator


def monitor_ai_processing(func):
    """AI 處理專用監控裝飾器"""
    def wrapper(*args, **kwargs):
        monitoring_service.add_breadcrumb(
            f"Starting AI processing: {func.__name__}",
            "ai_processing"
        )
        
        try:
            result = func(*args, **kwargs)
            
            # 記錄成功事件
            monitoring_service.capture_event(MonitoringEvent(
                category=EventCategory.AI_PROCESSING,
                level=MonitoringLevel.INFO,
                message=f"AI processing completed: {func.__name__}",
                extra_data={"function": func.__name__, "success": True}
            ))
            
            return result
            
        except Exception as e:
            monitoring_service.capture_exception_with_context(
                e,
                EventCategory.AI_PROCESSING,
                extra_context={"function": func.__name__}
            )
            raise
    
    return wrapper