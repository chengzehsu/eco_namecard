import os
import sqlite3
import threading
from contextlib import contextmanager
from typing import Iterator, Optional
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import structlog
from ..models.card import ProcessingStatus, BatchProcessResult

# 台灣時區
TW_TZ = ZoneInfo("Asia/Taipei")
RESET_HOUR = 4  # 台灣時間 04:00 重設

logger = structlog.get_logger()

# user_status 建表語句（IF NOT EXISTS，可重複執行）
_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS user_status (
    user_id TEXT PRIMARY KEY,
    daily_usage INTEGER NOT NULL DEFAULT 0,
    usage_reset_date TEXT NOT NULL,
    is_batch_mode INTEGER NOT NULL DEFAULT 0,
    batch_json TEXT,
    last_activity TEXT NOT NULL
)
"""


class UserService:
    """使用者服務管理（SQLite 持久化）

    每次操作開一條短連線（WAL + busy_timeout），單一進程內多執行緒安全。
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        初始化使用者服務

        Args:
            db_path: SQLite 資料庫路徑；為 None 時讀取 TENANT_DB_PATH 環境變數，
                     預設 data/tenants.db
        """
        self.db_path = db_path or os.getenv("TENANT_DB_PATH", "data/tenants.db")

        # 延遲建表：避免模組載入（全域單例）時就寫入磁碟，
        # 第一次實際操作時才確保 schema 存在
        self._schema_ready = False
        self._schema_lock = threading.Lock()

        logger.info(
            "UserService initialized",
            storage_backend="SQLite",
            db_path=self.db_path,
        )

    def _open_raw(self) -> sqlite3.Connection:
        """開啟原始 SQLite 連線並套用慣例 PRAGMA（WAL + busy_timeout）"""
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=15000")
        return conn

    def _ensure_schema(self) -> None:
        """確保資料表存在（延遲建表：避免模組載入全域單例時就寫入磁碟）"""
        if self._schema_ready:
            return
        with self._schema_lock:
            if self._schema_ready:
                return
            parent = Path(self.db_path).parent
            if str(parent) not in ("", "."):
                parent.mkdir(parents=True, exist_ok=True)
            conn = self._open_raw()
            try:
                conn.execute(_CREATE_TABLE_SQL)
                conn.commit()
            finally:
                conn.close()
            self._schema_ready = True

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """短連線交易情境管理：成功 commit、失敗 rollback，離開時關閉連線"""
        self._ensure_schema()
        conn = self._open_raw()
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    @staticmethod
    def _row_to_status(row) -> ProcessingStatus:
        """將資料列還原為 ProcessingStatus"""
        user_id, daily_usage, usage_reset_date, is_batch_mode, batch_json, last_activity = row
        current_batch = (
            BatchProcessResult.model_validate_json(batch_json) if batch_json else None
        )
        return ProcessingStatus(
            user_id=user_id,
            daily_usage=daily_usage,
            usage_reset_date=datetime.fromisoformat(usage_reset_date),
            is_batch_mode=bool(is_batch_mode),
            current_batch=current_batch,
            last_activity=datetime.fromisoformat(last_activity),
        )

    def _write_status(self, status: ProcessingStatus) -> None:
        """將完整狀態寫回資料庫（upsert）"""
        batch_json = (
            status.current_batch.model_dump_json() if status.current_batch else None
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO user_status
                    (user_id, daily_usage, usage_reset_date, is_batch_mode, batch_json, last_activity)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    daily_usage = excluded.daily_usage,
                    usage_reset_date = excluded.usage_reset_date,
                    is_batch_mode = excluded.is_batch_mode,
                    batch_json = excluded.batch_json,
                    last_activity = excluded.last_activity
                """,
                (
                    status.user_id,
                    status.daily_usage,
                    status.usage_reset_date.isoformat(),
                    1 if status.is_batch_mode else 0,
                    batch_json,
                    status.last_activity.isoformat(),
                ),
            )

    def get_user_status(self, user_id: str) -> ProcessingStatus:
        """獲取使用者狀態（不存在則建立預設列）"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT user_id, daily_usage, usage_reset_date, is_batch_mode, batch_json, last_activity "
                "FROM user_status WHERE user_id = ?",
                (user_id,),
            ).fetchone()

            if row is None:
                status = ProcessingStatus(user_id=user_id)
                conn.execute(
                    "INSERT OR IGNORE INTO user_status "
                    "(user_id, daily_usage, usage_reset_date, is_batch_mode, batch_json, last_activity) "
                    "VALUES (?, ?, ?, 0, NULL, ?)",
                    (
                        user_id,
                        status.daily_usage,
                        status.usage_reset_date.isoformat(),
                        status.last_activity.isoformat(),
                    ),
                )
            else:
                status = self._row_to_status(row)

            # 檢查是否需要重設每日使用量（台灣時間 04:00 重設）
            now_tw = datetime.now(TW_TZ)

            # 計算今天的重設時間點
            if now_tw.hour >= RESET_HOUR:
                today_reset = now_tw.replace(hour=RESET_HOUR, minute=0, second=0, microsecond=0)
            else:
                # 凌晨 04:00 之前，重設時間點是昨天的 04:00
                today_reset = (now_tw - timedelta(days=1)).replace(
                    hour=RESET_HOUR, minute=0, second=0, microsecond=0
                )

            # 將 usage_reset_date 轉換為台灣時間比較
            try:
                reset_date_tw = status.usage_reset_date.astimezone(TW_TZ)
            except (ValueError, TypeError):
                # 如果沒有時區資訊，假設是 UTC 並轉換
                reset_date_tw = status.usage_reset_date.replace(
                    tzinfo=ZoneInfo("UTC")
                ).astimezone(TW_TZ)

            # 如果上次重設時間早於今天的重設時間點，則重設
            if reset_date_tw < today_reset:
                status.daily_usage = 0
                status.usage_reset_date = today_reset
                conn.execute(
                    "UPDATE user_status SET daily_usage = 0, usage_reset_date = ? WHERE user_id = ?",
                    (today_reset.isoformat(), user_id),
                )
                logger.info("Reset daily usage at 04:00 TW time", user_id=user_id)

        return status

    def check_rate_limit(self, user_id: str, limit: int = 50) -> bool:
        """檢查使用者是否超過每日限制"""
        status = self.get_user_status(user_id)
        return status.daily_usage < limit

    def increment_usage(self, user_id: str) -> None:
        """增加使用者使用次數（單句原子 UPDATE）"""
        # 確保列存在並套用每日重設邏輯
        self.get_user_status(user_id)

        with self._connect() as conn:
            conn.execute(
                "UPDATE user_status SET daily_usage = daily_usage + 1, last_activity = ? "
                "WHERE user_id = ?",
                (datetime.now().isoformat(), user_id),
            )

        logger.info("User usage incremented", user_id=user_id, storage="SQLite")

    def start_batch_mode(self, user_id: str) -> BatchProcessResult:
        """開始批次模式"""
        status = self.get_user_status(user_id)

        if status.is_batch_mode and status.current_batch:
            # 結束當前批次，開始新的
            self.end_batch_mode(user_id)
            status = self.get_user_status(user_id)

        batch_result = BatchProcessResult(user_id=user_id, started_at=datetime.now())

        status.is_batch_mode = True
        status.current_batch = batch_result
        self._write_status(status)

        logger.info("Batch mode started", user_id=user_id)
        return batch_result

    def end_batch_mode(self, user_id: str) -> Optional[BatchProcessResult]:
        """結束批次模式"""
        status = self.get_user_status(user_id)

        if not status.is_batch_mode or not status.current_batch:
            return None

        batch_result = status.current_batch
        batch_result.completed_at = datetime.now()

        status.is_batch_mode = False
        status.current_batch = None
        self._write_status(status)

        logger.info(
            "Batch mode ended",
            user_id=user_id,
            total_cards=batch_result.total_cards,
            success_rate=batch_result.success_rate,
        )

        return batch_result

    def add_card_to_batch(self, user_id: str, card) -> bool:
        """將名片加入當前批次"""
        status = self.get_user_status(user_id)

        if not status.is_batch_mode or not status.current_batch:
            return False

        batch = status.current_batch
        batch.cards.append(card)
        batch.total_cards += 1

        if hasattr(card, "processed") and card.processed:
            batch.successful_cards += 1
        else:
            batch.failed_cards += 1

        self._write_status(status)
        return True

    def get_batch_status(self, user_id: str) -> Optional[str]:
        """獲取批次狀態描述"""
        status = self.get_user_status(user_id)

        if not status.is_batch_mode or not status.current_batch:
            return None

        batch = status.current_batch
        duration = datetime.now() - batch.started_at

        return (
            f"📊 批次進度: {batch.total_cards} 張名片\n"
            f"✅ 成功: {batch.successful_cards} 張\n"
            f"❌ 失敗: {batch.failed_cards} 張\n"
            f"⏱️ 處理時間: {duration.seconds // 60} 分鐘"
        )

    def cleanup_inactive_sessions(self, hours: int = 24) -> int:
        """清理非活躍的使用者會話，回傳刪除數"""
        cutoff = datetime.now() - timedelta(hours=hours)

        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM user_status WHERE last_activity < ?",
                (cutoff.isoformat(),),
            )
            deleted = cursor.rowcount

        if deleted:
            logger.info("Cleaned up inactive sessions", count=deleted)

        return deleted


# 全域使用者服務實例（event_handler / main.py 以 from-import 綁定）
user_service = UserService()
