"""
排程服務測試（croniter 背景迴圈版）

涵蓋：
- cron 到期判斷（is_cron_due / is_valid_cron）
- init_scheduler 冪等（不會重複開執行緒）
- 到期掃描觸發同步（_scan_and_trigger 呼叫 mock 的觸發函式）
- schedule_drive_sync 只做 cron 驗證
"""

import threading
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.namecard.core.services import scheduler


# ==================== cron 到期判斷 ====================


class TestCronDue:
    def test_due_within_window(self):
        """視窗內有到期點 → True（每天 09:00，視窗 08:59 → 09:01）"""
        last_check = datetime(2026, 7, 12, 8, 59, 0)
        now = datetime(2026, 7, 12, 9, 1, 0)
        assert scheduler.is_cron_due("0 9 * * *", last_check, now) is True

    def test_not_due_outside_window(self):
        """視窗內沒有到期點 → False（每天 09:00，視窗 09:01 → 09:03）"""
        last_check = datetime(2026, 7, 12, 9, 1, 0)
        now = datetime(2026, 7, 12, 9, 3, 0)
        assert scheduler.is_cron_due("0 9 * * *", last_check, now) is False

    def test_boundary_exclusive_left_inclusive_right(self):
        """視窗左開右閉：到期點恰等於 last_check 不觸發，恰等於 now 觸發"""
        fire = datetime(2026, 7, 12, 9, 0, 0)
        # 左界 = 到期點 → 下一個到期點是明天，不觸發
        assert scheduler.is_cron_due("0 9 * * *", fire, datetime(2026, 7, 12, 9, 0, 30)) is False
        # 右界 = 到期點 → 觸發
        assert scheduler.is_cron_due("0 9 * * *", datetime(2026, 7, 12, 8, 59, 30), fire) is True

    def test_invalid_cron_returns_false(self):
        """無效 cron → False（不拋例外，迴圈不中斷）"""
        last_check = datetime(2026, 7, 12, 8, 0, 0)
        now = datetime(2026, 7, 12, 10, 0, 0)
        assert scheduler.is_cron_due("not a cron", last_check, now) is False

    def test_is_valid_cron(self):
        assert scheduler.is_valid_cron("0 9 * * *") is True
        assert scheduler.is_valid_cron("*/5 * * * *") is True
        assert scheduler.is_valid_cron("99 99 * * *") is False
        assert scheduler.is_valid_cron("") is False
        assert scheduler.is_valid_cron(None) is False


# ==================== init 冪等 ====================


class TestInitScheduler:
    def test_init_is_idempotent(self):
        """重複呼叫 init_scheduler 只會有一條排程執行緒"""
        try:
            assert scheduler.init_scheduler() is True
            assert scheduler.init_scheduler() is True
            threads = [
                t for t in threading.enumerate()
                if t.name == "drive-sync-scheduler" and t.is_alive()
            ]
            assert len(threads) == 1
        finally:
            scheduler.shutdown_scheduler()

    def test_shutdown_stops_thread(self):
        """shutdown 後執行緒結束，可以重新啟動"""
        scheduler.init_scheduler()
        scheduler.shutdown_scheduler()
        threads = [
            t for t in threading.enumerate()
            if t.name == "drive-sync-scheduler" and t.is_alive()
        ]
        assert threads == []
        # 可以再次啟動
        try:
            assert scheduler.init_scheduler() is True
        finally:
            scheduler.shutdown_scheduler()


# ==================== 到期掃描觸發 ====================


def _make_row(tenant_id="t1", enabled=1, cron="0 9 * * *", folder="https://drive.google.com/x"):
    return {
        "id": tenant_id,
        "google_drive_sync_enabled": enabled,
        "google_drive_sync_schedule": cron,
        "google_drive_folder_url": folder,
    }


class TestScanAndTrigger:
    def test_due_tenant_triggers_sync(self, monkeypatch):
        """到期的啟用租戶會觸發同步"""
        mock_trigger = MagicMock()
        monkeypatch.setattr(scheduler, "_trigger_sync", mock_trigger)

        last_check = datetime(2026, 7, 12, 8, 59, 0)
        now = datetime(2026, 7, 12, 9, 1, 0)
        triggered = scheduler._scan_and_trigger(last_check, now, rows=[_make_row()])

        assert triggered == 1
        mock_trigger.assert_called_once_with("t1", "https://drive.google.com/x")

    def test_disabled_or_incomplete_tenants_skipped(self, monkeypatch):
        """未啟用、缺 cron、缺資料夾的租戶都不觸發"""
        mock_trigger = MagicMock()
        monkeypatch.setattr(scheduler, "_trigger_sync", mock_trigger)

        last_check = datetime(2026, 7, 12, 8, 59, 0)
        now = datetime(2026, 7, 12, 9, 1, 0)
        rows = [
            _make_row("t1", enabled=0),
            _make_row("t2", cron=None),
            _make_row("t3", folder=None),
        ]
        triggered = scheduler._scan_and_trigger(last_check, now, rows=rows)

        assert triggered == 0
        mock_trigger.assert_not_called()

    def test_not_due_tenant_not_triggered(self, monkeypatch):
        """視窗內沒到期點就不觸發"""
        mock_trigger = MagicMock()
        monkeypatch.setattr(scheduler, "_trigger_sync", mock_trigger)

        last_check = datetime(2026, 7, 12, 9, 5, 0)
        now = datetime(2026, 7, 12, 9, 6, 0)
        triggered = scheduler._scan_and_trigger(last_check, now, rows=[_make_row()])

        assert triggered == 0
        mock_trigger.assert_not_called()


# ==================== schedule / cancel 介面 ====================


class TestScheduleInterface:
    def test_schedule_drive_sync_validates_cron(self):
        assert scheduler.schedule_drive_sync("t1", "0 9 * * *") is True
        assert scheduler.schedule_drive_sync("t1", "bogus") is False

    def test_cancel_drive_sync_returns_true(self):
        assert scheduler.cancel_drive_sync("t1") is True
