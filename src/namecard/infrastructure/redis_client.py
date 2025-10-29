"""Redis 客戶端工具模組"""
import structlog
from typing import Optional
from simple_config import settings

logger = structlog.get_logger()


def create_redis_client():
    """
    創建 Redis 客戶端

    Returns:
        Redis 客戶端實例，如果 Redis 未啟用或連接失敗則返回 None
    """
    if not settings.redis_enabled:
        logger.info("Redis is disabled in configuration")
        return None

    try:
        import redis

        # 優先使用 REDIS_URL
        if settings.redis_url:
            logger.info("Connecting to Redis using REDIS_URL")
            client = redis.from_url(
                settings.redis_url,
                decode_responses=settings.redis_decode_responses,
                socket_timeout=settings.redis_socket_timeout,
                max_connections=settings.redis_max_connections
            )
        else:
            # 使用個別參數
            logger.info("Connecting to Redis using host/port configuration",
                       host=settings.redis_host,
                       port=settings.redis_port,
                       db=settings.redis_db)

            client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                password=settings.redis_password,
                db=settings.redis_db,
                decode_responses=settings.redis_decode_responses,
                socket_timeout=settings.redis_socket_timeout,
                max_connections=settings.redis_max_connections
            )

        # 測試連接
        client.ping()
        logger.info("Redis connection established successfully")
        return client

    except ImportError:
        logger.warning("redis package not installed, falling back to in-memory storage")
        return None
    except Exception as e:
        logger.error("Failed to connect to Redis, falling back to in-memory storage",
                    error=str(e),
                    redis_host=settings.redis_host,
                    redis_port=settings.redis_port)
        return None


# 全域 Redis 客戶端（延遲初始化）
_redis_client: Optional[any] = None


def get_redis_client():
    """
    獲取全域 Redis 客戶端（單例模式）

    Returns:
        Redis 客戶端實例或 None
    """
    global _redis_client

    if _redis_client is None:
        _redis_client = create_redis_client()

    return _redis_client


def close_redis_client():
    """關閉 Redis 連接"""
    global _redis_client

    if _redis_client:
        try:
            _redis_client.close()
            logger.info("Redis connection closed")
        except Exception as e:
            logger.error("Error closing Redis connection", error=str(e))
        finally:
            _redis_client = None
