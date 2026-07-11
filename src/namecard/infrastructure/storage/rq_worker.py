"""
RQ Worker 啟動腳本

啟動 RQ Worker 來處理圖片上傳任務。

用法:
    # 開發環境
    python -m src.namecard.infrastructure.storage.rq_worker

    # 或直接運行
    python src/namecard/infrastructure/storage/rq_worker.py

    # 生產環境（使用 rq 命令）
    rq worker image_upload --url redis://localhost:6379/0
"""

import sys
import os
import socket
import time
import json
import uuid

# 確保專案根目錄在 Python path 中
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import structlog
from simple_config import settings

logger = structlog.get_logger()

def _is_debug_log_enabled():
    """
    檢查除錯日誌是否啟用

    透過環境變數 RQ_WORKER_DEBUG_LOG 控制：
    - 未設定或設為 "false"/"0"/"no" -> 停用（預設）
    - 設為 "true"/"1"/"yes" -> 啟用

    Returns:
        bool: True 表示啟用除錯日誌，False 表示停用
    """
    debug_env = os.getenv("RQ_WORKER_DEBUG_LOG", "false").lower()
    return debug_env in ("true", "1", "yes")


def _debug_log(hypothesis_id, location, message, data=None):
    """
    除錯日誌函式（僅輸出到 stdout / 容器日誌）

    可透過環境變數 RQ_WORKER_DEBUG_LOG 控制是否啟用：
    - 預設停用
    - 設定 RQ_WORKER_DEBUG_LOG=true 可啟用

    Args:
        hypothesis_id: 假設 ID（用於除錯追蹤）
        location: 程式碼位置
        message: 日誌訊息
        data: 附加資料（可選）
    """
    # 檢查是否啟用除錯日誌
    if not _is_debug_log_enabled():
        return

    # 輸出到 stdout 以便在容器日誌中看到
    try:
        print(f"[DEBUG] {location}: {message} | {json.dumps(data or {})}", flush=True)
    except Exception:
        pass


def create_rq_redis_client():
    """
    創建專用於 RQ 的 Redis 客戶端
    
    RQ 需要 decode_responses=False 來正確處理序列化的任務資料
    RQ Worker 需要長期連接，所以使用較長的超時和 keepalive
    """
    import redis
    
    # RQ Worker 需要較長的超時（用於 PubSub 監聽）
    # 設置 None 表示無超時，讓 Worker 可以一直等待任務
    rq_socket_timeout = None  # 無超時，Worker 會一直等待
    
    # 優先使用 REDIS_URL
    if settings.redis_url:
        logger.info("🔗 [RQ] Connecting to Redis using REDIS_URL")
        return redis.from_url(
            settings.redis_url,
            decode_responses=False,  # RQ 需要 False
            socket_timeout=rq_socket_timeout,
            socket_keepalive=True,  # 保持 TCP 連接活躍
            health_check_interval=30,  # 每 30 秒檢查連接健康
        )
    else:
        logger.info(
            "🔗 [RQ] Connecting to Redis using host/port configuration",
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
        )
        return redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password,
            db=settings.redis_db,
            decode_responses=False,  # RQ 需要 False
            socket_timeout=rq_socket_timeout,
            socket_keepalive=True,  # 保持 TCP 連接活躍
            health_check_interval=30,  # 每 30 秒檢查連接健康
        )


def is_worker_expired(worker, timeout_seconds=60):
    """
    檢查 worker 是否過期
    
    Args:
        worker: RQ Worker 實例
        timeout_seconds: 超時時間（秒），默認 60 秒
    
    Returns:
        bool: True 表示 worker 已過期，False 表示 worker 仍活躍或無法確定
    """
    try:
        # 檢查最後心跳時間
        if hasattr(worker, 'last_heartbeat') and worker.last_heartbeat:
            time_since_heartbeat = time.time() - worker.last_heartbeat
            is_expired = time_since_heartbeat > timeout_seconds
            logger.debug(
                "Checked worker heartbeat",
                worker_name=worker.name,
                time_since_heartbeat=time_since_heartbeat,
                is_expired=is_expired
            )
            return is_expired
        
        # 如果無法獲取心跳時間，檢查 worker 狀態
        if hasattr(worker, 'get_state'):
            try:
                state = worker.get_state()
                # 如果狀態不是活躍狀態，可能是過期的
                is_expired = state not in ('started', 'busy', 'idle')
                logger.debug(
                    "Checked worker state",
                    worker_name=worker.name,
                    state=state,
                    is_expired=is_expired
                )
                return is_expired
            except Exception:
                pass
        
        # 保守處理：無法確定時返回 False（不清理）
        logger.debug(
            "Cannot determine worker expiration status, treating as active",
            worker_name=worker.name
        )
        return False
    except Exception as e:
        # 出錯時保守處理
        logger.warning(
            "Error checking worker expiration",
            worker_name=getattr(worker, 'name', 'unknown'),
            error=str(e)
        )
        return False


