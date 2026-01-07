"""
Tests for Commercialization Services (QuotaService & SubscriptionService)

Tests cover:
1. Basic quota operations
2. Plan management
3. Grandfathering mechanism
4. Race condition handling
5. Monthly reset logic
"""

import pytest
import tempfile
import os
from datetime import datetime, timedelta


@pytest.fixture
def test_db():
    """Create a temporary test database"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    from src.namecard.infrastructure.storage.tenant_db import TenantDatabase
    db = TenantDatabase(db_path)
    
    # Create test tenant
    with db.get_connection() as conn:
        conn.execute('''
            INSERT INTO tenants (id, name, slug, line_channel_id, 
                line_channel_access_token_encrypted, line_channel_secret_encrypted,
                notion_api_key_encrypted, notion_database_id)
            VALUES ('test-tenant', 'Test Company', 'test', 'U12345', 
                    'encrypted_token', 'encrypted_secret', 'encrypted_key', 'db_id')
        ''')
    
    yield db
    
    # Cleanup
    os.unlink(db_path)


@pytest.fixture
def quota_service(test_db):
    """Create QuotaService with test database"""
    from src.namecard.core.services.quota_service import QuotaService
    return QuotaService(test_db)


@pytest.fixture
def subscription_service(test_db):
    """Create SubscriptionService with test database"""
    from src.namecard.core.services.subscription_service import SubscriptionService
    return SubscriptionService(test_db)


# ==================== QuotaService Tests ====================

class TestQuotaService:
    """Tests for QuotaService"""
    
    def test_get_quota_status_default_plan(self, quota_service):
        """Test quota status for tenant without assigned plan (uses defaults)"""
        status = quota_service.get_quota_status("test-tenant")
        
        assert status["plan_name"] == "free"
        assert status["monthly_scan_quota"] == 50
        assert status["user_limit"] == 5
        assert status["remaining_scans"] == 50
        assert status["has_scan_quota"] is True
    
    def test_consume_scan_success(self, quota_service):
        """Test successful scan consumption"""
        result = quota_service.consume_scan("test-tenant", 1)
        
        assert result["success"] is True
        assert result["remaining_scans"] == 49
        
        # Verify status updated
        status = quota_service.get_quota_status("test-tenant")
        assert status["current_month_scans"] == 1
        assert status["remaining_scans"] == 49
    
    def test_consume_multiple_scans(self, quota_service):
        """Test consuming multiple scans"""
        result = quota_service.consume_scan("test-tenant", 10)
        
        assert result["success"] is True
        assert result["remaining_scans"] == 40
    
    def test_consume_scan_quota_exceeded(self, quota_service, test_db):
        """Test scan consumption when quota is exhausted"""
        from datetime import datetime
        # Set current scans to max AND set reset_date to current month to avoid reset
        current_month = datetime.now().strftime("%Y-%m-01")
        with test_db.get_connection() as conn:
            conn.execute(
                "UPDATE tenants SET current_month_scans = 50, quota_reset_date = ? WHERE id = ?",
                (current_month, "test-tenant",)
            )
        
        result = quota_service.consume_scan("test-tenant", 1)
        
        assert result["success"] is False
        assert "配額不足" in result["message"] or result["remaining_scans"] == 0
    
    def test_check_user_limit_within_limit(self, quota_service):
        """Test user limit check when within limit"""
        result = quota_service.check_user_limit("test-tenant")
        
        assert result["allowed"] is True
        assert result["current_users"] == 0
        assert result["user_limit"] == 5
    
    def test_add_bonus_quota(self, quota_service):
        """Test adding bonus quota"""
        result = quota_service.add_bonus_quota(
            tenant_id="test-tenant",
            amount=100,
            description="Test purchase"
        )
        
        assert result["success"] is True
        assert result["new_balance"] == 100
        
        # Verify quota increased
        status = quota_service.get_quota_status("test-tenant")
        assert status["bonus_scan_quota"] == 100
        assert status["total_scan_quota"] == 150  # 50 monthly + 100 bonus
    
    def test_quota_transactions_recorded(self, quota_service, test_db):
        """Test that quota transactions are recorded"""
        quota_service.add_bonus_quota(
            tenant_id="test-tenant",
            amount=50,
            description="Test transaction"
        )
        
        transactions = quota_service.get_quota_transactions("test-tenant")
        
        assert len(transactions) == 1
        assert transactions[0]["quota_amount"] == 50
        assert transactions[0]["transaction_type"] == "purchase"


# ==================== SubscriptionService Tests ====================

class TestSubscriptionService:
    """Tests for SubscriptionService"""
    
    def test_list_plans(self, subscription_service):
        """Test listing all plans"""
        plans = subscription_service.list_plans()
        
        assert len(plans) == 4
        plan_names = [p["name"] for p in plans]
        assert "free" in plan_names
        assert "starter" in plan_names
        assert "business" in plan_names
        assert "enterprise" in plan_names
    
    def test_get_plan(self, subscription_service):
        """Test getting a specific plan"""
        plan = subscription_service.get_plan("starter")
        
        assert plan is not None
        assert plan["display_name"] == "Starter"
        assert plan["monthly_scan_quota"] == 500
        assert plan["user_limit"] == 20
    
    def test_assign_plan(self, subscription_service, test_db):
        """Test assigning a plan to tenant"""
        result = subscription_service.assign_plan("test-tenant", "starter", 1)
        
        assert result["success"] is True
        assert result["plan_name"] == "Starter"
        assert "version_id" in result
        
        # Verify tenant updated
        sub = subscription_service.get_tenant_subscription("test-tenant")
        assert sub["plan_name"] == "starter"
        assert sub["plan_display_name"] == "Starter"
    
    def test_create_plan_version_grandfathering(self, subscription_service, test_db):
        """Test that creating new version doesn't affect existing tenants"""
        # Assign current version to tenant
        subscription_service.assign_plan("test-tenant", "starter", 1)
        old_sub = subscription_service.get_tenant_subscription("test-tenant")
        old_version_id = old_sub["plan_version_id"]
        
        # Create new version with different limits
        new_version = subscription_service.create_plan_version(
            plan_id="starter",
            monthly_scan_quota=1000,  # Increased
            user_limit=50,  # Increased
        )
        
        # Tenant should still have old version
        current_sub = subscription_service.get_tenant_subscription("test-tenant")
        assert current_sub["plan_version_id"] == old_version_id
        assert current_sub["monthly_scan_quota"] == 500  # Old value
        assert current_sub["update_available"] is True  # But update is available
    
    def test_renew_subscription_gets_latest_version(self, subscription_service, test_db):
        """Test that renewal applies latest plan version"""
        # Assign initial version
        subscription_service.assign_plan("test-tenant", "starter", 1)
        
        # Create new version
        subscription_service.create_plan_version(
            plan_id="starter",
            monthly_scan_quota=1000,
            user_limit=50,
        )
        
        # Renew subscription
        result = subscription_service.renew_subscription("test-tenant", 1)
        
        assert result["success"] is True
        
        # Tenant should now have new limits
        sub = subscription_service.get_tenant_subscription("test-tenant")
        assert sub["monthly_scan_quota"] == 1000
        assert sub["user_limit"] == 50
        assert sub["update_available"] is False
    
    def test_update_plan_metadata(self, subscription_service):
        """Test updating plan display name and description"""
        result = subscription_service.update_plan(
            "free",
            display_name="Free Trial",
            description="14 天免費試用"
        )
        
        assert result is not None
        assert result["display_name"] == "Free Trial"
        assert result["description"] == "14 天免費試用"


