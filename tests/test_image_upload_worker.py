"""
圖片上傳背景處理測試

涵蓋：
1. submit_image_upload 提交後由背景執行緒實際執行（單一 worker 保序）
2. 失敗時寫入 SQLite failed_uploads 表（含 BLOB / image_url）
3. get / retry / clear failed_tasks 行為
4. 7 天保留清理
"""

import json
import sqlite3
import threading
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from uuid import uuid4

import pytest

import src.namecard.infrastructure.storage.image_upload_worker as worker_module
from src.namecard.infrastructure.storage.image_upload_worker import (
    submit_image_upload,
    get_failed_tasks,
    retry_failed_task,
    retry_all_failed_tasks,
    clear_failed_tasks,
)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """每個測試使用獨立的 SQLite 資料庫（不碰 repo 的 data/）"""
    monkeypatch.setenv("TENANT_DB_PATH", str(tmp_path / "test_uploads.db"))
    yield


@pytest.fixture(autouse=True)
def fresh_executor():
    """每個測試使用全新的背景 executor，結束時等待任務清空"""
    worker_module._executor = None
    yield
    if worker_module._executor is not None:
        worker_module._executor.shutdown(wait=True)
    worker_module._executor = None


def _insert_failed_row(
    user_id,
    task_id=None,
    page_ids=None,
    error="test error",
    image=None,
    image_url=None,
    created_at=None,
):
    """直接寫一筆失敗任務到 SQLite（測試前置資料）"""
    conn = worker_module._open_conn()
    try:
        conn.execute(
            """
            INSERT INTO failed_uploads
                (task_id, user_id, page_ids, error, image, image_url, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id or str(uuid4())[:8],
                user_id,
                json.dumps(page_ids or ["page1"]),
                error,
                image,
                image_url,
                created_at or datetime.now().isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _count_rows():
    """回傳 failed_uploads 表總筆數"""
    conn = worker_module._open_conn()
    try:
        return conn.execute("SELECT COUNT(*) FROM failed_uploads").fetchone()[0]
    finally:
        conn.close()


class TestSubmitImageUpload:
    """submit_image_upload 背景執行測試"""

    @patch("src.namecard.infrastructure.storage.image_upload_worker.get_image_storage")
    def test_runs_in_background_thread_and_updates_pages(self, mock_get_storage):
        """提交後應在背景執行緒上傳並更新所有 Notion 頁面"""
        upload_thread_names = []

        mock_storage = MagicMock()

        def fake_upload(data):
            upload_thread_names.append(threading.current_thread().name)
            return "https://i.ibb.co/test.jpg"

        mock_storage.upload.side_effect = fake_upload
        mock_get_storage.return_value = mock_storage

        mock_notion = MagicMock()
        mock_notion.update_page_with_image.return_value = True

        future = submit_image_upload(
            image_data=b"test_image_data",
            page_ids=["page1", "page2", "page3"],
            notion_client=mock_notion,
            user_id="user123",
        )

        assert future.result(timeout=5) is True

        # 在背景執行緒（非主執行緒）執行
        assert upload_thread_names[0].startswith("ImageUpload")

        mock_storage.upload.assert_called_once_with(b"test_image_data")
        assert mock_notion.update_page_with_image.call_count == 3
        mock_notion.update_page_with_image.assert_any_call(
            "page1", "https://i.ibb.co/test.jpg"
        )

        # 全部成功不應留下失敗記錄
        assert get_failed_tasks("user123") == []

    @patch("src.namecard.infrastructure.storage.image_upload_worker.get_image_storage")
    def test_multiple_tasks_processed_in_order(self, mock_get_storage):
        """單一 worker 應依提交順序處理多個任務"""
        processed_order = []

        mock_storage = MagicMock()

        def fake_upload(data):
            processed_order.append(data.decode())
            return "https://i.ibb.co/test.jpg"

        mock_storage.upload.side_effect = fake_upload
        mock_get_storage.return_value = mock_storage

        mock_notion = MagicMock()
        mock_notion.update_page_with_image.return_value = True

        futures = [
            submit_image_upload(
                image_data=f"image_{i}".encode(),
                page_ids=[f"page_{i}"],
                notion_client=mock_notion,
                user_id=f"user_{i}",
            )
            for i in range(5)
        ]

        for future in futures:
            assert future.result(timeout=5) is True

        assert processed_order == [f"image_{i}" for i in range(5)]
        assert mock_notion.update_page_with_image.call_count == 5

    @patch("src.namecard.infrastructure.storage.image_upload_worker.get_image_storage")
    def test_imgbb_failure_records_to_sqlite_with_blob(self, mock_get_storage):
        """ImgBB 上傳失敗時應寫入 SQLite 失敗表（圖片存 BLOB），且不更新 Notion"""
        mock_storage = MagicMock()
        mock_storage.upload.return_value = None  # 模擬上傳失敗
        mock_get_storage.return_value = mock_storage

        mock_notion = MagicMock()

        future = submit_image_upload(
            image_data=b"raw_image_bytes",
            page_ids=["page1"],
            notion_client=mock_notion,
            user_id="user_fail",
        )

        assert future.result(timeout=5) is False
        mock_notion.update_page_with_image.assert_not_called()

        tasks = get_failed_tasks("user_fail")
        assert len(tasks) == 1
        assert tasks[0]["error"] == "ImgBB upload failed"
        assert tasks[0]["page_ids"] == ["page1"]

        # 圖片應以 BLOB 形式存在資料庫（非 base64）
        conn = worker_module._open_conn()
        try:
            row = conn.execute(
                "SELECT image FROM failed_uploads WHERE user_id = ?", ("user_fail",)
            ).fetchone()
        finally:
            conn.close()
        assert row[0] == b"raw_image_bytes"

    @patch("src.namecard.infrastructure.storage.image_upload_worker.get_image_storage")
    def test_storage_unavailable_records_failure(self, mock_get_storage):
        """圖片儲存服務不可用時應記錄失敗"""
        mock_get_storage.return_value = None

        future = submit_image_upload(
            image_data=b"img",
            page_ids=["page1"],
            notion_client=MagicMock(),
            user_id="user_nostorage",
        )

        assert future.result(timeout=5) is False
        tasks = get_failed_tasks("user_nostorage")
        assert len(tasks) == 1
        assert tasks[0]["error"] == "Image storage not available"

    @patch("src.namecard.infrastructure.storage.image_upload_worker.get_image_storage")
    def test_notion_partial_failure_records_failed_pages_with_url(self, mock_get_storage):
        """Notion 部分頁面更新失敗時，應只記錄失敗頁面且保留 image_url（不留 BLOB）"""
        mock_storage = MagicMock()
        mock_storage.upload.return_value = "https://i.ibb.co/test.jpg"
        mock_get_storage.return_value = mock_storage

        mock_notion = MagicMock()
        mock_notion.update_page_with_image.side_effect = [
            True,
            Exception("API Error"),
            True,
        ]

        future = submit_image_upload(
            image_data=b"img",
            page_ids=["page1", "page2", "page3"],
            notion_client=mock_notion,
            user_id="user_partial",
        )

        assert future.result(timeout=5) is False
        # 失敗後仍應繼續處理其他頁面
        assert mock_notion.update_page_with_image.call_count == 3

        tasks = get_failed_tasks("user_partial")
        assert len(tasks) == 1
        assert tasks[0]["page_ids"] == ["page2"]
        assert tasks[0]["image_url"] == "https://i.ibb.co/test.jpg"

        # 圖片已上傳成功，不應再存 BLOB
        conn = worker_module._open_conn()
        try:
            row = conn.execute(
                "SELECT image FROM failed_uploads WHERE user_id = ?", ("user_partial",)
            ).fetchone()
        finally:
            conn.close()
        assert row[0] is None

    @patch("src.namecard.infrastructure.storage.image_upload_worker.get_image_storage")
    def test_unexpected_exception_records_failure(self, mock_get_storage):
        """未預期例外也應留下失敗記錄且不讓背景執行緒炸掉"""
        mock_get_storage.side_effect = RuntimeError("boom")

        future = submit_image_upload(
            image_data=b"img",
            page_ids=["page1"],
            notion_client=MagicMock(),
            user_id="user_crash",
        )

        assert future.result(timeout=5) is False
        tasks = get_failed_tasks("user_crash")
        assert len(tasks) == 1
        assert "Unexpected error" in tasks[0]["error"]


class TestGetFailedTasks:
    """get_failed_tasks 查詢測試"""

    def test_returns_expected_format_without_blob(self):
        """回傳格式應包含 task_id/user_id/page_ids/error/timestamp，且不含 BLOB"""
        _insert_failed_row(
            "user1", task_id="t1", page_ids=["p1", "p2"], error="err", image=b"blob"
        )

        tasks = get_failed_tasks("user1")
        assert len(tasks) == 1
        task = tasks[0]
        assert task["task_id"] == "t1"
        assert task["user_id"] == "user1"
        assert task["page_ids"] == ["p1", "p2"]
        assert task["error"] == "err"
        assert task["timestamp"]
        assert "image" not in task
        assert "image_data_b64" not in task

    def test_sorted_newest_first_and_scoped_to_user(self):
        """應依時間新到舊排序，且只回傳指定使用者的任務"""
        now = datetime.now()
        _insert_failed_row(
            "user1", task_id="old", created_at=(now - timedelta(hours=2)).isoformat()
        )
        _insert_failed_row("user1", task_id="new", created_at=now.isoformat())
        _insert_failed_row("user2", task_id="other")

        tasks = get_failed_tasks("user1")
        assert [t["task_id"] for t in tasks] == ["new", "old"]

    def test_empty_when_no_tasks(self):
        """沒有失敗任務時應回傳空列表"""
        assert get_failed_tasks("nobody") == []


class TestRetryFailedTask:
    """retry_failed_task 重試測試"""

    def test_retry_with_image_url_updates_pages_and_deletes(self):
        """已有 image_url 的任務：直接補更新頁面，全部成功後刪除記錄"""
        _insert_failed_row(
            "user1",
            task_id="t1",
            page_ids=["p1", "p2"],
            image_url="https://i.ibb.co/x.jpg",
        )

        mock_notion = MagicMock()
        mock_notion.update_page_with_image.return_value = True

        assert retry_failed_task("user1", "t1", mock_notion) is True
        assert mock_notion.update_page_with_image.call_count == 2
        assert get_failed_tasks("user1") == []

    def test_retry_with_image_url_partial_success_keeps_record(self):
        """部分頁面更新失敗時應保留記錄，但仍回報成功（有進度）"""
        _insert_failed_row(
            "user1",
            task_id="t1",
            page_ids=["p1", "p2"],
            image_url="https://i.ibb.co/x.jpg",
        )

        mock_notion = MagicMock()
        mock_notion.update_page_with_image.side_effect = [True, Exception("fail")]

        assert retry_failed_task("user1", "t1", mock_notion) is True
        assert len(get_failed_tasks("user1")) == 1

    @patch("src.namecard.infrastructure.storage.image_upload_worker.get_image_storage")
    def test_retry_with_blob_reuploads_image(self, mock_get_storage):
        """只有 BLOB 的任務：重新上傳圖片並更新頁面，成功後刪除舊記錄"""
        mock_storage = MagicMock()
        mock_storage.upload.return_value = "https://i.ibb.co/new.jpg"
        mock_get_storage.return_value = mock_storage

        _insert_failed_row("user1", task_id="t1", page_ids=["p1"], image=b"blob_data")

        mock_notion = MagicMock()
        mock_notion.update_page_with_image.return_value = True

        assert retry_failed_task("user1", "t1", mock_notion) is True
        mock_storage.upload.assert_called_once_with(b"blob_data")
        mock_notion.update_page_with_image.assert_called_once_with(
            "p1", "https://i.ibb.co/new.jpg"
        )
        assert get_failed_tasks("user1") == []

    @patch("src.namecard.infrastructure.storage.image_upload_worker.get_image_storage")
    def test_retry_with_blob_failure_records_new_task(self, mock_get_storage):
        """重新上傳仍失敗時：舊記錄刪除，寫入新的失敗記錄"""
        mock_storage = MagicMock()
        mock_storage.upload.return_value = None
        mock_get_storage.return_value = mock_storage

        _insert_failed_row("user1", task_id="t1", page_ids=["p1"], image=b"blob_data")

        assert retry_failed_task("user1", "t1", MagicMock()) is False

        tasks = get_failed_tasks("user1")
        assert len(tasks) == 1
        assert tasks[0]["task_id"] != "t1"  # 舊記錄已刪、換成新記錄
        assert tasks[0]["error"] == "ImgBB upload failed"

    def test_retry_nonexistent_task_returns_false(self):
        """找不到任務時應回傳 False"""
        assert retry_failed_task("user1", "nope", MagicMock()) is False

    def test_retry_without_image_or_url_returns_false(self):
        """既無 BLOB 也無 URL 的任務無法重試"""
        _insert_failed_row("user1", task_id="t1", image=None, image_url=None)
        assert retry_failed_task("user1", "t1", MagicMock()) is False


class TestRetryAllFailedTasks:
    """retry_all_failed_tasks 測試"""

    def test_retries_all_and_counts_success(self):
        """應重試所有任務並回傳成功數"""
        _insert_failed_row(
            "user1", task_id="t1", page_ids=["p1"], image_url="https://i.ibb.co/a.jpg"
        )
        _insert_failed_row(
            "user1", task_id="t2", page_ids=["p2"], image_url="https://i.ibb.co/b.jpg"
        )

        mock_notion = MagicMock()
        mock_notion.update_page_with_image.return_value = True

        assert retry_all_failed_tasks("user1", mock_notion) == 2
        assert get_failed_tasks("user1") == []

    def test_returns_zero_when_no_tasks(self):
        """沒有失敗任務時應回傳 0"""
        assert retry_all_failed_tasks("user1", MagicMock()) == 0


class TestClearFailedTasks:
    """clear_failed_tasks 測試"""

    def test_clears_only_target_user(self):
        """只清除指定使用者的記錄並回傳刪除筆數"""
        _insert_failed_row("user1", task_id="t1")
        _insert_failed_row("user1", task_id="t2")
        _insert_failed_row("user2", task_id="t3")

        assert clear_failed_tasks("user1") == 2
        assert get_failed_tasks("user1") == []
        assert len(get_failed_tasks("user2")) == 1

    def test_returns_zero_when_nothing_to_clear(self):
        """沒有記錄可清時應回傳 0"""
        assert clear_failed_tasks("user1") == 0


class TestRetention:
    """7 天保留清理測試"""

    def test_expired_tasks_purged_on_query(self):
        """查詢時應順手刪除超過 7 天的記錄"""
        now = datetime.now()
        _insert_failed_row(
            "user1", task_id="old", created_at=(now - timedelta(days=8)).isoformat()
        )
        _insert_failed_row("user1", task_id="recent", created_at=now.isoformat())

        tasks = get_failed_tasks("user1")
        assert [t["task_id"] for t in tasks] == ["recent"]

        # 過期記錄應真的從資料庫刪除，不只是過濾
        assert _count_rows() == 1

    @patch("src.namecard.infrastructure.storage.image_upload_worker.get_image_storage")
    def test_expired_tasks_purged_on_write(self, mock_get_storage):
        """寫入新失敗記錄時也應順手清理過期記錄"""
        mock_storage = MagicMock()
        mock_storage.upload.return_value = None
        mock_get_storage.return_value = mock_storage

        _insert_failed_row(
            "user_other",
            task_id="old",
            created_at=(datetime.now() - timedelta(days=8)).isoformat(),
        )

        future = submit_image_upload(
            image_data=b"img",
            page_ids=["p1"],
            notion_client=MagicMock(),
            user_id="user1",
        )
        assert future.result(timeout=5) is False

        # 只剩新寫入的那筆
        assert _count_rows() == 1
        assert get_failed_tasks("user_other") == []
