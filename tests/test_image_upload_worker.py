"""
ImageUploadWorker 測試

測試圖片上傳 Queue 機制，確保：
1. Worker 正確啟動和停止
2. 任務正確提交和處理
3. 多任務依序處理
4. 錯誤處理正確
"""

import pytest
import time
import threading
from unittest.mock import patch, MagicMock, call

from src.namecard.infrastructure.storage.image_upload_worker import (
    ImageUploadWorker,
    ImageUploadTask,
    get_upload_worker,
    submit_image_upload,
)


class TestImageUploadTask:
    """ImageUploadTask 資料類別測試"""

    def test_create_task(self):
        """應能創建任務"""
        mock_notion = MagicMock()
        task = ImageUploadTask(
            image_data=b"test_image",
            page_ids=["page1", "page2"],
            notion_client=mock_notion,
            user_id="user123"
        )
        
        assert task.image_data == b"test_image"
        assert task.page_ids == ["page1", "page2"]
        assert task.notion_client == mock_notion
        assert task.user_id == "user123"


class TestImageUploadWorker:
    """ImageUploadWorker 單元測試"""

    def test_worker_starts_and_stops(self):
        """Worker 應能正確啟動和停止"""
        worker = ImageUploadWorker()
        
        # 啟動
        worker.start()
        assert worker._running is True
        assert worker._worker_thread is not None
        assert worker._worker_thread.is_alive()
        
        # 停止
        worker.stop()
        time.sleep(0.5)  # 等待線程結束
        assert worker._running is False

    def test_worker_start_idempotent(self):
        """多次啟動應該只有一個線程"""
        worker = ImageUploadWorker()
        
        worker.start()
        thread1 = worker._worker_thread
        
        worker.start()  # 再次啟動
        thread2 = worker._worker_thread
        
        assert thread1 is thread2  # 同一個線程
        
        worker.stop()

    @patch('src.namecard.infrastructure.storage.image_upload_worker.get_image_storage')
    def test_submit_task(self, mock_get_storage):
        """應能提交任務到隊列"""
        mock_storage = MagicMock()
        mock_storage.upload.return_value = None  # 模擬上傳失敗，避免複雜的 mock
        mock_get_storage.return_value = mock_storage
        
        worker = ImageUploadWorker()
        worker.start()
        
        mock_notion = MagicMock()
        task = ImageUploadTask(
            image_data=b"test",
            page_ids=["page1"],
            notion_client=mock_notion,
            user_id="user1"
        )
        
        worker.submit(task)
        
        # 等待任務處理
        time.sleep(0.5)
        
        worker.stop()

    @patch('src.namecard.infrastructure.storage.image_upload_worker.get_image_storage')
    def test_process_task_uploads_and_updates_pages(self, mock_get_storage):
        """任務處理應上傳圖片並更新 Notion 頁面"""
        # 設置 mock
        mock_storage = MagicMock()
        mock_storage.upload.return_value = "https://i.ibb.co/test.jpg"
        mock_get_storage.return_value = mock_storage
        
        mock_notion = MagicMock()
        mock_notion.update_page_with_image.return_value = True
        
        worker = ImageUploadWorker()
        worker.start()
        
        task = ImageUploadTask(
            image_data=b"test_image_data",
            page_ids=["page1", "page2", "page3"],
            notion_client=mock_notion,
            user_id="user123"
        )
        
        worker.submit(task)
        
        # 等待任務處理完成
        time.sleep(1)
        
        # 驗證上傳被調用
        mock_storage.upload.assert_called_once_with(b"test_image_data")
        
        # 驗證每個頁面都被更新
        assert mock_notion.update_page_with_image.call_count == 3
        mock_notion.update_page_with_image.assert_any_call("page1", "https://i.ibb.co/test.jpg")
        mock_notion.update_page_with_image.assert_any_call("page2", "https://i.ibb.co/test.jpg")
        mock_notion.update_page_with_image.assert_any_call("page3", "https://i.ibb.co/test.jpg")
        
        worker.stop()

    @patch('src.namecard.infrastructure.storage.image_upload_worker.get_image_storage')
    def test_handles_upload_failure(self, mock_get_storage):
        """上傳失敗時不應更新 Notion 頁面"""
        mock_storage = MagicMock()
        mock_storage.upload.return_value = None  # 模擬上傳失敗
        mock_get_storage.return_value = mock_storage
        
        mock_notion = MagicMock()
        
        worker = ImageUploadWorker()
        worker.start()
        
        task = ImageUploadTask(
            image_data=b"test",
            page_ids=["page1"],
            notion_client=mock_notion,
            user_id="user1"
        )
        
        worker.submit(task)
        time.sleep(0.5)
        
        # Notion 不應被調用
        mock_notion.update_page_with_image.assert_not_called()
        
        worker.stop()

    @patch('src.namecard.infrastructure.storage.image_upload_worker.get_image_storage')
    def test_handles_notion_update_failure(self, mock_get_storage):
        """Notion 更新失敗時應繼續處理其他頁面"""
        mock_storage = MagicMock()
        mock_storage.upload.return_value = "https://i.ibb.co/test.jpg"
        mock_get_storage.return_value = mock_storage
        
        mock_notion = MagicMock()
        # 第一個頁面失敗，其他成功
        mock_notion.update_page_with_image.side_effect = [
            Exception("API Error"),
            True,
            True
        ]
        
        worker = ImageUploadWorker()
        worker.start()
        
        task = ImageUploadTask(
            image_data=b"test",
            page_ids=["page1", "page2", "page3"],
            notion_client=mock_notion,
            user_id="user1"
        )
        
        worker.submit(task)
        time.sleep(1)
        
        # 所有頁面都應該嘗試更新
        assert mock_notion.update_page_with_image.call_count == 3
        
        worker.stop()

    @patch('src.namecard.infrastructure.storage.image_upload_worker.get_image_storage')
    def test_multiple_tasks_processed_sequentially(self, mock_get_storage):
        """多個任務應依序處理"""
        mock_storage = MagicMock()
        mock_storage.upload.return_value = "https://i.ibb.co/test.jpg"
        mock_get_storage.return_value = mock_storage
        
        mock_notion = MagicMock()
        mock_notion.update_page_with_image.return_value = True
        
        worker = ImageUploadWorker()
        worker.start()
        
        # 提交多個任務
        for i in range(5):
            task = ImageUploadTask(
                image_data=f"image_{i}".encode(),
                page_ids=[f"page_{i}"],
                notion_client=mock_notion,
                user_id=f"user_{i}"
            )
            worker.submit(task)
        
        # 等待所有任務處理完成
        time.sleep(2)
        
        # 驗證所有上傳都被調用
        assert mock_storage.upload.call_count == 5
        
        # 驗證所有頁面都被更新
        assert mock_notion.update_page_with_image.call_count == 5
        
        worker.stop()


