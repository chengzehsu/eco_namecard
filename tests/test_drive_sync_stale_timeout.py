"""
Drive 同步 stale timeout 測試

驗證 drive_sync_logs 的 processing 互斥鎖具備「心跳 + 逾時放行」機制：
- 新鮮 processing 列（心跳未逾時）→ 仍視為進行中，擋住新同步
- stale processing 列（心跳超過 30 分鐘）→ 自動標記 failed，放行新同步
- 舊資料沒有 updated_at 時退回用 started_at 判斷
- update_drive_sync_log 每次呼叫（同步迴圈每處理完一個檔案）都會更新心跳
"""

import pytest
from datetime import datetime, timedelta

from src.namecard.infrastructure.storage.tenant_db import (
    TenantDatabase,
    DRIVE_SYNC_STALE_TIMEOUT_MINUTES,
)

TENANT_ID = "tenant-test-001"
FOLDER_URL = "https://drive.google.com/drive/folders/abc123"


@pytest.fixture
def db(tmp_path):
    """使用 tmp_path 建立獨立測試資料庫，不碰 repo 的 data/"""
    return TenantDatabase(db_path=str(tmp_path / "test_tenants.db"))


def _set_heartbeat(db, log_id, updated_at=None, started_at=None):
    """直接改寫 sync log 的時間戳，模擬心跳狀態"""
    with db.get_connection() as conn:
        conn.execute(
            "UPDATE drive_sync_logs SET updated_at = ? WHERE id = ?",
            (updated_at.isoformat() if updated_at else None, log_id),
        )
        if started_at is not None:
            conn.execute(
                "UPDATE drive_sync_logs SET started_at = ? WHERE id = ?",
                (started_at.isoformat(), log_id),
            )


def _minutes_ago(minutes):
    return datetime.now() - timedelta(minutes=minutes)


