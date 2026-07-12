"""
排程服務（croniter 背景迴圈版）

排程的唯一真實來源是 tenants.db 的租戶配置：
- google_drive_sync_enabled：是否啟用排程
- google_drive_sync_schedule：cron 表達式（5 欄位）
- google_drive_folder_url：要同步的 Google Drive 資料夾

運作方式：
- init_scheduler() 啟動一條 daemon 背景執行緒（冪等，重複呼叫不會多開）
- 迴圈每 60 秒醒來，掃描所有啟用排程的租戶，用 croniter 判斷
  「上次檢查時間到現在」之間是否有到期點，到期就執行同步
- 憑證只在執行當下從租戶配置解密取得，絕不序列化寫入磁碟
- 防重複觸發：迴圈以記憶體中的 last_check 單調前進，同一個到期點
  只會落在一個檢查視窗內；重啟後視窗從「現在」起算，過去的到期點
  不會補跑，因此也不可能重複觸發（最壞情況是停機期間漏跑一次）
"""

import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog
from croniter import croniter

logger = structlog.get_logger()

# 檢查間隔（秒）
CHECK_INTERVAL_SECONDS = 60

# 模組層狀態：單一背景執行緒 + 停止事件
_stop_event = threading.Event()
_thread: Optional[threading.Thread] = None
_lock = threading.Lock()


def is_valid_cron(cron_expression: str) -> bool:
    """驗證 cron 表達式是否合法（5 欄位，croniter 可解析）"""
    if not cron_expression or not isinstance(cron_expression, str):
        return False
    try:
        croniter(cron_expression)
        return True
    except Exception:
        return False


def is_cron_due(cron_expression: str, last_check: datetime, now: datetime) -> bool:
    """
    判斷 cron 在 (last_check, now] 視窗內是否有到期點。

    croniter.get_next() 回傳嚴格大於基準時間的下一個到期點，
    因此視窗左開右閉，相鄰視窗不會重複判定同一個到期點。
    """
    try:
        next_fire = croniter(cron_expression, last_check).get_next(datetime)
    except Exception as e:
        logger.warning(
            "Cron 表達式解析失敗，略過此租戶",
            cron=cron_expression,
            error=str(e),
        )
        return False
    return next_fire <= now


def init_scheduler() -> bool:
    """
    冪等啟動排程背景執行緒。

    應在應用程式啟動時呼叫（app.py），確保部署重啟後
    tenants.db 內的排程立即生效，不需等管理員重存設定。
    """
    global _thread
    with _lock:
        if _thread is not None and _thread.is_alive():
            return True
        _stop_event.clear()
        _thread = threading.Thread(
            target=_scheduler_loop,
            name="drive-sync-scheduler",
            daemon=True,
        )
        _thread.start()
        logger.info(
            "Drive 同步排程迴圈已啟動",
            check_interval_seconds=CHECK_INTERVAL_SECONDS,
        )
        return True


def shutdown_scheduler() -> None:
    """停止排程背景執行緒"""
    global _thread
    _stop_event.set()
    thread = _thread
    if thread is not None and thread.is_alive():
        thread.join(timeout=5)
    _thread = None
    logger.info("Drive 同步排程迴圈已停止")


def schedule_drive_sync(tenant_id: str, cron_expression: str) -> bool:
    """
    驗證租戶的排程設定。

    實際排程狀態就是租戶配置（tenants.db 的 google_drive_sync_enabled
    與 google_drive_sync_schedule），沒有獨立的 jobstore；
    此函式只負責驗證 cron 合法性，寫入配置由呼叫端處理。
    """
    if not is_valid_cron(cron_expression):
        logger.error(
            "無效的 cron 表達式",
            tenant_id=tenant_id,
            expression=cron_expression,
        )
        return False
    logger.info(
        "Drive 同步排程已驗證",
        tenant_id=tenant_id,
        cron=cron_expression,
    )
    return True


def cancel_drive_sync(tenant_id: str) -> bool:
    """
    取消租戶排程。

    排程狀態即租戶配置，呼叫端把 google_drive_sync_enabled 設為停用
    後排程迴圈就不會再觸發；此函式只留下紀錄。
    """
    logger.info("Drive 同步排程已取消", tenant_id=tenant_id)
    return True


# ==================== 內部：背景迴圈 ====================


def _scheduler_loop() -> None:
    """背景迴圈：每 CHECK_INTERVAL_SECONDS 秒掃描一次到期排程"""
    last_check = datetime.now()
    while not _stop_event.wait(CHECK_INTERVAL_SECONDS):
        now = datetime.now()
        try:
            _scan_and_trigger(last_check, now)
        except Exception as e:
            logger.error("排程掃描失敗", error=str(e))
        last_check = now