def cleanup_worker_from_redis(redis_client, worker_name):
    """
    直接從 Redis 清理 worker 註冊
    
    Args:
        redis_client: Redis 客戶端實例
        worker_name: Worker 名稱
    
    Returns:
        int: 刪除的 key 數量
    """
    try:
        # RQ 存儲 worker 資訊的主要 key
        worker_key = f"rq:worker:{worker_name}".encode('utf-8')
        deleted = redis_client.delete(worker_key)
        
        # 刪除所有相關 keys（使用模式匹配）
        pattern = f"rq:worker:{worker_name}*".encode('utf-8')
        keys_to_delete = list(redis_client.scan_iter(match=pattern))
        if keys_to_delete:
            deleted += redis_client.delete(*keys_to_delete)
        
        # 也從 RQ 的 workers 集合中移除（如果存在）
        try:
            redis_client.srem("rq:workers".encode('utf-8'), worker_name.encode('utf-8'))
        except Exception:
            pass  # 集合可能不存在，忽略錯誤
        
        return deleted
    except Exception as e:
        logger.warning("Error in cleanup_worker_from_redis", worker_name=worker_name, error=str(e))
        return 0


def cleanup_stale_workers(redis_client, proposed_worker_name, logger_instance=None):
    """
    清理過期的 worker 註冊
    
    策略：
    1. 只清理舊格式的 worker（image-upload-worker-{pid}）
    2. 檢查 worker 是否真的過期（最後心跳 > 60秒）
    3. 不清理新格式的 worker（包含 UUID）
    4. 清理與新名稱完全相同的 worker（極不可能但以防萬一）
    
    Args:
        redis_client: Redis 客戶端實例
        proposed_worker_name: 提議的新 worker 名稱
        logger_instance: 日誌實例（可選，默認使用模組級 logger）
    
    Returns:
        tuple: (cleaned_count, cleaned_names) - 清理的數量和名稱列表
    """
    if logger_instance is None:
        logger_instance = logger
    
    from rq import Worker
    
    cleaned_count = 0
    cleaned_names = []
    
    try:
        # 方法1: 通過 RQ Worker.all() 獲取並清理
        existing_workers = Worker.all(connection=redis_client)
        worker_names_before = [w.name for w in existing_workers]
        
        logger_instance.info(
            "Checking existing workers for cleanup",
            count=len(existing_workers),
            names=worker_names_before
        )
        
        for worker in existing_workers:
            try:
                worker_name = worker.name
                should_clean = False
                reason = ""
                
                # 情況1: 與新名稱完全相同（極不可能但以防萬一）
                if worker_name == proposed_worker_name:
                    should_clean = True
                    reason = "exact_name_match"
                    logger_instance.warning(
                        "Found duplicate worker name",
                        worker_name=worker_name,
                        reason=reason
                    )
                # 情況2: 舊格式的 worker（image-upload-worker-{pid}）
                elif worker_name.startswith("image-upload-worker-") and worker_name.count("-") == 2:
                    parts = worker_name.split("-")
                    if len(parts) == 4 and parts[-1].isdigit():  # 最後一部分是純數字（PID）
                        # 檢查 worker 是否過期
                        if is_worker_expired(worker, timeout_seconds=60):
                            should_clean = True
                            reason = "old_format_expired"
                            logger_instance.info(
                                "Found expired old-format worker",
                                worker_name=worker_name,
                                reason=reason
                            )
                        else:
                            logger_instance.debug(
                                "Old-format worker is still active, skipping",
                                worker_name=worker_name
                            )
                
                if should_clean:
                    logger_instance.warning(
                        "Cleaning up worker",
                        worker_name=worker_name,
                        reason=reason
                    )
                    try:
                        # 方法1: 嘗試使用 RQ 的 register_death()
                        try:
                            worker.register_death()
                            logger_instance.debug("Registered worker death via RQ API", worker_name=worker_name)
                        except Exception as e:
                            logger_instance.debug(
                                "Failed to register_death via RQ API, using direct Redis cleanup",
                                worker_name=worker_name,
                                error=str(e)
                            )
                        
                        # 方法2: 直接刪除 Redis keys（更徹底）
                        deleted = cleanup_worker_from_redis(redis_client, worker_name)
                        
                        if deleted > 0:
                            cleaned_count += 1
                            cleaned_names.append(worker_name)
                            logger_instance.info(
                                "Successfully cleaned up worker from Redis",
                                worker_name=worker_name,
                                deleted_keys=deleted,
                                reason=reason
                            )
                        else:
                            logger_instance.warning(
                                "No keys deleted for worker",
                                worker_name=worker_name
                            )
                    except Exception as cleanup_error:
                        logger_instance.warning(
                            "Failed to cleanup worker from Redis",
                            worker_name=worker_name,
                            error=str(cleanup_error)
                        )
            except Exception as e:
                logger_instance.warning(
                    "Failed to check/clean worker",
                    worker_name=getattr(worker, 'name', 'unknown'),
                    error=str(e)
                )
        
        # 方法2: 直接掃描 Redis 查找所有舊格式的 worker keys 並清理
        # 這確保即使 Worker.all() 沒有返回某些 worker，我們也能清理它們
        try:
            pattern = "rq:worker:image-upload-worker-*".encode('utf-8')
            all_worker_keys = list(redis_client.scan_iter(match=pattern))
            
            for key in all_worker_keys:
                try:
                    # 從 key 中提取 worker 名稱
                    key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                    if key_str.startswith("rq:worker:image-upload-worker-"):
                        worker_name_from_key = key_str.replace("rq:worker:", "")
                        
                        # 只處理舊格式的 worker（已經在 cleaned_names 中的跳過）
                        if worker_name_from_key not in cleaned_names:
                            # 檢查是否為舊格式
                            if worker_name_from_key.count("-") == 2:
                                parts = worker_name_from_key.split("-")
                                if len(parts) == 4 and parts[-1].isdigit():
                                    logger_instance.warning(
                                        "Found additional old-format worker key in Redis, cleaning up",
                                        worker_name=worker_name_from_key,
                                        key=key_str
                                    )
                                    deleted = cleanup_worker_from_redis(redis_client, worker_name_from_key)
                                    if deleted > 0:
                                        cleaned_count += 1
                                        cleaned_names.append(worker_name_from_key)
                except Exception as e:
                    logger_instance.warning("Error processing worker key", key=key, error=str(e))
        except Exception as scan_error:
            logger_instance.warning("Failed to scan Redis for worker keys", error=str(scan_error))
        
        if cleaned_count > 0:
            logger_instance.info(
                "Cleaned up stale worker registrations",
                count=cleaned_count,
                names=cleaned_names
            )
        else:
            logger_instance.info("No stale workers found to clean")
        
        return cleaned_count, cleaned_names
        
    except Exception as e:
        logger_instance.warning(
            "Failed to check/clean existing workers",
            error=str(e),
            error_type=type(e).__name__
        )
        return 0, []


