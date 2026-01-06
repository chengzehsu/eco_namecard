"""
Scheduler Service for Automated Tasks

Provides scheduled execution of tasks like Google Drive sync.
Uses APScheduler with SQLite job store for persistence.
"""

import os
from datetime import datetime
from typing import Optional, Dict, Callable
import structlog

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
    SCHEDULER_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False

logger = structlog.get_logger()

# Singleton scheduler instance
_scheduler: Optional["BackgroundScheduler"] = None


def get_scheduler() -> Optional["BackgroundScheduler"]:
    """Get the singleton scheduler instance."""
    return _scheduler


def init_scheduler(db_path: Optional[str] = None) -> Optional["BackgroundScheduler"]:
    """
    Initialize the scheduler with SQLite job store.
    
    Args:
        db_path: Path to SQLite database for job persistence.
                 Defaults to data/scheduler_jobs.db
    
    Returns:
        The scheduler instance, or None if APScheduler is not available.
    """
    global _scheduler
    
    if not SCHEDULER_AVAILABLE:
        logger.warning("APScheduler not available, scheduled tasks disabled")
        return None
    
    if _scheduler is not None:
        return _scheduler
    
    # Default database path
    if db_path is None:
        db_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "..", "..", "data", "scheduler_jobs.db"
        )
        db_path = os.path.normpath(db_path)
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # Configure job stores
    jobstores = {
        "default": SQLAlchemyJobStore(url=f"sqlite:///{db_path}")
    }
    
    # Create scheduler
    _scheduler = BackgroundScheduler(
        jobstores=jobstores,
        job_defaults={
            "coalesce": True,  # Combine missed executions
            "max_instances": 1,  # Only one instance at a time
            "misfire_grace_time": 3600,  # 1 hour grace period
        }
    )
    
    # Add event listeners
    def job_listener(event):
        if event.exception:
            logger.error(
                "Scheduled job failed",
                job_id=event.job_id,
                exception=str(event.exception),
            )
        else:
            logger.info("Scheduled job completed", job_id=event.job_id)
    
    _scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
    
    # Start scheduler
    _scheduler.start()
    logger.info("Scheduler initialized", db_path=db_path)
    
    return _scheduler


def shutdown_scheduler():
    """Shutdown the scheduler gracefully."""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler shutdown")


def schedule_drive_sync(
    tenant_id: str,
    cron_expression: str,
    folder_url: str,
    notion_api_key: str,
    notion_database_id: str,
    google_api_key: Optional[str] = None,
) -> bool:
    """
    Schedule a periodic Google Drive sync for a tenant.
    
    Args:
        tenant_id: The tenant ID
        cron_expression: Cron expression (e.g., "0 9 * * *" for daily at 9 AM)
        folder_url: Google Drive folder URL
        notion_api_key: Notion API key
        notion_database_id: Notion database ID
        google_api_key: Optional Google API key
    
    Returns:
        True if scheduled successfully
    """
    scheduler = get_scheduler()
    if not scheduler:
        logger.warning("Cannot schedule sync: scheduler not available")
        return False
    
    job_id = f"drive_sync_{tenant_id}"
    
    # Parse cron expression
    try:
        # APScheduler uses different field order: minute hour day month day_of_week
        parts = cron_expression.split()
        if len(parts) == 5:
            trigger = CronTrigger(
                minute=parts[0],
                hour=parts[1],
                day=parts[2],
                month=parts[3],
                day_of_week=parts[4],
            )
        else:
            logger.error("Invalid cron expression", expression=cron_expression)
            return False
    except Exception as e:
        logger.error("Failed to parse cron expression", error=str(e))
        return False
    
    # Remove existing job if any
    try:
        scheduler.remove_job(job_id)
    except Exception:
        pass
    
    # Add new job
    scheduler.add_job(
        func=_execute_drive_sync,
        trigger=trigger,
        id=job_id,
        kwargs={
            "tenant_id": tenant_id,
            "folder_url": folder_url,
            "notion_api_key": notion_api_key,
            "notion_database_id": notion_database_id,
            "google_api_key": google_api_key,
        },
        replace_existing=True,
    )
    
    logger.info(
        "Drive sync scheduled",
        tenant_id=tenant_id,
        job_id=job_id,
        cron=cron_expression,
    )
    
    return True


def cancel_drive_sync(tenant_id: str) -> bool:
    """
    Cancel a scheduled drive sync for a tenant.
    
    Args:
        tenant_id: The tenant ID
    
    Returns:
        True if cancelled successfully
    """
    scheduler = get_scheduler()
    if not scheduler:
        return False
    
    job_id = f"drive_sync_{tenant_id}"
    
    try:
        scheduler.remove_job(job_id)
        logger.info("Drive sync cancelled", tenant_id=tenant_id, job_id=job_id)
        return True
    except Exception as e:
        logger.warning("Failed to cancel drive sync", tenant_id=tenant_id, error=str(e))
        return False


def get_scheduled_jobs(tenant_id: Optional[str] = None) -> list:
    """
    Get list of scheduled jobs.
    
    Args:
        tenant_id: Optional filter by tenant ID
    
    Returns:
        List of job info dicts
    """
    scheduler = get_scheduler()
    if not scheduler:
        return []
    
    jobs = []
    for job in scheduler.get_jobs():
        if tenant_id and not job.id.endswith(tenant_id):
            continue
        
        jobs.append({
            "id": job.id,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
        })
    
    return jobs


def _execute_drive_sync(
    tenant_id: str,
    folder_url: str,
    notion_api_key: str,
    notion_database_id: str,
    google_api_key: Optional[str] = None,
):
    """
    Execute a scheduled drive sync.
    
    This is called by the scheduler.
    """
    logger.info("Executing scheduled drive sync", tenant_id=tenant_id)
    
    try:
        from src.namecard.infrastructure.storage.google_drive_client import get_google_drive_client
        from src.namecard.core.services.drive_sync_service import DriveSyncService
        from src.namecard.infrastructure.storage.tenant_db import get_tenant_db
        from src.namecard.api.admin.socketio_events import emit_sync_progress, emit_sync_completed
        
        drive_client = get_google_drive_client()
        if not drive_client:
            logger.error("Drive client not available for scheduled sync")
            return
        
        db = get_tenant_db()
        
        # Create sync log
        sync_log = db.create_drive_sync_log(
            tenant_id=tenant_id,
            folder_url=folder_url,
            folder_id=None,
            is_scheduled=True,
        )
        
        # Initialize sync service
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
            emit_sync_progress(tenant_id, progress.to_dict())
        
        # Run sync
        result = sync_service.sync_folder(
            folder_url=folder_url,
            progress_callback=progress_callback,
            user_id=f"scheduled_sync_{tenant_id}",
        )
        
        # Update final status
        db.update_drive_sync_log(
            log_id=sync_log["id"],
            status=result.status,
            completed=True,
        )
        
        db.update_tenant(tenant_id, {
            "google_drive_sync_status": result.status,
            "google_drive_last_sync": datetime.now().isoformat(),
        })
        
        emit_sync_completed(tenant_id, result.to_dict())
        
        logger.info(
            "Scheduled drive sync completed",
            tenant_id=tenant_id,
            status=result.status,
            success=result.success_count,
            errors=result.error_count,
        )
        
    except Exception as e:
        logger.error("Scheduled drive sync failed", tenant_id=tenant_id, error=str(e))