def _scan_and_trigger(
    last_check: datetime,
    now: datetime,
    rows: Optional[List[Dict[str, Any]]] = None,
) -> int:
    """
    掃描啟用 Drive 同步排程的租戶，到期就觸發同步。

    Args:
        last_check: 上次檢查時間（視窗左界，不含）
        now: 本次檢查時間（視窗右界，含）
        rows: 測試用，直接注入租戶資料列；正式流程從 tenants.db 讀取

    Returns:
        本次觸發的同步數量
    """
    if rows is None:
        rows = _load_sync_candidates()

    triggered = 0
    for row in rows:
        cron = row.get("google_drive_sync_schedule")
        folder_url = row.get("google_drive_folder_url")
        if not row.get("google_drive_sync_enabled") or not cron or not folder_url:
            continue
        if is_cron_due(cron, last_check, now):
            _trigger_sync(row["id"], folder_url)
            triggered += 1
    return triggered


def _load_sync_candidates() -> List[Dict[str, Any]]:
    """從 tenants.db 讀取所有啟用中的租戶資料列（含 Drive 排程欄位）"""
    from src.namecard.infrastructure.storage.tenant_db import get_tenant_db

    db = get_tenant_db()
    return db.list_tenants(include_inactive=False)


def _trigger_sync(tenant_id: str, folder_url: str) -> None:
    """
    觸發單一租戶的 Drive 同步。

    憑證在此刻才從租戶配置解密取得（tenant_service 負責解密），
    不經過任何序列化儲存。
    """
    logger.info("排程到期，觸發 Drive 同步", tenant_id=tenant_id)
    try:
        from simple_config import settings
        from src.namecard.core.services.tenant_service import get_tenant_service

        tenant = get_tenant_service().get_tenant_by_id(tenant_id)
        if not tenant:
            logger.error("找不到租戶，略過排程同步", tenant_id=tenant_id)
            return

        # 依租戶設定決定使用專屬或共用的 API key
        google_api_key = (
            tenant.google_api_key
            if not tenant.use_shared_google_api and tenant.google_api_key
            else settings.google_api_key
        )
        notion_api_key = (
            tenant.notion_api_key
            if not tenant.use_shared_notion_api and tenant.notion_api_key
            else settings.notion_api_key
        )

        _execute_drive_sync(
            tenant_id=tenant_id,
            folder_url=folder_url,
            notion_api_key=notion_api_key,
            notion_database_id=tenant.notion_database_id,
            google_api_key=google_api_key,
        )
    except Exception as e:
        logger.error("排程同步觸發失敗", tenant_id=tenant_id, error=str(e))


def _execute_drive_sync(
    tenant_id: str,
    folder_url: str,
    notion_api_key: str,
    notion_database_id: str,
    google_api_key: Optional[str] = None,
) -> None:
    """執行一次排程的 Drive 同步（在排程執行緒內同步執行，一次一個）"""
    logger.info("開始執行排程 Drive 同步", tenant_id=tenant_id)

    try:
        from src.namecard.core.services.drive_sync_service import DriveSyncService
        from src.namecard.infrastructure.storage.google_drive_client import (
            get_google_drive_client,
        )
        from src.namecard.infrastructure.storage.tenant_db import get_tenant_db

        drive_client = get_google_drive_client()
        if not drive_client:
            logger.error("Drive client 不可用，略過排程同步", tenant_id=tenant_id)
            return

        db = get_tenant_db()

        # 建立同步紀錄
        sync_log = db.create_drive_sync_log(
            tenant_id=tenant_id,
            folder_url=folder_url,
            folder_id=None,
            is_scheduled=True,
        )

        # 初始化同步服務
        sync_service = DriveSyncService(
            tenant_id=tenant_id,
            drive_client=drive_client,
            google_api_key=google_api_key,
            notion_api_key=notion_api_key,
            notion_database_id=notion_database_id,
        )

        def progress_callback(progress):
            db.update_drive_sync_log(
                log_id=sync_log["id"],
                total_files=progress.total_files,
                processed_files=progress.processed_files,
                success_count=progress.success_count,
                error_count=progress.error_count,
                skipped_count=progress.skipped_count,
                status=progress.status,
            )

        # 執行同步
        result = sync_service.sync_folder(
            folder_url=folder_url,
            progress_callback=progress_callback,
            user_id=f"scheduled_sync_{tenant_id}",
        )

        # 更新最終狀態
        db.update_drive_sync_log(
            log_id=sync_log["id"],
            status=result.status,
            completed=True,
        )

        db.update_tenant(
            tenant_id,
            {
                "google_drive_sync_status": result.status,
                "google_drive_last_sync": datetime.now().isoformat(),
            },
        )

        logger.info(
            "排程 Drive 同步完成",
            tenant_id=tenant_id,
            status=result.status,
            success=result.success_count,
            errors=result.error_count,
        )

    except Exception as e:
        logger.error("排程 Drive 同步失敗", tenant_id=tenant_id, error=str(e))
