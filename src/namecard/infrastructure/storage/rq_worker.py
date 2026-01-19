"""
RQ Worker 啟動腳本

啟動 RQ Worker 來處理圖片上傳任務。

用法:
    # 開發環境
    python -m src.namecard.infrastructure.storage.rq_worker

    # 或直接運行
    python src/namecard/infrastructure/storage/rq_worker.py

    # 生產環境（使用 rq 命令）
    rq worker image_upload --url redis://localhost:6379/0
"""

import sys
import os

# 確保專案根目錄在 Python path 中
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import structlog
from simple_config import settings

logger = structlog.get_logger()


def create_rq_redis_client():
    """
    創建專用於 RQ 的 Redis 客戶端
    
    RQ 需要 decode_responses=False 來正確處理序列化的任務資料
    RQ Worker 需要長期連接，所以使用較長的超時和 keepalive
    """
    import redis
    
    # RQ Worker 需要較長的超時（用於 PubSub 監聽）
    # 設置 None 表示無超時，讓 Worker 可以一直等待任務
    rq_socket_timeout = None  # 無超時，Worker 會一直等待
    
    # 優先使用 REDIS_URL
    if settings.redis_url:
        logger.info("🔗 [RQ] Connecting to Redis using REDIS_URL")
        return redis.from_url(
            settings.redis_url,
            decode_responses=False,  # RQ 需要 False
            socket_timeout=rq_socket_timeout,
            socket_keepalive=True,  # 保持 TCP 連接活躍
            health_check_interval=30,  # 每 30 秒檢查連接健康
        )
    else:
        logger.info(
            "🔗 [RQ] Connecting to Redis using host/port configuration",
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
        )
        return redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password,
            db=settings.redis_db,
            decode_responses=False,  # RQ 需要 False
            socket_timeout=rq_socket_timeout,
            socket_keepalive=True,  # 保持 TCP 連接活躍
            health_check_interval=30,  # 每 30 秒檢查連接健康
        )


def start_worker():
    """啟動 RQ Worker"""
    try:
        from rq import Worker, Queue
        from src.namecard.infrastructure.storage.image_upload_worker import RQ_QUEUE_NAME
    except ImportError as e:
        logger.error("Required packages not installed", error=str(e))
        logger.info("Please install: pip install rq redis")
        sys.exit(1)

    # 創建 RQ 專用的 Redis 連接（decode_responses=False）
    try:
        redis_client = create_rq_redis_client()
        redis_client.ping()
        logger.info("✅ [RQ] Redis connection established successfully")
    except Exception as e:
        logger.error("Failed to connect to Redis", error=str(e))
        logger.info("Please ensure Redis is running and REDIS_URL is configured")
        sys.exit(1)

    logger.info("Starting RQ Worker", queue=RQ_QUEUE_NAME, redis_enabled=settings.redis_enabled)

    # 創建隊列
    queue = Queue(RQ_QUEUE_NAME, connection=redis_client)

    # 創建並啟動 Worker
    worker = Worker([queue], connection=redis_client, name=f"image-upload-worker-{os.getpid()}")

    logger.info("RQ Worker started, waiting for jobs...")

    # 開始處理任務
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    start_worker()
