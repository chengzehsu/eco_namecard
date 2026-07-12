"""使用者服務測試（SQLite 後端）"""

import sqlite3

import pytest
from datetime import datetime, timedelta
from src.namecard.core.services.user_service import UserService
from src.namecard.core.models.card import BusinessCard


class TestUserService:
    """使用者服務測試"""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path):
        """每個測試方法前的設置（資料庫一律放在 tmp_path，絕不寫入 repo 的 data/）"""
        self.db_path = str(tmp_path / "test.db")
        self.user_service = UserService(db_path=self.db_path)
        self.test_user_id = "test_user_123"

    def _set_db_columns(self, user_id, **columns):
        """直接改寫資料庫欄位（SQLite 後端下，改動回傳物件不會寫回，測試需直接操作 DB）"""
        assignments = ", ".join(f"{col} = ?" for col in columns)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                f"UPDATE user_status SET {assignments} WHERE user_id = ?",
                (*columns.values(), user_id),
            )

    def test_get_user_status_new_user(self):
        """測試獲取新使用者狀態"""
        status = self.user_service.get_user_status(self.test_user_id)

        assert status.user_id == self.test_user_id
        assert status.daily_usage == 0
        assert not status.is_batch_mode
        assert status.current_batch is None

    def test_check_rate_limit(self):
        """測試速率限制檢查"""
        # 新使用者應該通過限制檢查
        assert self.user_service.check_rate_limit(self.test_user_id, 50)

        # 模擬達到限制
        self.user_service.get_user_status(self.test_user_id)
        self._set_db_columns(self.test_user_id, daily_usage=50)

        assert not self.user_service.check_rate_limit(self.test_user_id, 50)

    def test_increment_usage(self):
        """測試增加使用次數"""
        initial_usage = self.user_service.get_user_status(self.test_user_id).daily_usage

        self.user_service.increment_usage(self.test_user_id)

        final_usage = self.user_service.get_user_status(self.test_user_id).daily_usage
        assert final_usage == initial_usage + 1

    def test_batch_mode_lifecycle(self):
        """測試批次模式生命週期"""
        # 開始批次模式
        batch_result = self.user_service.start_batch_mode(self.test_user_id)

        assert batch_result is not None
        assert batch_result.user_id == self.test_user_id
        assert batch_result.total_cards == 0

        status = self.user_service.get_user_status(self.test_user_id)
        assert status.is_batch_mode
        assert status.current_batch is not None

        # 結束批次模式
        completed_batch = self.user_service.end_batch_mode(self.test_user_id)

        assert completed_batch is not None
        assert completed_batch.completed_at is not None

        status = self.user_service.get_user_status(self.test_user_id)
        assert not status.is_batch_mode
        assert status.current_batch is None

    def test_add_card_to_batch(self):
        """測試將名片加入批次"""
        # 先開始批次模式
        self.user_service.start_batch_mode(self.test_user_id)

        # 建立測試名片
        card = BusinessCard(
            name="測試名片",
            company="測試公司",
            line_user_id=self.test_user_id,
            processed=True
        )

        # 加入批次
        success = self.user_service.add_card_to_batch(self.test_user_id, card)

        assert success

        status = self.user_service.get_user_status(self.test_user_id)
        batch = status.current_batch

        assert batch.total_cards == 1
        assert batch.successful_cards == 1
        assert len(batch.cards) == 1

    def test_add_card_without_batch_mode(self):
        """測試在非批次模式下加入名片"""
        card = BusinessCard(
            name="測試名片",
            line_user_id=self.test_user_id
        )

        # 未開始批次模式，應該失敗
        success = self.user_service.add_card_to_batch(self.test_user_id, card)
        assert not success

    def test_daily_usage_reset(self):
        """測試每日使用量重設"""
        # 設置使用量與昨天的重設時間
        self.user_service.get_user_status(self.test_user_id)
        self._set_db_columns(
            self.test_user_id,
            daily_usage=20,
            usage_reset_date=(datetime.now() - timedelta(days=1)).isoformat(),
        )

        # 重新獲取狀態應該觸發重設
        new_status = self.user_service.get_user_status(self.test_user_id)
        assert new_status.daily_usage == 0

    def test_get_batch_status(self):
        """測試獲取批次狀態"""
        # 非批次模式應該返回 None
        status_text = self.user_service.get_batch_status(self.test_user_id)
        assert status_text is None

        # 開始批次模式
        self.user_service.start_batch_mode(self.test_user_id)

        # 應該返回狀態文字
        status_text = self.user_service.get_batch_status(self.test_user_id)
        assert status_text is not None
        assert "批次進度" in status_text

    def test_cleanup_inactive_sessions(self):
        """測試清理非活躍會話"""
        # 建立一個舊的會話（超過 24 小時未活動）
        self.user_service.get_user_status("old_user")
        self._set_db_columns(
            "old_user",
            last_activity=(datetime.now() - timedelta(hours=25)).isoformat(),
        )

        # 建立一個活躍的會話
        self.user_service.get_user_status(self.test_user_id)
        self._set_db_columns(
            self.test_user_id,
            last_activity=datetime.now().isoformat(),
        )

        # 清理非活躍會話
        cleaned_count = self.user_service.cleanup_inactive_sessions(hours=24)

        assert cleaned_count == 1

        # 活躍會話應該仍然存在
        remaining_status = self.user_service.get_user_status(self.test_user_id)
        assert remaining_status.user_id == self.test_user_id

    def test_status_persists_across_instances(self):
        """測試狀態跨 UserService 實例持久化（SQLite 後端核心價值）"""
        self.user_service.increment_usage(self.test_user_id)
        self.user_service.start_batch_mode(self.test_user_id)

        # 用同一個 db_path 建立新實例，狀態應該還在
        new_service = UserService(db_path=self.db_path)
        status = new_service.get_user_status(self.test_user_id)

        assert status.daily_usage == 1
        assert status.is_batch_mode
        assert status.current_batch is not None