def start_worker():
    """啟動 RQ Worker"""
    try:
        from rq import Worker, Queue
        from src.namecard.infrastructure.storage.image_upload_worker import RQ_QUEUE_NAME
    except ImportError as e:
        logger.error("Required packages not installed", error=str(e))
        logger.info("Please install: pip install rq redis")
        sys.exit(1)

    # 創建 RQ 專用的 Redis 連接（decode_responses=False）
    try:
        redis_client = create_rq_redis_client()
        redis_client.ping()
        logger.info("✅ [RQ] Redis connection established successfully")
    except Exception as e:
        logger.error("Failed to connect to Redis", error=str(e))
        logger.info("Please ensure Redis is running and REDIS_URL is configured")
        sys.exit(1)

    logger.info("Starting RQ Worker", queue=RQ_QUEUE_NAME, redis_enabled=settings.redis_enabled)

    # #region agent log
    current_pid = os.getpid()
    hostname = socket.gethostname()
    _debug_log("A", "rq_worker.py:118", "Worker startup - PID and hostname", {
        "pid": current_pid,
        "hostname": hostname,
        "queue_name": RQ_QUEUE_NAME
    })
    # #endregion

    # 創建隊列
    queue = Queue(RQ_QUEUE_NAME, connection=redis_client)

    # 生成唯一的 worker 名稱：包含 hostname、PID 和 UUID 前綴
    # 這樣即使同一容器重啟且 PID 相同，UUID 也會不同
    unique_id = str(uuid.uuid4())[:8]  # 使用 UUID 前 8 個字符作為唯一標識
    # 清理 hostname 中的特殊字符（用於 worker 名稱）
    safe_hostname = hostname.replace('.', '-').replace('_', '-')[:20]  # 限制長度
    proposed_worker_name = f"image-upload-worker-{safe_hostname}-{current_pid}-{unique_id}"
    
    # #region agent log
    _debug_log("A", "rq_worker.py:151", "Generated unique worker name", {
        "proposed_name": proposed_worker_name,
        "pid": current_pid,
        "hostname": hostname,
        "unique_id": unique_id
    })
    # #endregion

    # 清理可能衝突的 worker 註冊（防止重啟時的衝突）
    # 使用保守的清理策略：只清理真正過期的舊格式 worker
    # #region agent log
    _debug_log("B", "rq_worker.py:start_cleanup", "Starting worker cleanup", {
        "proposed_worker_name": proposed_worker_name
    })
    # #endregion
    
    cleaned_count, cleaned_names = cleanup_stale_workers(redis_client, proposed_worker_name, logger)
    
    if cleaned_count > 0:
        _debug_log("B", "rq_worker.py:after_cleanup", "Cleaned up stale workers", {
            "cleaned_count": cleaned_count,
            "cleaned_names": cleaned_names
        })
        # 等待一小段時間確保 Redis 更新
        time.sleep(0.5)
    else:
        _debug_log("B", "rq_worker.py:after_cleanup", "No stale workers to clean", {})
    # #endregion
    
    # 創建並啟動 Worker
    # #region agent log
    _debug_log("C", "rq_worker.py:202", "Creating Worker instance", {
        "worker_name": proposed_worker_name,
        "queue_name": RQ_QUEUE_NAME
    })
    # #endregion
    
    try:
        worker = Worker([queue], connection=redis_client, name=proposed_worker_name)
        # #region agent log
        _debug_log("C", "rq_worker.py:208", "Worker instance created successfully", {
            "worker_name": worker.name,
            "worker_id": getattr(worker, 'id', None)
        })
        # #endregion
    except ValueError as e:
        # #region agent log
        _debug_log("A", "rq_worker.py:214", "Worker creation failed - duplicate name", {
            "error": str(e),
            "proposed_name": proposed_worker_name,
            "pid": current_pid,
            "hostname": hostname,
            "unique_id": unique_id
        })
        # #endregion
        raise

    logger.info("RQ Worker started, waiting for jobs...", worker_name=worker.name)

    # #region agent log
    _debug_log("D", "rq_worker.py:223", "About to call worker.work()", {
        "worker_name": worker.name
    })
    # #endregion

    # 開始處理任務
    # 使用 try-except 捕獲 register_birth 時的錯誤
    try:
        worker.work(with_scheduler=False)
    except ValueError as e:
        error_msg = str(e)
        # #region agent log
        _debug_log("D", "rq_worker.py:232", "worker.work() failed - duplicate worker", {
            "error": error_msg,
            "worker_name": worker.name
        })
        # #endregion
        
        # 如果是重複 worker 的錯誤，嘗試清理後重試一次
        if "There exists an active worker named" in error_msg:
            logger.warning(
                "Duplicate worker detected during registration, attempting cleanup and retry",
                worker_name=worker.name,
                error=error_msg
            )
            
            # #region agent log
            _debug_log("D", "rq_worker.py:245", "Duplicate worker error detected", {
                "error": error_msg,
                "worker_name": worker.name
            })
            # #endregion
            
            # 提取錯誤訊息中的 worker 名稱
            conflicting_name = None
            if "named '" in error_msg and "' already" in error_msg:
                try:
                    start = error_msg.index("named '") + 7
                    end = error_msg.index("' already", start)
                    conflicting_name = error_msg[start:end]
                    logger.info("Extracted conflicting worker name from error", conflicting_name=conflicting_name)
                except (ValueError, IndexError):
                    pass
            
            # 再次嘗試清理：先清理衝突的 worker，然後清理所有過期 worker
            try:
                # 如果有衝突的 worker 名稱，先針對性清理它
                if conflicting_name:
                    logger.warning(
                        "Cleaning up conflicting worker specifically",
                        conflicting_name=conflicting_name
                    )
                    try:
                        # 直接清理衝突的 worker
                        deleted = cleanup_worker_from_redis(redis_client, conflicting_name)
                        if deleted > 0:
                            logger.info(
                                "Successfully cleaned up conflicting worker",
                                worker_name=conflicting_name,
                                deleted_keys=deleted
                            )
                        # 也嘗試使用 RQ API
                        try:
                            from rq import Worker
                            all_workers = Worker.all(connection=redis_client)
                            for w in all_workers:
                                if w.name == conflicting_name:
                                    try:
                                        w.register_death()
                                        logger.debug("Registered conflicting worker death via RQ API", worker_name=conflicting_name)
                                    except Exception:
                                        pass
                        except Exception:
                            pass
                    except Exception as cleanup_err:
                        logger.warning(
                            "Failed to cleanup conflicting worker",
                            worker_name=conflicting_name,
                            error=str(cleanup_err)
                        )
                
                # 然後清理所有過期的舊格式 worker（重用清理函數）
                # 使用當前 worker 名稱作為參考（稍後會生成新的唯一名稱）
                cleaned_count_retry, cleaned_names_retry = cleanup_stale_workers(
                    redis_client,
                    worker.name,  # 使用當前 worker 名稱
                    logger
                )
                
                if cleaned_count_retry > 0:
                    logger.info(
                        "Cleaned up workers during retry",
                        count=cleaned_count_retry,
                        names=cleaned_names_retry
                    )
                    # #region agent log
                    _debug_log("D", "rq_worker.py:retry_cleanup", "Cleaned up workers during retry", {
                        "cleaned_count": cleaned_count_retry,
                        "cleaned_names": cleaned_names_retry,
                        "conflicting_name": conflicting_name
                    })
                    # #endregion
            except Exception as cleanup_error:
                logger.warning("Failed to cleanup during retry", error=str(cleanup_error))
                # #region agent log
                _debug_log("D", "rq_worker.py:retry_cleanup_failed", "Failed to cleanup during retry", {
                    "error": str(cleanup_error)
                })
                # #endregion
            
            # 等待一小段時間讓 Redis 更新
            time.sleep(1.0)  # 確保 Redis 更新完成
            
            # 使用新的唯一名稱重試
            retry_unique_id = str(uuid.uuid4())[:8]
            retry_worker_name = f"image-upload-worker-{safe_hostname}-{current_pid}-{retry_unique_id}"
            logger.info("Retrying with new worker name", new_name=retry_worker_name, original_name=worker.name)
            
            # #region agent log
            _debug_log("D", "rq_worker.py:304", "Retrying with new worker name", {
                "original_name": worker.name,
                "retry_name": retry_worker_name,
                "conflicting_name": conflicting_name
            })
            # #endregion
            
            # 創建新的 worker 並重試
            try:
                retry_worker = Worker([queue], connection=redis_client, name=retry_worker_name)
                logger.info("Retry worker created, starting work...", worker_name=retry_worker_name)
                retry_worker.work(with_scheduler=False)
            except ValueError as retry_error:
                # 如果重試仍然失敗，記錄詳細資訊並拋出
                logger.error(
                    "Retry failed with new unique name - this should not happen",
                    retry_worker_name=retry_worker_name,
                    error=str(retry_error)
                )
                # #region agent log
                _debug_log("D", "rq_worker.py:320", "Retry failed - unexpected", {
                    "retry_worker_name": retry_worker_name,
                    "error": str(retry_error)
                })
                # #endregion
                raise
        else:
            # 其他錯誤直接拋出
            raise


if __name__ == "__main__":
    start_worker()
