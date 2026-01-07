"""
Subscription Service for Multi-Tenant Commercialization

Manages subscription plans, plan versions, and tenant plan assignments.
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import structlog

from src.namecard.infrastructure.storage.tenant_db import TenantDatabase, get_tenant_db

logger = structlog.get_logger()


class SubscriptionService:
    """
    Service for managing subscription plans and versions.
    
    Features:
    - Plan CRUD operations
    - Version control for plan changes (grandfathering)
    - Assign plans to tenants
    - Renew subscriptions with latest version
    """

    def __init__(self, db: Optional[TenantDatabase] = None):
        """
        Initialize the subscription service.
        
        Args:
            db: TenantDatabase instance. If None, uses global instance.
        """
        self.db = db or get_tenant_db()
        logger.info("SubscriptionService initialized")

    # ==================== Plan Operations ====================

    def list_plans(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """
        List all subscription plans with their current versions.
        
        Args:
            include_inactive: Include inactive plans
        
        Returns:
            List of plans with current version details
        """
        with self.db.get_connection() as conn:
            query = """
                SELECT 
                    sp.*,
                    pv.id as current_version_id,
                    pv.version_number,
                    pv.user_limit,
                    pv.monthly_scan_quota,
                    pv.daily_card_limit,
                    pv.batch_size_limit,
                    pv.price_monthly,
                    pv.price_yearly,
                    pv.effective_from
                FROM subscription_plans sp
                LEFT JOIN plan_versions pv ON sp.id = pv.plan_id AND pv.is_current = 1
            """
            if not include_inactive:
                query += " WHERE sp.is_active = 1"
            query += " ORDER BY sp.sort_order"
            
            cursor = conn.execute(query)
            return [dict(row) for row in cursor.fetchall()]

    def get_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a plan with its current version details.
        
        Args:
            plan_id: Plan ID or name
        
        Returns:
            Plan dict with current version details, or None
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT 
                    sp.*,
                    pv.id as current_version_id,
                    pv.version_number,
                    pv.user_limit,
                    pv.monthly_scan_quota,
                    pv.daily_card_limit,
                    pv.batch_size_limit,
                    pv.price_monthly,
                    pv.price_yearly,
                    pv.effective_from
                FROM subscription_plans sp
                LEFT JOIN plan_versions pv ON sp.id = pv.plan_id AND pv.is_current = 1
                WHERE sp.id = ? OR sp.name = ?
                """,
                (plan_id, plan_id)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_plan_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific plan version.
        
        Args:
            version_id: Plan version ID
        
        Returns:
            Version dict with plan details, or None
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT 
                    pv.*,
                    sp.name as plan_name,
                    sp.display_name as plan_display_name
                FROM plan_versions pv
                JOIN subscription_plans sp ON pv.plan_id = sp.id
                WHERE pv.id = ?
                """,
                (version_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_plan_versions(self, plan_id: str) -> List[Dict[str, Any]]:
        """
        Get all versions of a plan.
        
        Args:
            plan_id: Plan ID
        
        Returns:
            List of version dicts ordered by version number descending
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM plan_versions
                WHERE plan_id = ?
                ORDER BY version_number DESC
                """,
                (plan_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def create_plan_version(
        self,
        plan_id: str,
        user_limit: Optional[int] = None,
        monthly_scan_quota: int = 50,
        daily_card_limit: int = 10,
        batch_size_limit: int = 5,
        price_monthly: int = 0,
        price_yearly: Optional[int] = None,
        effective_from: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new version of a plan.
        
        This is the core mechanism for grandfathering - existing tenants
        keep their current version, new tenants get the new version.
        
        Args:
            plan_id: Plan ID to create new version for
            user_limit: Maximum LINE users (None = unlimited)
            monthly_scan_quota: Scans per month
            daily_card_limit: Scans per user per day
            batch_size_limit: Cards per batch
            price_monthly: Monthly price in TWD cents
            price_yearly: Optional yearly price in TWD cents
            effective_from: When version becomes effective (default: now)
        
        Returns:
            Dict with new version details
        """
        with self.db.get_connection() as conn:
            # Get current max version number
            cursor = conn.execute(
                "SELECT MAX(version_number) FROM plan_versions WHERE plan_id = ?",
                (plan_id,)
            )
            max_version = cursor.fetchone()[0] or 0
            new_version_number = max_version + 1
            
            # Set old current version to not current
            conn.execute(
                "UPDATE plan_versions SET is_current = 0 WHERE plan_id = ? AND is_current = 1",
                (plan_id,)
            )
            
            # Create new version
            version_id = str(uuid.uuid4())
            effective = effective_from or datetime.now().isoformat()
            
            conn.execute(
                """
                INSERT INTO plan_versions 
                (id, plan_id, version_number, user_limit, monthly_scan_quota,
                 daily_card_limit, batch_size_limit, price_monthly, price_yearly,
                 is_current, effective_from)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    version_id,
                    plan_id,
                    new_version_number,
                    user_limit,
                    monthly_scan_quota,
                    daily_card_limit,
                    batch_size_limit,
                    price_monthly,
                    price_yearly,
                    effective,
                )
            )
        
        logger.info(
            "Plan version created",
            plan_id=plan_id,
            version_id=version_id,
            version_number=new_version_number,
        )
        
        return {
            "id": version_id,
            "plan_id": plan_id,
            "version_number": new_version_number,
            "user_limit": user_limit,
            "monthly_scan_quota": monthly_scan_quota,
            "daily_card_limit": daily_card_limit,
            "batch_size_limit": batch_size_limit,
            "price_monthly": price_monthly,
            "price_yearly": price_yearly,
            "effective_from": effective,
        }

    def update_plan(
        self,
        plan_id: str,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        is_active: Optional[bool] = None,
        sort_order: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Update plan metadata (not version-controlled parameters).
        
        For updating limits/prices, use create_plan_version instead.
        
        Args:
            plan_id: Plan ID
            display_name: New display name
            description: New description
            is_active: Active status
            sort_order: Display order
        
        Returns:
            Updated plan dict or None if not found
        """
        updates = []
        values = []
        
        if display_name is not None:
            updates.append("display_name = ?")
            values.append(display_name)
        if description is not None:
            updates.append("description = ?")
            values.append(description)
        if is_active is not None:
            updates.append("is_active = ?")
            values.append(1 if is_active else 0)
        if sort_order is not None:
            updates.append("sort_order = ?")
            values.append(sort_order)
        
        if not updates:
            return self.get_plan(plan_id)
        
        values.append(plan_id)
        
        with self.db.get_connection() as conn:
            conn.execute(
                f"UPDATE subscription_plans SET {', '.join(updates)} WHERE id = ?",
                values
            )
        
        logger.info("Plan updated", plan_id=plan_id)
        return self.get_plan(plan_id)

    # ==================== Tenant Plan Assignment ====================

    def assign_plan(
        self,
        tenant_id: str,
        plan_id: str,
        duration_months: int = 1,
    ) -> Dict[str, Any]:
        """
        Assign a plan to a tenant.
        
        The tenant will be bound to the current version of the plan.
        
        Args:
            tenant_id: Tenant ID
            plan_id: Plan ID or name
            duration_months: Subscription duration in months
        
        Returns:
            Dict with assignment details
        """
        plan = self.get_plan(plan_id)
        if not plan:
            return {"success": False, "message": f"Plan not found: {plan_id}"}
        
        current_version_id = plan.get("current_version_id")
        if not current_version_id:
            return {"success": False, "message": f"Plan has no active version: {plan_id}"}
        
        now = datetime.now()
        expires_at = now + timedelta(days=duration_months * 30)
        
        with self.db.get_connection() as conn:
            conn.execute(
                """
                UPDATE tenants 
                SET plan_version_id = ?,
                    plan_started_at = ?,
                    plan_expires_at = ?,
                    next_plan_version_id = NULL
                WHERE id = ?
                """,
                (
                    current_version_id,
                    now.isoformat(),
                    expires_at.isoformat(),
                    tenant_id,
                )
            )
        
        logger.info(
            "Plan assigned to tenant",
            tenant_id=tenant_id,
            plan_id=plan_id,
            version_id=current_version_id,
            expires_at=expires_at.isoformat(),
        )
        
        return {
            "success": True,
            "tenant_id": tenant_id,
            "plan_id": plan_id,
            "plan_name": plan.get("display_name"),
            "version_id": current_version_id,
            "version_number": plan.get("version_number"),
            "started_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "message": f"已指派 {plan.get('display_name')} 方案 (v{plan.get('version_number')})",
        }

    def renew_subscription(self, tenant_id: str, duration_months: int = 1) -> Dict[str, Any]:
        """
        Renew a tenant's subscription with the latest plan version.
        
        This is where grandfathering ends - the tenant gets the current
        version of their plan with any updated limits/pricing.
        
        Args:
            tenant_id: Tenant ID
            duration_months: New subscription duration
        
        Returns:
            Dict with renewal details
        """
        with self.db.get_connection() as conn:
            # Get tenant's current plan
            cursor = conn.execute(
                """
                SELECT 
                    t.plan_version_id,
                    pv.plan_id
                FROM tenants t
                LEFT JOIN plan_versions pv ON t.plan_version_id = pv.id
                WHERE t.id = ?
                """,
                (tenant_id,)
            )
            row = cursor.fetchone()
            
            if not row or not row["plan_id"]:
                return {"success": False, "message": "Tenant has no assigned plan"}
            
            plan_id = row["plan_id"]
        
        # Get current version of the plan
        plan = self.get_plan(plan_id)
        if not plan or not plan.get("current_version_id"):
            return {"success": False, "message": "Plan not found or has no current version"}
        
        new_version_id = plan["current_version_id"]
        now = datetime.now()
        expires_at = now + timedelta(days=duration_months * 30)
        
        with self.db.get_connection() as conn:
            conn.execute(
                """
                UPDATE tenants 
                SET plan_version_id = ?,
                    plan_started_at = ?,
                    plan_expires_at = ?,
                    next_plan_version_id = NULL
                WHERE id = ?
                """,
                (new_version_id, now.isoformat(), expires_at.isoformat(), tenant_id)
            )
        
        logger.info(
            "Subscription renewed",
            tenant_id=tenant_id,
            plan_id=plan_id,
            new_version_id=new_version_id,
        )
        
        return {
            "success": True,
            "tenant_id": tenant_id,
            "plan_id": plan_id,
            "plan_name": plan.get("display_name"),
            "version_id": new_version_id,
            "version_number": plan.get("version_number"),
            "started_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "message": f"已續約 {plan.get('display_name')} 方案並套用最新版本 (v{plan.get('version_number')})",
        }

    def get_tenant_subscription(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a tenant's current subscription details.
        
        Args:
            tenant_id: Tenant ID
        
        Returns:
            Dict with subscription details or None
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT 
                    t.id as tenant_id,
                    t.name as tenant_name,
                    t.plan_version_id,
                    t.plan_started_at,
                    t.plan_expires_at,
                    t.next_plan_version_id,
                    pv.version_number,
                    pv.user_limit,
                    pv.monthly_scan_quota,
                    pv.daily_card_limit,
                    pv.batch_size_limit,
                    pv.price_monthly,
                    sp.id as plan_id,
                    sp.name as plan_name,
                    sp.display_name as plan_display_name,
                    cpv.version_number as current_version_number
                FROM tenants t
                LEFT JOIN plan_versions pv ON t.plan_version_id = pv.id
                LEFT JOIN subscription_plans sp ON pv.plan_id = sp.id
                LEFT JOIN plan_versions cpv ON sp.id = cpv.plan_id AND cpv.is_current = 1
                WHERE t.id = ?
                """,
                (tenant_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
            
            result = dict(row)
            
            # Check if update is available
            if result.get("version_number") and result.get("current_version_number"):
                result["update_available"] = (
                    result["current_version_number"] > result["version_number"]
                )
            else:
                result["update_available"] = False
            
            # Check if expired
            if result.get("plan_expires_at"):
                expires = datetime.fromisoformat(result["plan_expires_at"])
                result["is_expired"] = expires < datetime.now()
                result["days_until_expiry"] = (expires - datetime.now()).days
            else:
                result["is_expired"] = False
                result["days_until_expiry"] = None
            
            return result


# Global service instance
_service_instance: Optional[SubscriptionService] = None


def get_subscription_service() -> SubscriptionService:
    """Get or create the global SubscriptionService instance"""
    global _service_instance
    if _service_instance is None:
        _service_instance = SubscriptionService()
    return _service_instance
