"""
圖片上傳 Worker

支援兩種模式：
1. RQ (Redis Queue) - 推薦，支援持久化和自動重試
2. 內存 Queue - Fallback，當 RQ 不可用時使用

失敗任務會記錄到 Redis，可供後續重試。
"""

import queue
import threading
import structlog
import json
import base64
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from src.namecard.infrastructure.storage.image_storage import get_image_storage
from src.namecard.infrastructure.redis_client import get_redis_client

if TYPE_CHECKING:
    from src.namecard.infrastructure.storage.notion_client import NotionClient

logger = structlog.get_logger()

# Redis key prefixes
FAILED_TASK_PREFIX = "failed_upload:"
PENDING_TASK_PREFIX = "pending_upload:"
FAILED_TASK_TTL = 86400 * 7  # 7 days
PENDING_TASK_TTL = 86400  # 1 day

# RQ Queue name
RQ_QUEUE_NAME = "image_upload"

# Check if RQ is available
try:
    from rq import Queue, Retry
    from redis import Redis

    RQ_AVAILABLE = True
except Exception as e:
    # 捕獲所有異常（不只是 ImportError），因為版本不相容可能拋出其他異常
    RQ_AVAILABLE = False
    logger.warning(f"RQ import failed: {e}, will use in-memory queue")


@dataclass
class ImageUploadTask:
    """圖片上傳任務"""

    image_data: bytes
    page_ids: List[str]
    notion_client: "NotionClient"
    user_id: str


# ============================================================
# RQ-based Worker (持久化，推薦)
# ============================================================


def process_upload_task_rq(
    image_data_b64: str,
    page_ids: List[str],
    user_id: str,
    notion_api_key: str,
    notion_database_id: str,
) -> Dict[str, Any]:
    """
    RQ 任務處理函數（必須是頂層函數才能被 pickle）

    Args:
        image_data_b64: Base64 編碼的圖片資料
        page_ids: Notion 頁面 ID 列表
        user_id: 用戶 ID
        notion_api_key: Notion API Key
        notion_database_id: Notion Database ID

    Returns:
        處理結果
    """
    # 延遲導入以避免循環依賴
    from src.namecard.infrastructure.storage.notion_client import NotionClient

    logger.info("RQ: Processing image upload task", user_id=user_id, page_count=len(page_ids))

    # 解碼圖片資料
    image_data = base64.b64decode(image_data_b64)

    # 創建 NotionClient
    notion_client = NotionClient(api_key=notion_api_key, database_id=notion_database_id)

    # 1. 上傳圖片到 ImgBB
    image_storage = get_image_storage()
    if not image_storage:
        error_msg = "Image storage not available"
        logger.warning(error_msg)
        _record_failed_task_standalone(user_id, page_ids, error_msg, image_data)
        return {"success": False, "error": error_msg}

    image_url = image_storage.upload(image_data)

    if not image_url:
        error_msg = "ImgBB upload failed"
        logger.warning("Image upload failed", user_id=user_id)
        _record_failed_task_standalone(user_id, page_ids, error_msg, image_data)
        return {"success": False, "error": error_msg}

    logger.info("Image uploaded, updating Notion pages", url=image_url[:50] + "...")

    # 2. 更新所有 Notion 頁面
    success_count = 0
    failed_page_ids = []

    for page_id in page_ids:
        try:
            result = notion_client.update_page_with_image(page_id, image_url)
            if result:
                success_count += 1
                logger.info("Page updated with image", page_id=page_id[:10] + "...")
            else:
                failed_page_ids.append(page_id)
        except Exception as e:
            logger.error(
                "Failed to update page with image", page_id=page_id[:10] + "...", error=str(e)
            )
            failed_page_ids.append(page_id)

    # 記錄失敗的頁面
    if failed_page_ids:
        _record_failed_task_standalone(
            user_id,
            failed_page_ids,
            f"Failed to update {len(failed_page_ids)} pages",
            image_data=None,
            image_url=image_url,
        )

    logger.info(
        "RQ: Image upload task completed",
        user_id=user_id,
        success_count=success_count,
        total_pages=len(page_ids),
    )

    return {
        "success": success_count == len(page_ids),
        "success_count": success_count,
        "total_pages": len(page_ids),
    }


