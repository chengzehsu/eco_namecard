"""
圖片上傳 Worker

使用 Queue 機制處理圖片上傳任務，避免多線程競爭和 API 速率限制。
單一背景線程依序處理所有上傳任務。
"""

import queue
import threading
import structlog
from typing import List, Optional, TYPE_CHECKING
from dataclasses import dataclass

from src.namecard.infrastructure.storage.image_storage import get_image_storage

if TYPE_CHECKING:
    from src.namecard.infrastructure.storage.notion_client import NotionClient

logger = structlog.get_logger()


@dataclass
class ImageUploadTask:
    """圖片上傳任務"""
    image_data: bytes
    page_ids: List[str]
    notion_client: "NotionClient"
    user_id: str


class ImageUploadWorker:
    """
    圖片上傳 Worker
    
    使用單一背景線程處理所有圖片上傳任務，避免：
    - 多線程競爭
    - API 速率限制
    - 資源過度消耗
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
                target=self._process_queue,
                daemon=True,
                name="ImageUploadWorker"
            )
            self._worker_thread.start()
            logger.info("ImageUploadWorker started")
    
    def stop(self) -> None:
        """停止 worker 線程"""
        with self._lock:
            self._running = False
            # 放入 None 來喚醒阻塞的線程
            self._queue.put(None)  # type: ignore
    
    def submit(self, task: ImageUploadTask) -> None:
        """
        提交圖片上傳任務
        
        Args:
            task: 上傳任務
        """
        # 確保 worker 已啟動
        if not self._running:
            self.start()
        
        self._queue.put(task)
        logger.info("Image upload task submitted",
                   user_id=task.user_id,
                   page_count=len(task.page_ids),
                   queue_size=self._queue.qsize())
    
    def _process_queue(self) -> None:
        """處理任務隊列"""
        logger.info("ImageUploadWorker processing loop started")
        
        while self._running:
            try:
                # 阻塞等待任務
                task = self._queue.get(timeout=5)
                
                if task is None:
                    # 收到停止信號
                    break
                
                self._process_task(task)
                self._queue.task_done()
                
            except queue.Empty:
                # 超時，繼續等待
                continue
            except Exception as e:
                logger.error("Error in worker loop", error=str(e))
        
        logger.info("ImageUploadWorker stopped")
    
    def _process_task(self, task: ImageUploadTask) -> None:
        """
        處理單一上傳任務
        
        Args:
            task: 上傳任務
        """
        logger.info("Processing image upload task",
                   user_id=task.user_id,
                   page_count=len(task.page_ids))
        
        # 1. 上傳圖片到 ImgBB
        image_storage = get_image_storage()
        if not image_storage:
            logger.warning("Image storage not available, skipping task")
            return
        
        image_url = image_storage.upload(task.image_data)
        
        if not image_url:
            logger.warning("Image upload failed",
                          user_id=task.user_id)
            return
        
        logger.info("Image uploaded, updating Notion pages",
                   url=image_url[:50] + "...",
                   page_count=len(task.page_ids))
        
        # 2. 更新所有 Notion 頁面
        success_count = 0
        for page_id in task.page_ids:
            try:
                result = task.notion_client.update_page_with_image(page_id, image_url)
                if result:
                    success_count += 1
                    logger.info("Page updated with image",
                               page_id=page_id[:10] + "...")
            except Exception as e:
                logger.error("Failed to update page with image",
                            page_id=page_id[:10] + "...",
                            error=str(e))
        
        logger.info("Image upload task completed",
                   user_id=task.user_id,
                   success_count=success_count,
                   total_pages=len(task.page_ids))


# 全域 worker 實例（單例）
_worker: Optional[ImageUploadWorker] = None
_worker_lock = threading.Lock()


def get_upload_worker() -> ImageUploadWorker:
    """
    獲取全域 worker 實例
    
    Returns:
        ImageUploadWorker 實例
    """
    global _worker
    
    with _worker_lock:
        if _worker is None:
            _worker = ImageUploadWorker()
            _worker.start()
        return _worker


def submit_image_upload(
    image_data: bytes,
    page_ids: List[str],
    notion_client: "NotionClient",
    user_id: str
) -> None:
    """
    提交圖片上傳任務（便捷函數）
    
    Args:
        image_data: 圖片二進位資料
        page_ids: 要更新的 Notion 頁面 ID 列表
        notion_client: NotionClient 實例
        user_id: 用戶 ID（用於日誌）
    """
    worker = get_upload_worker()
    task = ImageUploadTask(
        image_data=image_data,
        page_ids=page_ids,
        notion_client=notion_client,
        user_id=user_id
    )
    worker.submit(task)