class TestDriveSyncStaleTimeout:
    def test_fresh_processing_still_blocks(self, db):
        """新鮮的 processing 列仍視為進行中，互斥檢查會擋住新同步"""
        log = db.create_drive_sync_log(TENANT_ID, FOLDER_URL)

        active = db.get_active_drive_sync(TENANT_ID)

        assert active is not None
        assert active["id"] == log["id"]
        assert active["status"] == "processing"

    def test_fresh_heartbeat_just_under_timeout_still_blocks(self, db):
        """心跳在逾時邊界內（29 分鐘前）仍視為進行中"""
        log = db.create_drive_sync_log(TENANT_ID, FOLDER_URL)
        _set_heartbeat(db, log["id"], updated_at=_minutes_ago(29))

        active = db.get_active_drive_sync(TENANT_ID)

        assert active is not None
        assert active["id"] == log["id"]

    def test_stale_processing_released_and_marked_failed(self, db):
        """stale processing 列（心跳 31 分鐘前）→ 標記 failed 並放行新同步"""
        log = db.create_drive_sync_log(TENANT_ID, FOLDER_URL)
        _set_heartbeat(db, log["id"], updated_at=_minutes_ago(31))

        active = db.get_active_drive_sync(TENANT_ID)

        # 放行：視為無進行中同步
        assert active is None

        # 舊列被標記為 failed，error_log 註明 stale timeout
        stale_log = db.get_drive_sync_log(log["id"])
        assert stale_log["status"] == "failed"
        assert "stale timeout" in stale_log["error_log"]
        assert str(DRIVE_SYNC_STALE_TIMEOUT_MINUTES) in stale_log["error_log"]
        assert stale_log["completed_at"] is not None

    def test_stale_release_allows_new_sync(self, db):
        """stale 列放行後，新同步可建立且成為唯一的進行中同步"""
        old_log = db.create_drive_sync_log(TENANT_ID, FOLDER_URL)
        _set_heartbeat(db, old_log["id"], updated_at=_minutes_ago(31))

        assert db.get_active_drive_sync(TENANT_ID) is None

        new_log = db.create_drive_sync_log(TENANT_ID, FOLDER_URL)
        active = db.get_active_drive_sync(TENANT_ID)

        assert active is not None
        assert active["id"] == new_log["id"]
        # 舊列維持 failed，不受影響
        assert db.get_drive_sync_log(old_log["id"])["status"] == "failed"

    def test_legacy_row_without_updated_at_uses_started_at(self, db):
        """舊資料沒有 updated_at → 退回用 started_at 判斷 stale"""
        log = db.create_drive_sync_log(TENANT_ID, FOLDER_URL)
        _set_heartbeat(db, log["id"], updated_at=None, started_at=_minutes_ago(31))

        assert db.get_active_drive_sync(TENANT_ID) is None
        assert db.get_drive_sync_log(log["id"])["status"] == "failed"

    def test_legacy_row_without_updated_at_fresh_started_at_blocks(self, db):
        """舊資料沒有 updated_at 但 started_at 很新 → 仍視為進行中"""
        log = db.create_drive_sync_log(TENANT_ID, FOLDER_URL)
        _set_heartbeat(db, log["id"], updated_at=None, started_at=_minutes_ago(5))

        active = db.get_active_drive_sync(TENANT_ID)

        assert active is not None
        assert active["id"] == log["id"]

    def test_update_drive_sync_log_refreshes_heartbeat(self, db):
        """update_drive_sync_log（同步迴圈每處理完一個檔案呼叫）會更新心跳"""
        log = db.create_drive_sync_log(TENANT_ID, FOLDER_URL)
        # 先讓心跳過期
        _set_heartbeat(db, log["id"], updated_at=_minutes_ago(31))

        # 模擬 progress_callback：處理完一個檔案後更新進度
        db.update_drive_sync_log(log_id=log["id"], processed_files=1)

        # 心跳已更新 → 不會被 stale timeout 放行
        active = db.get_active_drive_sync(TENANT_ID)
        assert active is not None
        assert active["id"] == log["id"]

        refreshed = db.get_drive_sync_log(log["id"])
        heartbeat = datetime.fromisoformat(refreshed["updated_at"])
        assert datetime.now() - heartbeat < timedelta(minutes=1)

    def test_stale_release_fixes_tenant_sync_status(self, db):
        """stale 放行後，租戶的 google_drive_sync_status 從 processing 修正為 failed"""
        # 直接插入最小租戶列（避開加密流程）
        with db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO tenants (
                    id, name, slug, line_channel_id,
                    line_channel_access_token_encrypted,
                    line_channel_secret_encrypted,
                    notion_database_id, google_drive_sync_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'processing')
                """,
                (TENANT_ID, "測試租戶", "test-tenant", "U0001", "enc", "enc", "db-id"),
            )

        log = db.create_drive_sync_log(TENANT_ID, FOLDER_URL)
        _set_heartbeat(db, log["id"], updated_at=_minutes_ago(31))

        assert db.get_active_drive_sync(TENANT_ID) is None

        with db.get_connection() as conn:
            row = conn.execute(
                "SELECT google_drive_sync_status FROM tenants WHERE id = ?",
                (TENANT_ID,),
            ).fetchone()
        assert row["google_drive_sync_status"] == "failed"

    def test_stale_check_scoped_to_tenant(self, db):
        """stale 判斷只影響該租戶，不動其他租戶的進行中同步"""
        stale_log = db.create_drive_sync_log(TENANT_ID, FOLDER_URL)
        _set_heartbeat(db, stale_log["id"], updated_at=_minutes_ago(31))

        other_log = db.create_drive_sync_log("tenant-other", FOLDER_URL)

        assert db.get_active_drive_sync(TENANT_ID) is None
        other_active = db.get_active_drive_sync("tenant-other")
        assert other_active is not None
        assert other_active["id"] == other_log["id"]
