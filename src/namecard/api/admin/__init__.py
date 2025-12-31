"""
Admin Panel for Multi-Tenant Management

Provides web interface for managing tenants, viewing statistics,
and configuring the namecard system.
"""

from src.namecard.api.admin.routes import admin_bp

__all__ = ["admin_bp"]