def _record_failed_task_standalone(
    user_id: str,
    page_ids: List[str],
    error: str,
    image_data: Optional[bytes] = None,
    image_url: Optional[str] = None,
) -> None:
    """
    記錄失敗任務（獨立函數，供 RQ 任務使用）
    """
    redis_client = get_redis_client()
    if not redis_client:
        logger.warning("Redis not available, cannot record failed task")
        return

    try:
        task_id = str(uuid4())[:8]
        failed_key = f"{FAILED_TASK_PREFIX}{user_id}:{task_id}"

        failed_data = {
            "task_id": task_id,
            "user_id": user_id,
            "page_ids": page_ids,
            "error": error,
            "timestamp": datetime.now().isoformat(),
            "image_url": image_url,
            "image_data_b64": base64.b64encode(image_data).decode() if image_data else None,
        }

        redis_client.setex(failed_key, FAILED_TASK_TTL, json.dumps(failed_data))
        logger.info("Failed task recorded", task_id=task_id, user_id=user_id, error=error)
    except Exception as e:
        logger.error("Failed to record failed task", error=str(e))


def submit_to_rq(
    image_data: bytes, page_ids: List[str], user_id: str, notion_client: "NotionClient"
) -> bool:
    """
    提交任務到 RQ 隊列

    Returns:
        是否成功提交
    """
    if not RQ_AVAILABLE:
        return False

    redis_client = get_redis_client()
    if not redis_client:
        return False

    try:
        # 創建 RQ Queue
        rq_queue = Queue(RQ_QUEUE_NAME, connection=redis_client)

        # 準備任務資料（需要可序列化）
        image_data_b64 = base64.b64encode(image_data).decode()

        # 提交任務（帶自動重試）
        job = rq_queue.enqueue(
            process_upload_task_rq,
            image_data_b64,
            page_ids,
            user_id,
            notion_client.api_key,
            notion_client.database_id,
            retry=Retry(max=3, interval=[10, 30, 60]),  # 重試 3 次：10s, 30s, 60s
            job_timeout=300,  # 5 分鐘超時
        )

        logger.info(
            "Task submitted to RQ", job_id=job.id, user_id=user_id, page_count=len(page_ids)
        )
        return True

    except Exception as e:
        logger.error("Failed to submit to RQ", error=str(e))
        return False


# ============================================================
# In-Memory Queue Worker (Fallback)
# ============================================================