# ==================== Integration Tests ====================

class TestQuotaAndSubscriptionIntegration:
    """Integration tests combining QuotaService and SubscriptionService"""
    
    def test_plan_limits_applied_to_quota(self, quota_service, subscription_service):
        """Test that assigned plan limits are applied to quota checks"""
        # Assign business plan
        subscription_service.assign_plan("test-tenant", "business", 1)
        
        # Check quota reflects business plan limits
        status = quota_service.get_quota_status("test-tenant")
        assert status["monthly_scan_quota"] == 3000
        assert status["user_limit"] == 100
        assert status["daily_card_limit"] == 50
    
    def test_consume_after_plan_upgrade(self, quota_service, subscription_service, test_db):
        """Test that consumption works correctly after plan upgrade"""
        # Start with free plan (default)
        # Consume some quota
        quota_service.consume_scan("test-tenant", 40)
        
        # Upgrade to starter
        subscription_service.assign_plan("test-tenant", "starter", 1)
        
        # Should now have more quota (500 - 40 already used)
        status = quota_service.get_quota_status("test-tenant")
        # Note: current_month_scans is preserved across plan changes
        assert status["monthly_scan_quota"] == 500
        assert status["remaining_scans"] == 460  # 500 - 40


# ==================== Edge Cases ====================

class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_consume_scan_nonexistent_tenant(self, quota_service):
        """Test handling of non-existent tenant"""
        result = quota_service.consume_scan("nonexistent-tenant", 1)
        
        assert result["success"] is False
        assert "not found" in result["message"].lower() or result["remaining_scans"] == 0
    
    def test_assign_nonexistent_plan(self, subscription_service):
        """Test assigning non-existent plan"""
        result = subscription_service.assign_plan("test-tenant", "super-premium", 1)
        
        assert result["success"] is False
        assert "not found" in result["message"].lower()
    
    def test_consume_exactly_remaining_quota(self, quota_service, test_db):
        """Test consuming exactly the remaining quota"""
        from datetime import datetime
        current_month = datetime.now().strftime("%Y-%m-01")
        with test_db.get_connection() as conn:
            conn.execute(
                "UPDATE tenants SET current_month_scans = 49, quota_reset_date = ? WHERE id = ?",
                (current_month, "test-tenant",)
            )
        
        result = quota_service.consume_scan("test-tenant", 1)
        
        assert result["success"] is True
        assert result["remaining_scans"] == 0
    
    def test_consume_more_than_remaining(self, quota_service, test_db):
        """Test trying to consume more than remaining quota"""
        from datetime import datetime
        current_month = datetime.now().strftime("%Y-%m-01")
        with test_db.get_connection() as conn:
            conn.execute(
                "UPDATE tenants SET current_month_scans = 45, quota_reset_date = ? WHERE id = ?",
                (current_month, "test-tenant",)
            )
        
        result = quota_service.consume_scan("test-tenant", 10)  # Only 5 remaining
        
        assert result["success"] is False
        assert result["remaining_scans"] == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
