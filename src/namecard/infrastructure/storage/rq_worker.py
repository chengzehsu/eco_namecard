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


def start_worker():
    """啟動 RQ Worker"""
    try:
        from rq import Worker, Queue
        from src.namecard.infrastructure.redis_client import get_redis_client
        from src.namecard.infrastructure.storage.image_upload_worker import RQ_QUEUE_NAME
    except ImportError as e:
        logger.error("Required packages not installed", error=str(e))
        logger.info("Please install: pip install rq redis")
        sys.exit(1)

    # 獲取 Redis 連接
    redis_client = get_redis_client()
    if not redis_client:
        logger.error("Failed to connect to Redis")
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