class TestGetUploadWorker:
    """get_upload_worker 函數測試"""

    def test_returns_singleton(self):
        """應返回單例 worker"""
        # 重置全域狀態
        import src.namecard.infrastructure.storage.image_upload_worker as module
        module._worker = None
        
        worker1 = get_upload_worker()
        worker2 = get_upload_worker()
        
        assert worker1 is worker2
        
        worker1.stop()


class TestSubmitImageUpload:
    """submit_image_upload 便捷函數測試"""

    @patch('src.namecard.infrastructure.storage.image_upload_worker.get_upload_worker')
    def test_submits_task_to_worker(self, mock_get_worker):
        """應提交任務到 worker"""
        mock_worker = MagicMock()
        mock_get_worker.return_value = mock_worker
        
        mock_notion = MagicMock()
        
        submit_image_upload(
            image_data=b"test_image",
            page_ids=["page1", "page2"],
            notion_client=mock_notion,
            user_id="user123"
        )
        
        # 驗證 submit 被調用
        mock_worker.submit.assert_called_once()
        
        # 驗證任務內容
        submitted_task = mock_worker.submit.call_args[0][0]
        assert submitted_task.image_data == b"test_image"
        assert submitted_task.page_ids == ["page1", "page2"]
        assert submitted_task.user_id == "user123"


class TestBatchUploadScenario:
    """批量上傳場景測試 (10-30 張圖片)"""

    @patch('src.namecard.infrastructure.storage.image_upload_worker.get_image_storage')
    def test_handles_30_images_batch(self, mock_get_storage):
        """應能處理 30 張圖片的批次上傳"""
        mock_storage = MagicMock()
        mock_storage.upload.return_value = "https://i.ibb.co/batch.jpg"
        mock_get_storage.return_value = mock_storage
        
        mock_notion = MagicMock()
        mock_notion.update_page_with_image.return_value = True
        
        worker = ImageUploadWorker()
        worker.start()
        
        # 模擬 30 張圖片上傳（每張圖片對應一個任務）
        num_images = 30
        for i in range(num_images):
            task = ImageUploadTask(
                image_data=f"image_data_{i}".encode(),
                page_ids=[f"page_{i}_1", f"page_{i}_2"],  # 每張圖片對應 2 個頁面
                notion_client=mock_notion,
                user_id=f"user_{i}"
            )
            worker.submit(task)
        
        # 等待所有任務處理（給足夠時間）
        timeout = 10  # 10 秒超時
        start = time.time()
        while worker._queue.qsize() > 0 and (time.time() - start) < timeout:
            time.sleep(0.1)
        
        # 驗證所有圖片都被上傳
        assert mock_storage.upload.call_count == num_images
        
        # 驗證所有頁面都被更新（30 張圖片 x 2 頁面 = 60 次更新）
        assert mock_notion.update_page_with_image.call_count == num_images * 2
        
        worker.stop()

    @patch('src.namecard.infrastructure.storage.image_upload_worker.get_image_storage')
    def test_queue_does_not_block_main_thread(self, mock_get_storage):
        """Queue 不應阻塞主線程"""
        mock_storage = MagicMock()
        # 模擬慢速上傳
        def slow_upload(data):
            time.sleep(0.1)
            return "https://i.ibb.co/slow.jpg"
        mock_storage.upload.side_effect = slow_upload
        mock_get_storage.return_value = mock_storage
        
        mock_notion = MagicMock()
        
        worker = ImageUploadWorker()
        worker.start()
        
        # 記錄開始時間
        start = time.time()
        
        # 快速提交 10 個任務
        for i in range(10):
            task = ImageUploadTask(
                image_data=f"image_{i}".encode(),
                page_ids=[f"page_{i}"],
                notion_client=mock_notion,
                user_id=f"user_{i}"
            )
            worker.submit(task)
        
        # 提交應該非常快（不阻塞）
        submit_time = time.time() - start
        assert submit_time < 0.5, f"Submit took too long: {submit_time}s"
        
        worker.stop()