class ImageUploadWorker:
    """
    內存隊列 Worker（當 RQ 不可用時使用）

    使用單一背景線程處理所有圖片上傳任務
    """

    def __init__(self):
        self._queue: queue.Queue[ImageUploadTask] = queue.Queue()
        self._worker_thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()

    def start(self) -> None:
        """啟動 worker 線程"""
        with self._lock:
            if self._running:
                return

            self._running = True
            self._worker_thread = threading.Thread(
                target=self._process_queue, daemon=True, name="ImageUploadWorker"
            )
            self._worker_thread.start()
            logger.info("ImageUploadWorker (in-memory) started")

    def stop(self) -> None:
        """停止 worker 線程"""
        with self._lock:
            self._running = False
            self._queue.put(None)  # type: ignore

    def submit(self, task: ImageUploadTask) -> None:
        """提交任務"""
        if not self._running:
            self.start()

        self._queue.put(task)
        logger.info(
            "Task submitted to in-memory queue",
            user_id=task.user_id,
            page_count=len(task.page_ids),
            queue_size=self._queue.qsize(),
        )

    def _process_queue(self) -> None:
        """處理任務隊列"""
        logger.info("ImageUploadWorker processing loop started")

        while self._running:
            try:
                task = self._queue.get(timeout=5)

                if task is None:
                    break

                self._process_task(task)
                self._queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                logger.error("Error in worker loop", error=str(e))

        logger.info("ImageUploadWorker stopped")

    def _process_task(self, task: ImageUploadTask) -> None:
        """處理單一上傳任務"""
        logger.info(
            "Processing image upload task", user_id=task.user_id, page_count=len(task.page_ids)
        )

        # 1. 上傳圖片到 ImgBB
        image_storage = get_image_storage()
        if not image_storage:
            error_msg = "Image storage not available"
            logger.warning(error_msg)
            self._record_failed_task(task, error_msg)
            return

        image_url = image_storage.upload(task.image_data)

        if not image_url:
            error_msg = "ImgBB upload failed"
            logger.warning("Image upload failed", user_id=task.user_id)
            self._record_failed_task(task, error_msg)
            return

        logger.info("Image uploaded, updating Notion pages", url=image_url[:50] + "...")

        # 2. 更新所有 Notion 頁面
        success_count = 0
        failed_page_ids = []

        for page_id in task.page_ids:
            try:
                result = task.notion_client.update_page_with_image(page_id, image_url)
                if result:
                    success_count += 1
                    logger.info("Page updated with image", page_id=page_id[:10] + "...")
                else:
                    failed_page_ids.append(page_id)
            except Exception as e:
                logger.error(
                    "Failed to update page with image", page_id=page_id[:10] + "...", error=str(e)
                )
                failed_page_ids.append(page_id)

        if failed_page_ids:
            self._record_failed_task(
                task,
                f"Failed to update {len(failed_page_ids)} pages",
                failed_page_ids=failed_page_ids,
                image_url=image_url,
            )

        logger.info(
            "Image upload task completed",
            user_id=task.user_id,
            success_count=success_count,
            total_pages=len(task.page_ids),
        )

    def _record_failed_task(
        self,
        task: ImageUploadTask,
        error: str,
        failed_page_ids: Optional[List[str]] = None,
        image_url: Optional[str] = None,
    ) -> None:
        """記錄失敗任務到 Redis"""
        _record_failed_task_standalone(
            task.user_id,
            failed_page_ids or task.page_ids,
            error,
            image_data=task.image_data if not image_url else None,
            image_url=image_url,
        )


# ============================================================
# Public API
# ============================================================

# 全域 worker 實例（單例）
_worker: Optional[ImageUploadWorker] = None
_worker_lock = threading.Lock()
_use_rq: Optional[bool] = None  # 緩存 RQ 可用性檢查結果


def _is_rq_available() -> bool:
    """檢查 RQ 是否可用（帶緩存）"""
    global _use_rq

    if _use_rq is not None:
        return _use_rq

    if not RQ_AVAILABLE:
        _use_rq = False
        return False

    redis_client = get_redis_client()
    if not redis_client:
        _use_rq = False
        logger.info("Redis not available, RQ disabled")
        return False

    _use_rq = True
    logger.info("RQ is available and will be used for image uploads")
    return True


def get_upload_worker() -> ImageUploadWorker:
    """獲取內存 worker 實例（當 RQ 不可用時使用）"""
    global _worker

    with _worker_lock:
        if _worker is None:
            _worker = ImageUploadWorker()
            _worker.start()
        return _worker


def submit_image_upload(
    image_data: bytes, page_ids: List[str], notion_client: "NotionClient", user_id: str
) -> None:
    """
    提交圖片上傳任務

    自動選擇 RQ（如果可用）或內存隊列

    Args:
        image_data: 圖片二進位資料
        page_ids: Notion 頁面 ID 列表
        notion_client: NotionClient 實例
        user_id: 用戶 ID
    """
    # 優先使用 RQ
    if _is_rq_available():
        if submit_to_rq(image_data, page_ids, user_id, notion_client):
            return
        logger.warning("RQ submit failed, falling back to in-memory queue")

    # Fallback 到內存隊列
    worker = get_upload_worker()
    task = ImageUploadTask(
        image_data=image_data, page_ids=page_ids, notion_client=notion_client, user_id=user_id
    )
    worker.submit(task)


# ============================================================
# Failed Task Management
# ============================================================


