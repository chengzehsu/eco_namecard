"""
Quota Service for Multi-Tenant Commercialization

Manages scan quotas, user limits, and quota consumption tracking.
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import structlog

from src.namecard.infrastructure.storage.tenant_db import TenantDatabase, get_tenant_db

logger = structlog.get_logger()


class QuotaService:
    """
    Service for managing tenant quotas and usage limits.
    
    Features:
    - Check user limits before allowing new LINE users
    - Check scan quotas before processing cards
    - Track quota consumption
    - Handle monthly quota resets
    - Manage bonus quota purchases
    """

    def __init__(self, db: Optional[TenantDatabase] = None):
        """
        Initialize the quota service.
        
        Args:
            db: TenantDatabase instance. If None, uses global instance.
        """
        self.db = db or get_tenant_db()
        logger.info("QuotaService initialized")

    def get_tenant_limits(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current limits for a tenant based on their plan version.
        
        Returns:
            Dict with user_limit, monthly_scan_quota, daily_card_limit, batch_size_limit
            or None if tenant not found
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT 
                    t.id as tenant_id,
                    t.name as tenant_name,
                    t.plan_version_id,
                    t.bonus_scan_quota,
                    t.current_month_scans,
                    t.quota_reset_date,
                    pv.user_limit,
                    pv.monthly_scan_quota,
                    pv.daily_card_limit,
                    pv.batch_size_limit,
                    sp.name as plan_name,
                    sp.display_name as plan_display_name
                FROM tenants t
                LEFT JOIN plan_versions pv ON t.plan_version_id = pv.id
                LEFT JOIN subscription_plans sp ON pv.plan_id = sp.id
                WHERE t.id = ?
                """,
                (tenant_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
            
            result = dict(row)
            
            # If no plan assigned, use default Free plan limits
            if result.get("plan_version_id") is None:
                result["user_limit"] = 5
                result["monthly_scan_quota"] = 50
                result["daily_card_limit"] = 10
                result["batch_size_limit"] = 5
                result["plan_name"] = "free"
                result["plan_display_name"] = "Free (Default)"
            
            return result

    def get_quota_status(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get comprehensive quota status for a tenant.
        
        Returns:
            Dict with:
            - plan_name: Current plan name
            - user_limit: Maximum allowed LINE users
            - current_users: Current number of LINE users
            - has_user_capacity: Whether more users can be added
            - monthly_scan_quota: Scans allowed per month (from plan)
            - bonus_scan_quota: Extra purchased scans
            - total_scan_quota: Total available scans
            - current_month_scans: Scans used this month
            - remaining_scans: Scans remaining
            - has_scan_quota: Whether scans are available
            - quota_reset_date: When monthly quota resets
        """
        limits = self.get_tenant_limits(tenant_id)
        if not limits:
            return {"error": "Tenant not found"}
        
        # Get current user count
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM line_users WHERE tenant_id = ?",
                (tenant_id,)
            )
            current_users = cursor.fetchone()[0]
        
        monthly_quota = limits.get("monthly_scan_quota") or 50
        bonus_quota = limits.get("bonus_scan_quota") or 0
        current_scans = limits.get("current_month_scans") or 0
        total_quota = monthly_quota + bonus_quota
        remaining_scans = max(0, total_quota - current_scans)
        
        user_limit = limits.get("user_limit")
        has_user_capacity = user_limit is None or current_users < user_limit
        
        return {
            "plan_name": limits.get("plan_name", "free"),
            "plan_display_name": limits.get("plan_display_name", "Free"),
            "user_limit": user_limit,
            "current_users": current_users,
            "has_user_capacity": has_user_capacity,
            "monthly_scan_quota": monthly_quota,
            "bonus_scan_quota": bonus_quota,
            "total_scan_quota": total_quota,
            "current_month_scans": current_scans,
            "remaining_scans": remaining_scans,
            "has_scan_quota": remaining_scans > 0,
            "quota_reset_date": limits.get("quota_reset_date"),
            "daily_card_limit": limits.get("daily_card_limit", 10),
            "batch_size_limit": limits.get("batch_size_limit", 5),
        }

    def check_user_limit(self, tenant_id: str) -> Dict[str, Any]:
        """
        Check if a tenant can add more LINE users.
        
        Returns:
            Dict with:
            - allowed: Boolean indicating if new users can be added
            - current_users: Current user count
            - user_limit: Maximum allowed (None = unlimited)
            - message: Human-readable status message
        """
        status = self.get_quota_status(tenant_id)
        if "error" in status:
            return {"allowed": False, "message": status["error"]}
        
        allowed = status["has_user_capacity"]
        limit = status["user_limit"]
        current = status["current_users"]
        
        if allowed:
            if limit is None:
                message = f"目前有 {current} 位用戶 (無上限)"
            else:
                message = f"目前有 {current}/{limit} 位用戶"
        else:
            message = f"已達用戶上限 ({limit} 位)，請升級方案"
        
        return {
            "allowed": allowed,
            "current_users": current,
            "user_limit": limit,
            "message": message,
        }

    def check_scan_quota(self, tenant_id: str) -> Dict[str, Any]:
        """
        Check if a tenant has available scan quota.
        
        Returns:
            Dict with:
            - has_quota: Boolean indicating if scans are available
            - remaining_scans: Number of scans remaining
            - total_quota: Total quota (monthly + bonus)
            - message: Human-readable status message
        """
        # First, check if monthly reset is needed
        self._check_quota_reset(tenant_id)
        
        status = self.get_quota_status(tenant_id)
        if "error" in status:
            return {"has_quota": False, "message": status["error"]}
        
        has_quota = status["has_scan_quota"]
        remaining = status["remaining_scans"]
        total = status["total_scan_quota"]
        used = status["current_month_scans"]
        
        if has_quota:
            message = f"剩餘 {remaining}/{total} 張掃描配額"
        else:
            message = f"本月配額已用完 ({used}/{total})，請購買額外配額或等待下月重置"
        
        return {
            "has_quota": has_quota,
            "remaining_scans": remaining,
            "total_quota": total,
            "current_month_scans": used,
            "message": message,
        }

    def consume_scan(self, tenant_id: str, count: int = 1, _retry_count: int = 0) -> Dict[str, Any]:
        """
        Consume scan quota for a tenant using atomic operation.
        
        Uses UPDATE with WHERE clause to prevent race conditions in
        concurrent scenarios.
        
        Args:
            tenant_id: Tenant ID
            count: Number of scans to consume (default 1)
            _retry_count: Internal retry counter (do not set manually)
        
        Returns:
            Dict with:
            - success: Whether the consumption was successful
            - remaining_scans: Scans remaining after consumption
            - message: Status message
        """
        MAX_RETRIES = 3  # Prevent infinite recursion in race conditions
        
        # First, check if monthly reset is needed
        self._check_quota_reset(tenant_id)
        
        # Atomic update: only succeed if there's enough quota
        # This prevents race conditions in concurrent requests
        with self.db.get_connection() as conn:
            # Get current quota limits
            cursor = conn.execute(
                """
                SELECT 
                    t.current_month_scans,
                    t.bonus_scan_quota,
                    COALESCE(pv.monthly_scan_quota, 50) as monthly_scan_quota
                FROM tenants t
                LEFT JOIN plan_versions pv ON t.plan_version_id = pv.id
                WHERE t.id = ?
                """,
                (tenant_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return {
                    "success": False,
                    "remaining_scans": 0,
                    "message": "Tenant not found",
                }
            
            current_scans = row["current_month_scans"] or 0
            bonus_quota = row["bonus_scan_quota"] or 0
            monthly_quota = row["monthly_scan_quota"] or 50
            total_quota = monthly_quota + bonus_quota
            remaining_before = total_quota - current_scans
            
            if remaining_before < count:
                return {
                    "success": False,
                    "remaining_scans": max(0, remaining_before),
                    "message": f"配額不足，需要 {count} 張但只剩 {remaining_before} 張",
                }
            
            # Atomic update with condition check
            # Only updates if the current_month_scans hasn't changed
            cursor = conn.execute(
                """
                UPDATE tenants 
                SET current_month_scans = COALESCE(current_month_scans, 0) + ?
                WHERE id = ? 
                  AND COALESCE(current_month_scans, 0) = ?
                """,
                (count, tenant_id, current_scans)
            )
            
            # Check if update succeeded (row was actually modified)
            if cursor.rowcount == 0:
                # Someone else modified it - retry with fresh data
                if _retry_count >= MAX_RETRIES:
                    logger.error(
                        "Quota consumption failed after max retries",
                        tenant_id=tenant_id,
                        retry_count=_retry_count,
                    )
                    return {
                        "success": False,
                        "remaining_scans": remaining_before,
                        "message": "配額操作失敗，請稍後重試",
                    }
                
                logger.warning(
                    "Quota consumption retry",
                    tenant_id=tenant_id,
                    retry_count=_retry_count + 1,
                    reason="concurrent_modification",
                )
                # Retry with incremented counter
                return self.consume_scan(tenant_id, count, _retry_count + 1)
            
            new_remaining = remaining_before - count
        
        logger.info(
            "Scan quota consumed",
            tenant_id=tenant_id,
            count=count,
            remaining=new_remaining,
        )
        
        return {
            "success": True,
            "remaining_scans": new_remaining,
            "message": f"已使用 {count} 張配額，剩餘 {new_remaining} 張",
        }

    def _check_quota_reset(self, tenant_id: str):
        """
        Check if quota reset is needed based on tenant's reset cycle configuration.
        
        Supports three cycles:
        - daily: Reset every day at midnight
        - weekly: Reset on specific weekday (1=Monday to 7=Sunday)
        - monthly: Reset on specific day of month (1-28)
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """SELECT quota_reset_date, current_month_scans, 
                          quota_reset_cycle, quota_reset_day 
                   FROM tenants WHERE id = ?""",
                (tenant_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return
            
            reset_date = row["quota_reset_date"]
            cycle = row["quota_reset_cycle"] or "monthly"
            reset_day = row["quota_reset_day"] or 1
            now = datetime.now()
            
            should_reset = False
            new_reset_date = None
            
            if cycle == "daily":
                # Reset every day - check if reset_date is not today
                today = now.strftime("%Y-%m-%d")
                if not reset_date or reset_date != today:
                    should_reset = True
                    new_reset_date = today
                    
            elif cycle == "weekly":
                # Reset on specific weekday (1=Monday to 7=Sunday)
                # Python's weekday(): 0=Monday to 6=Sunday
                current_weekday = now.weekday() + 1  # Convert to 1-7
                
                # Calculate the start of the current week's reset period
                days_since_reset_day = (current_weekday - reset_day) % 7
                week_start = now - timedelta(days=days_since_reset_day)
                week_start_str = week_start.strftime("%Y-%m-%d")
                
                if not reset_date or reset_date < week_start_str:
                    should_reset = True
                    new_reset_date = week_start_str
                    
            else:  # monthly (default)
                # Reset on specific day of month
                current_month = now.strftime("%Y-%m")
                
                # Determine the reset date for current month
                # Use min(reset_day, last_day_of_month) for safety
                last_day = 28  # Safe default
                try:
                    if now.month == 12:
                        next_month = now.replace(year=now.year + 1, month=1, day=1)
                    else:
                        next_month = now.replace(month=now.month + 1, day=1)
                    last_day = (next_month - timedelta(days=1)).day
                except ValueError:
                    pass
                
                effective_reset_day = min(reset_day, last_day)
                month_reset_date = f"{current_month}-{effective_reset_day:02d}"
                
                # Reset if no reset date or if we've passed the reset day this month
                if not reset_date or reset_date < month_reset_date:
                    if now.day >= effective_reset_day:
                        should_reset = True
                        new_reset_date = month_reset_date
            
            if should_reset and new_reset_date:
                old_scans = row["current_month_scans"] or 0
                
                conn.execute(
                    """
                    UPDATE tenants 
                    SET current_month_scans = 0, quota_reset_date = ?
                    WHERE id = ?
                    """,
                    (new_reset_date, tenant_id)
                )
                
                logger.info(
                    "Quota reset performed",
                    tenant_id=tenant_id,
                    cycle=cycle,
                    old_scans=old_scans,
                    reset_date=new_reset_date,
                )

    def add_bonus_quota(
        self,
        tenant_id: str,
        amount: int,
        description: str = "購買配額包",
        payment_reference: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Add bonus scan quota to a tenant.
        
        Args:
            tenant_id: Tenant ID
            amount: Quota amount to add
            description: Description for the transaction
            payment_reference: Optional payment reference
            created_by: Admin ID or 'system'
        
        Returns:
            Dict with transaction details and new balance
        """
        with self.db.get_connection() as conn:
            # Get current bonus quota
            cursor = conn.execute(
                "SELECT bonus_scan_quota FROM tenants WHERE id = ?",
                (tenant_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return {"success": False, "message": "Tenant not found"}
            
            old_balance = row["bonus_scan_quota"] or 0
            new_balance = old_balance + amount
            
            # Update tenant's bonus quota
            conn.execute(
                "UPDATE tenants SET bonus_scan_quota = ? WHERE id = ?",
                (new_balance, tenant_id)
            )
            
            # Record transaction
            transaction_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO quota_transactions 
                (id, tenant_id, transaction_type, quota_amount, balance_after, 
                 description, payment_reference, created_by)
                VALUES (?, ?, 'purchase', ?, ?, ?, ?, ?)
                """,
                (
                    transaction_id,
                    tenant_id,
                    amount,
                    new_balance,
                    description,
                    payment_reference,
                    created_by or "admin",
                )
            )
        
        logger.info(
            "Bonus quota added",
            tenant_id=tenant_id,
            amount=amount,
            new_balance=new_balance,
            transaction_id=transaction_id,
        )
        
        return {
            "success": True,
            "transaction_id": transaction_id,
            "amount_added": amount,
            "old_balance": old_balance,
            "new_balance": new_balance,
            "message": f"已新增 {amount} 張配額，餘額: {new_balance} 張",
        }

    def get_quota_transactions(
        self,
        tenant_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get quota transaction history for a tenant.
        
        Args:
            tenant_id: Tenant ID
            limit: Maximum number of transactions to return
        
        Returns:
            List of transaction records
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM quota_transactions
                WHERE tenant_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (tenant_id, limit)
            )
            return [dict(row) for row in cursor.fetchall()]


# Global service instance
_service_instance: Optional[QuotaService] = None


def get_quota_service() -> QuotaService:
    """Get or create the global QuotaService instance"""
    global _service_instance
    if _service_instance is None:
        _service_instance = QuotaService()
    return _service_instance
