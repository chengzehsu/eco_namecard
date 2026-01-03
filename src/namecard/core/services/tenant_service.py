"""
Tenant Service for Multi-Tenant System

Manages tenant configurations with encryption, caching, and CRUD operations.
"""

import re
import os
import base64
import time
from datetime import datetime
from typing import Optional, List, Dict, Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import structlog

from src.namecard.core.models.tenant import (
    TenantConfig,
    TenantCreateRequest,
    TenantUpdateRequest,
)
from src.namecard.infrastructure.storage.tenant_db import TenantDatabase, get_tenant_db

logger = structlog.get_logger()


class TenantService:
    """
    Service for managing tenant configurations.

    Features:
    - Credential encryption using Fernet
    - In-memory caching with TTL
    - CRUD operations for tenants
    """

    # Cache TTL in seconds
    CACHE_TTL = 300  # 5 minutes

    def __init__(self, db: Optional[TenantDatabase] = None):
        """
        Initialize the tenant service.

        Args:
            db: TenantDatabase instance. If None, uses global instance.
        """
        self.db = db or get_tenant_db()
        self._cipher = self._create_cipher()

        # In-memory cache: {cache_key: (data, timestamp)}
        self._cache: Dict[str, tuple] = {}

        logger.info("TenantService initialized")

    def _create_cipher(self) -> Fernet:
        """Create Fernet cipher from SECRET_KEY"""
        secret_key = os.environ.get("SECRET_KEY", "default-secret-key-change-me")

        # Derive a 32-byte key from SECRET_KEY using PBKDF2
        salt = b"tenant_service_salt_2024"
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(secret_key.encode("utf-8")))
        return Fernet(key)

    def _encrypt(self, plaintext: str) -> str:
        """Encrypt a string"""
        if not plaintext:
            return ""
        encrypted = self._cipher.encrypt(plaintext.encode("utf-8"))
        return base64.urlsafe_b64encode(encrypted).decode("utf-8")

    def _decrypt(self, ciphertext: str) -> str:
        """Decrypt a string"""
        if not ciphertext:
            return ""
        try:
            encrypted = base64.urlsafe_b64decode(ciphertext.encode("utf-8"))
            decrypted = self._cipher.decrypt(encrypted)
            return decrypted.decode("utf-8")
        except Exception as e:
            logger.error("Decryption failed", error=str(e))
            return ""

    def _generate_slug(self, name: str) -> str:
        """Generate URL-friendly slug from name"""
        # Convert to lowercase and replace spaces/special chars with hyphens
        slug = name.lower().strip()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[\s_]+", "-", slug)
        slug = re.sub(r"-+", "-", slug).strip("-")

        # Ensure uniqueness
        base_slug = slug or "tenant"
        counter = 0
        while True:
            test_slug = f"{base_slug}-{counter}" if counter > 0 else base_slug
            if not self.db.get_tenant_by_slug(test_slug):
                return test_slug
            counter += 1

    def _get_cache(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
        if key in self._cache:
            data, timestamp = self._cache[key]
            if time.time() - timestamp < self.CACHE_TTL:
                return data
            else:
                del self._cache[key]
        return None

    def _set_cache(self, key: str, data: Any):
        """Set value in cache"""
        self._cache[key] = (data, time.time())

    def _invalidate_cache(self, tenant_id: Optional[str] = None):
        """Invalidate cache for a tenant or all tenants"""
        if tenant_id:
            keys_to_delete = [k for k in self._cache if tenant_id in k]
            for key in keys_to_delete:
                del self._cache[key]
        else:
            self._cache.clear()

    def _row_to_config(self, row: Dict[str, Any]) -> TenantConfig:
        """Convert database row to TenantConfig with decrypted credentials"""
        return TenantConfig(
            id=row["id"],
            name=row["name"],
            slug=row["slug"],
            is_active=bool(row["is_active"]),
            created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else datetime.now(),
            updated_at=datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else datetime.now(),
            line_channel_id=row["line_channel_id"],
            line_channel_access_token=self._decrypt(row["line_channel_access_token_encrypted"]),
            line_channel_secret=self._decrypt(row["line_channel_secret_encrypted"]),
            notion_api_key=self._decrypt(row["notion_api_key_encrypted"]),
            notion_database_id=row["notion_database_id"],
            use_shared_notion_api=bool(row.get("use_shared_notion_api", 1)),
            google_api_key=self._decrypt(row["google_api_key_encrypted"]) if row.get("google_api_key_encrypted") else None,
            use_shared_google_api=bool(row.get("use_shared_google_api", 1)),
            daily_card_limit=row.get("daily_card_limit", 50),
            batch_size_limit=row.get("batch_size_limit", 10),
        )

    # ==================== Public API ====================

    def create_tenant(self, request: TenantCreateRequest) -> TenantConfig:
        """
        Create a new tenant.

        Args:
            request: TenantCreateRequest with configuration

        Returns:
            Created TenantConfig
        """
        # Generate slug if not provided
        slug = request.slug or self._generate_slug(request.name)

        # Prepare encrypted data
        data = {
            "name": request.name,
            "slug": slug,
            "is_active": True,
            "line_channel_id": request.line_channel_id,
            "line_channel_access_token_encrypted": self._encrypt(request.line_channel_access_token),
            "line_channel_secret_encrypted": self._encrypt(request.line_channel_secret),
            "notion_api_key_encrypted": self._encrypt(request.notion_api_key) if request.notion_api_key else "",
            "notion_database_id": request.notion_database_id,
            "use_shared_notion_api": request.use_shared_notion_api,
            "google_api_key_encrypted": self._encrypt(request.google_api_key) if request.google_api_key else None,
            "use_shared_google_api": request.use_shared_google_api,
            "daily_card_limit": request.daily_card_limit,
            "batch_size_limit": request.batch_size_limit,
        }

        row = self.db.create_tenant(data)
        tenant = self._row_to_config(row)

        logger.info("Tenant created", tenant_id=tenant.id, name=tenant.name)
        return tenant

    def get_tenant_by_id(self, tenant_id: str) -> Optional[TenantConfig]:
        """Get tenant by ID (with caching)"""
        cache_key = f"tenant:id:{tenant_id}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        row = self.db.get_tenant_by_id(tenant_id)
        if not row:
            return None

        tenant = self._row_to_config(row)
        self._set_cache(cache_key, tenant)
        return tenant

    def get_tenant_by_channel_id(self, channel_id: str) -> Optional[TenantConfig]:
        """Get tenant by LINE Channel ID (with caching)"""
        cache_key = f"tenant:channel:{channel_id}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        row = self.db.get_tenant_by_channel_id(channel_id)
        if not row:
            return None

        tenant = self._row_to_config(row)
        self._set_cache(cache_key, tenant)
        # Also cache by ID for cross-reference
        self._set_cache(f"tenant:id:{tenant.id}", tenant)
        return tenant

    def get_tenant_by_slug(self, slug: str) -> Optional[TenantConfig]:
        """Get tenant by slug"""
        cache_key = f"tenant:slug:{slug}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        row = self.db.get_tenant_by_slug(slug)
        if not row:
            return None

        tenant = self._row_to_config(row)
        self._set_cache(cache_key, tenant)
        return tenant

    def list_tenants(self, include_inactive: bool = False) -> List[TenantConfig]:
        """List all tenants"""
        rows = self.db.list_tenants(include_inactive=include_inactive)
        return [self._row_to_config(row) for row in rows]

    def update_tenant(self, tenant_id: str, request: TenantUpdateRequest) -> Optional[TenantConfig]:
        """
        Update tenant configuration.

        Args:
            tenant_id: Tenant ID
            request: Fields to update

        Returns:
            Updated TenantConfig or None if not found
        """
        # Build update data
        data = {}

        if request.name is not None:
            data["name"] = request.name
        if request.is_active is not None:
            data["is_active"] = request.is_active
        if request.line_channel_access_token is not None:
            data["line_channel_access_token_encrypted"] = self._encrypt(request.line_channel_access_token)
        if request.line_channel_secret is not None:
            data["line_channel_secret_encrypted"] = self._encrypt(request.line_channel_secret)
        if request.notion_api_key is not None:
            data["notion_api_key_encrypted"] = self._encrypt(request.notion_api_key)
        if request.notion_database_id is not None:
            data["notion_database_id"] = request.notion_database_id
        if request.use_shared_notion_api is not None:
            data["use_shared_notion_api"] = request.use_shared_notion_api
        if request.google_api_key is not None:
            data["google_api_key_encrypted"] = self._encrypt(request.google_api_key) if request.google_api_key else None
        if request.use_shared_google_api is not None:
            data["use_shared_google_api"] = request.use_shared_google_api
        if request.daily_card_limit is not None:
            data["daily_card_limit"] = request.daily_card_limit
        if request.batch_size_limit is not None:
            data["batch_size_limit"] = request.batch_size_limit

        row = self.db.update_tenant(tenant_id, data)
        if not row:
            return None

        # Invalidate cache
        self._invalidate_cache(tenant_id)

        tenant = self._row_to_config(row)
        logger.info("Tenant updated", tenant_id=tenant_id)
        return tenant

    def delete_tenant(self, tenant_id: str, soft_delete: bool = True) -> bool:
        """
        Delete a tenant.

        Args:
            tenant_id: Tenant ID
            soft_delete: If True, just deactivate. If False, permanently delete.

        Returns:
            True if deleted, False if not found
        """
        result = self.db.delete_tenant(tenant_id, soft_delete=soft_delete)
        if result:
            self._invalidate_cache(tenant_id)
            logger.info("Tenant deleted", tenant_id=tenant_id, soft_delete=soft_delete)
        return result

    def record_usage(self, tenant_id: str, cards_processed: int = 0,
                     cards_saved: int = 0, api_calls: int = 0, errors: int = 0):
        """Record usage statistics"""
        self.db.record_usage(
            tenant_id=tenant_id,
            cards_processed=cards_processed,
            cards_saved=cards_saved,
            api_calls=api_calls,
            errors=errors
        )

    def get_tenant_stats(self, tenant_id: str, days: int = 30) -> List[Dict[str, Any]]:
        """Get usage stats for a tenant"""
        return self.db.get_tenant_stats(tenant_id, days)

    def get_overall_stats(self) -> Dict[str, Any]:
        """Get overall statistics"""
        return self.db.get_overall_stats()

    def get_today_stats_by_tenant(self) -> Dict[str, Dict[str, int]]:
        """Get today's usage stats for all tenants"""
        return self.db.get_today_stats_by_tenant()

    # ==================== Extended Statistics ====================

    def record_user_usage(self, tenant_id: str, line_user_id: str,
                          cards_processed: int = 0, cards_saved: int = 0, errors: int = 0):
        """Record usage statistics for a specific user"""
        self.db.record_user_usage(
            tenant_id=tenant_id,
            line_user_id=line_user_id,
            cards_processed=cards_processed,
            cards_saved=cards_saved,
            errors=errors
        )

    def get_tenant_monthly_stats(self, tenant_id: str, months: int = 12) -> List[Dict[str, Any]]:
        """Get monthly aggregated stats for a tenant"""
        return self.db.get_tenant_stats_monthly(tenant_id, months)

    def get_tenant_yearly_stats(self, tenant_id: str, years: int = 3) -> List[Dict[str, Any]]:
        """Get yearly aggregated stats for a tenant"""
        return self.db.get_tenant_stats_yearly(tenant_id, years)

    def get_tenant_stats_by_range(self, tenant_id: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """Get stats for a tenant within a date range"""
        return self.db.get_tenant_stats_range(tenant_id, start_date, end_date)

    def get_tenant_stats_summary(self, tenant_id: str, days: int = 30) -> Dict[str, Any]:
        """
        Get comprehensive summary statistics for a tenant.

        Returns dict with:
        - total_processed, total_saved, total_errors, total_api_calls
        - active_days, avg_daily_processed
        - success_rate, error_rate (calculated percentages)
        """
        return self.db.get_tenant_stats_summary(tenant_id, days)

    def get_tenant_users_stats(self, tenant_id: str, days: int = 30) -> List[Dict[str, Any]]:
        """Get aggregated stats for all users of a tenant"""
        return self.db.get_tenant_users_stats(tenant_id, days)

    def get_top_users(self, tenant_id: str, limit: int = 10, days: int = 30) -> List[Dict[str, Any]]:
        """Get top users by usage for a tenant"""
        return self.db.get_top_users(tenant_id, limit, days)

    def get_user_count(self, tenant_id: str, days: int = 30) -> int:
        """Get count of unique users for a tenant"""
        return self.db.get_user_count_by_tenant(tenant_id, days)

    def get_all_tenants_summary(self, days: int = 30) -> Dict[str, Any]:
        """Get summary statistics across all tenants"""
        return self.db.get_all_tenants_summary(days)

    # ==================== Auto-Activation Support ====================

    def get_pending_tenants(self) -> List[TenantConfig]:
        """
        Get all pending (inactive) tenants that can be auto-activated.

        These are tenants that have been created but not yet activated
        because their line_channel_id hasn't been confirmed.

        Returns:
            List of inactive TenantConfig objects
        """
        rows = self.db.list_tenants(include_inactive=True)
        pending = []
        for row in rows:
            # Pending tenants are those that are inactive OR have placeholder channel_id
            if not row["is_active"] or (row["line_channel_id"] and row["line_channel_id"].startswith("pending_")):
                pending.append(self._row_to_config(row))
        logger.info("get_pending_tenants called", total_tenants=len(rows), pending_count=len(pending))
        return pending

    def activate_tenant_with_channel_id(self, tenant_id: str, channel_id: str) -> Optional[TenantConfig]:
        """
        Activate a tenant and bind it to a specific LINE channel ID.

        This is used during auto-activation when a webhook is received
        from an unknown channel that matches a pending tenant's signature.

        Args:
            tenant_id: The tenant ID to activate
            channel_id: The LINE Bot User ID (destination) to bind

        Returns:
            Updated TenantConfig or None if not found
        """
        # Update the tenant with the new channel_id and activate it
        data = {
            "is_active": True,
            "line_channel_id": channel_id,
        }

        row = self.db.update_tenant(tenant_id, data)
        if not row:
            return None

        # Invalidate cache
        self._invalidate_cache(tenant_id)

        tenant = self._row_to_config(row)
        logger.info("Tenant activated with channel_id",
                   tenant_id=tenant_id,
                   channel_id=channel_id[:10] + "...")
        return tenant


# Global service instance
_service_instance: Optional[TenantService] = None


def get_tenant_service() -> TenantService:
    """Get or create the global TenantService instance"""
    global _service_instance
    if _service_instance is None:
        _service_instance = TenantService()
    return _service_instance


def create_tenant_service(db: Optional[TenantDatabase] = None) -> TenantService:
    """Create a new TenantService instance"""
    global _service_instance
    _service_instance = TenantService(db)
    return _service_instance