def get_failed_tasks(user_id: str) -> List[Dict[str, Any]]:
    """查詢用戶的失敗任務列表"""
    redis_client = get_redis_client()
    if not redis_client:
        return []

    try:
        pattern = f"{FAILED_TASK_PREFIX}{user_id}:*"
        keys = redis_client.keys(pattern)

        failed_tasks = []
        for key in keys:
            data = redis_client.get(key)
            if data:
                task_data = json.loads(data)
                task_data.pop("image_data_b64", None)  # 不返回大資料
                failed_tasks.append(task_data)

        failed_tasks.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return failed_tasks
    except Exception as e:
        logger.error("Failed to get failed tasks", error=str(e))
        return []


def retry_failed_task(user_id: str, task_id: str, notion_client: "NotionClient") -> bool:
    """重試失敗的任務"""
    redis_client = get_redis_client()
    if not redis_client:
        logger.warning("Redis not available for retry")
        return False

    try:
        failed_key = f"{FAILED_TASK_PREFIX}{user_id}:{task_id}"
        data = redis_client.get(failed_key)

        if not data:
            logger.warning("Failed task not found", task_id=task_id)
            return False

        task_data = json.loads(data)

        # 如果有已上傳的圖片 URL，直接更新頁面
        if task_data.get("image_url"):
            image_url = task_data["image_url"]
            page_ids = task_data["page_ids"]

            success_count = 0
            for page_id in page_ids:
                try:
                    result = notion_client.update_page_with_image(page_id, image_url)
                    if result:
                        success_count += 1
                except Exception as e:
                    logger.error("Retry: Failed to update page", error=str(e))

            if success_count == len(page_ids):
                redis_client.delete(failed_key)
                logger.info("Retry successful, removed failed task", task_id=task_id)
            return success_count > 0

        # 如果需要重新上傳圖片
        elif task_data.get("image_data_b64"):
            image_data = base64.b64decode(task_data["image_data_b64"])
            page_ids = task_data["page_ids"]

            submit_image_upload(image_data, page_ids, notion_client, user_id)
            redis_client.delete(failed_key)
            logger.info("Retry submitted, removed old failed task", task_id=task_id)
            return True
        else:
            logger.warning("No image data or URL available for retry", task_id=task_id)
            return False

    except Exception as e:
        logger.error("Failed to retry task", task_id=task_id, error=str(e))
        return False


def retry_all_failed_tasks(user_id: str, notion_client: "NotionClient") -> int:
    """重試用戶所有失敗的任務"""
    failed_tasks = get_failed_tasks(user_id)
    success_count = 0

    for task in failed_tasks:
        if retry_failed_task(user_id, task["task_id"], notion_client):
            success_count += 1

    logger.info(
        "Retry all failed tasks completed",
        user_id=user_id,
        total=len(failed_tasks),
        success=success_count,
    )
    return success_count


def clear_failed_tasks(user_id: str) -> int:
    """清除用戶所有失敗的任務記錄"""
    redis_client = get_redis_client()
    if not redis_client:
        return 0

    try:
        pattern = f"{FAILED_TASK_PREFIX}{user_id}:*"
        keys = redis_client.keys(pattern)
        if keys:
            redis_client.delete(*keys)
        return len(keys)
    except Exception as e:
        logger.error("Failed to clear failed tasks", error=str(e))
        return 0


def get_queue_info() -> Dict[str, Any]:
    """獲取隊列狀態資訊（用於監控）"""
    info = {
        "rq_available": RQ_AVAILABLE,
        "rq_enabled": _is_rq_available(),
        "queue_name": RQ_QUEUE_NAME if _is_rq_available() else "in-memory",
    }

    if _is_rq_available():
        try:
            redis_client = get_redis_client()
            if redis_client:
                rq_queue = Queue(RQ_QUEUE_NAME, connection=redis_client)
                info["pending_jobs"] = len(rq_queue)
                info["failed_jobs"] = rq_queue.failed_job_registry.count
        except Exception as e:
            info["error"] = str(e)
    else:
        if _worker:
            info["queue_size"] = _worker._queue.qsize()

    return info
