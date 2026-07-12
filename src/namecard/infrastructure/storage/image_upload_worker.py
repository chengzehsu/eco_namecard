"""
圖片上傳背景處理

單一背景執行緒（ThreadPoolExecutor max_workers=1，保序）執行：
上傳圖片到 ImgBB → 更新 Notion 頁面 → 失敗記錄到 SQLite failed_uploads 表。

失敗任務保留 7 天，可透過 retry_failed_task / retry_all_failed_tasks 重試。
"""

import os
import json
import sqlite3
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from uuid import uuid4

import structlog

from src.namecard.infrastructure.storage.image_storage import get_image_storage

if TYPE_CHECKING:
    from src.namecard.infrastructure.storage.notion_client import NotionClient

logger = structlog.get_logger()

# 失敗任務保留天數
FAILED_TASK_RETENTION_DAYS = 7


# ============================================================
# SQLite 失敗表
# ============================================================

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS failed_uploads (
    task_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    page_ids TEXT NOT NULL,
    error TEXT,
    image BLOB,
    image_url TEXT,
    created_at TEXT NOT NULL
)
"""


def _db_path() -> str:
    """SQLite 資料庫路徑（每次呼叫讀取環境變數，方便測試覆寫）"""
    return os.getenv("TENANT_DB_PATH", "data/tenants.db")


def _open_conn() -> sqlite3.Connection:
    """開啟 SQLite 連線並套用慣例 PRAGMA（WAL + busy_timeout），lazy 建表"""
    path = _db_path()
    parent = Path(path).parent
    if str(parent) not in ("", "."):
        parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=15000")
    conn.execute(_CREATE_TABLE_SQL)
    return conn


def _purge_expired(conn: sqlite3.Connection) -> None:
    """刪除超過保留天數的失敗任務（查詢/寫入時順手清理）"""
    cutoff = (datetime.now() - timedelta(days=FAILED_TASK_RETENTION_DAYS)).isoformat()
    conn.execute("DELETE FROM failed_uploads WHERE created_at < ?", (cutoff,))


def _record_failed_task(
    user_id: str,
    page_ids: List[str],
    error: str,
    image_data: Optional[bytes] = None,
    image_url: Optional[str] = None,
) -> None:
    """記錄失敗任務到 SQLite（圖片直接存 BLOB）"""
    try:
        task_id = str(uuid4())[:8]
        conn = _open_conn()
        try:
            _purge_expired(conn)
            conn.execute(
                """
                INSERT INTO failed_uploads
                    (task_id, user_id, page_ids, error, image, image_url, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    user_id,
                    json.dumps(page_ids),
                    error,
                    image_data,
                    image_url,
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        logger.info("Failed upload recorded", task_id=task_id, user_id=user_id, error=error)
    except Exception as e:
        logger.error("Failed to record failed upload", error=str(e))


def _delete_failed_task(user_id: str, task_id: str) -> None:
    """刪除單筆失敗任務記錄"""
    conn = _open_conn()
    try:
        conn.execute(
            "DELETE FROM failed_uploads WHERE user_id = ? AND task_id = ?",
            (user_id, task_id),
        )
        conn.commit()
    finally:
        conn.close()


# ============================================================
# 上傳核心流程
# ============================================================


def _sync_upload_image(
    image_data: bytes, page_ids: List[str], notion_client: "NotionClient", user_id: str
) -> bool:
    """
    上傳圖片並更新 Notion 頁面（在背景執行緒或重試時同步執行）

    流程：上傳 ImgBB → 更新所有 Notion 頁面 → 失敗記錄到 SQLite。

    Returns:
        是否全部頁面更新成功
    """
    # 1. 上傳圖片到 ImgBB
    image_storage = get_image_storage()
    if not image_storage:
        logger.warning("Image storage not available", user_id=user_id)
        _record_failed_task(user_id, page_ids, "Image storage not available", image_data)
        return False

    image_url = image_storage.upload(image_data)
    if not image_url:
        logger.warning("ImgBB upload failed", user_id=user_id)
        _record_failed_task(user_id, page_ids, "ImgBB upload failed", image_data)
        return False

    # 2. 更新所有 Notion 頁面
    success_count = 0
    failed_page_ids: List[str] = []

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

    # 3. 更新失敗的頁面記錄到失敗表（圖片已上傳成功，只留 URL 不留 BLOB）
    if failed_page_ids:
        _record_failed_task(
            user_id,
            failed_page_ids,
            f"Failed to update {len(failed_page_ids)} pages",
            image_data=None,
            image_url=image_url,
        )

    logger.info(
        "Image upload task completed",
        user_id=user_id,
        success_count=success_count,
        total_pages=len(page_ids),
    )
    return success_count == len(page_ids)


def _run_upload_task(
    image_data: bytes, page_ids: List[str], notion_client: "NotionClient", user_id: str
) -> bool:
    """背景執行緒的任務入口：包住核心流程，未預期例外也要留下失敗記錄"""
    try:
        return _sync_upload_image(image_data, page_ids, notion_client, user_id)
    except Exception as e:
        logger.error("Image upload task crashed", user_id=user_id, error=str(e))
        _record_failed_task(user_id, page_ids, f"Unexpected error: {e}", image_data)
        return False


# ============================================================
# 背景執行緒（單一 worker，保序）
# ============================================================

_executor: Optional[ThreadPoolExecutor] = None
_executor_lock = threading.Lock()


def _get_executor() -> ThreadPoolExecutor:
    """取得模組層級的單執行緒 executor（lazy 建立）"""
    global _executor
    with _executor_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ImageUpload")
        return _executor


def submit_image_upload(
    image_data: bytes, page_ids: List[str], notion_client: "NotionClient", user_id: str
) -> "Future[bool]":
    """
    提交圖片上傳任務到背景執行緒（單一 worker，依提交順序執行）

    Args:
        image_data: 圖片二進位資料
        page_ids: Notion 頁面 ID 列表
        notion_client: NotionClient 實例
        user_id: 使用者 ID

    Returns:
        背景任務的 Future（呼叫端可忽略；測試可用來等待完成）
    """
    future = _get_executor().submit(
        _run_upload_task, image_data, page_ids, notion_client, user_id
    )
    logger.info(
        "Image upload task submitted",
        user_id=user_id[:10] + "..." if user_id else None,
        page_count=len(page_ids),
        image_size=len(image_data),
    )
    return future


# ============================================================
# 失敗任務管理
# ============================================================


def get_failed_tasks(user_id: str) -> List[Dict[str, Any]]:
    """查詢使用者的失敗任務列表（不含圖片 BLOB，新到舊排序）"""
    try:
        conn = _open_conn()
        try:
            _purge_expired(conn)
            conn.commit()
            rows = conn.execute(
                """
                SELECT task_id, user_id, page_ids, error, image_url, created_at
                FROM failed_uploads
                WHERE user_id = ?
                ORDER BY created_at DESC
                """,
                (user_id,),
            ).fetchall()
        finally:
            conn.close()

        return [
            {
                "task_id": row[0],
                "user_id": row[1],
                "page_ids": json.loads(row[2]),
                "error": row[3],
                "image_url": row[4],
                "timestamp": row[5],
            }
            for row in rows
        ]
    except Exception as e:
        logger.error("Failed to get failed tasks", error=str(e))
        return []


def retry_failed_task(user_id: str, task_id: str, notion_client: "NotionClient") -> bool:
    """重試單一失敗任務"""
    try:
        conn = _open_conn()
        try:
            _purge_expired(conn)
            conn.commit()
            row = conn.execute(
                """
                SELECT page_ids, image, image_url
                FROM failed_uploads
                WHERE user_id = ? AND task_id = ?
                """,
                (user_id, task_id),
            ).fetchone()
        finally:
            conn.close()

        if not row:
            logger.warning("Failed task not found", task_id=task_id)
            return False

        page_ids = json.loads(row[0])
        image_data = row[1]
        image_url = row[2]

        # 圖片已上傳過：直接補更新 Notion 頁面
        if image_url:
            success_count = 0
            for page_id in page_ids:
                try:
                    result = notion_client.update_page_with_image(page_id, image_url)
                    if result:
                        success_count += 1
                except Exception as e:
                    logger.error("Retry: Failed to update page", error=str(e))

            if success_count == len(page_ids):
                _delete_failed_task(user_id, task_id)
                logger.info("Retry successful, removed failed task", task_id=task_id)
            return success_count > 0

        # 需要重新上傳圖片：先刪舊記錄再同步重跑（失敗會寫入新記錄）
        if image_data:
            _delete_failed_task(user_id, task_id)
            success = _sync_upload_image(image_data, page_ids, notion_client, user_id)
            logger.info("Retry re-upload finished", task_id=task_id, success=success)
            return success

        logger.warning("No image data or URL available for retry", task_id=task_id)
        return False

    except Exception as e:
        logger.error("Failed to retry task", task_id=task_id, error=str(e))
        return False


def retry_all_failed_tasks(user_id: str, notion_client: "NotionClient") -> int:
    """重試使用者所有失敗任務，回傳成功數"""
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
    """清除使用者所有失敗任務記錄，回傳刪除筆數"""
    try:
        conn = _open_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM failed_uploads WHERE user_id = ?", (user_id,)
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()
    except Exception as e:
        logger.error("Failed to clear failed tasks", error=str(e))
        return 0
