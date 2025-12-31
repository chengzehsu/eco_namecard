"""
Multi-Tenant Models for LINE Bot Namecard System

Provides TenantConfig for storing tenant configuration and
TenantContext for runtime service instances.
"""

from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime
from linebot import LineBotApi


class TenantConfig(BaseModel):
    """Tenant-specific configuration (decrypted at runtime)"""

    id: str = Field(..., description="Unique tenant ID (UUID)")
    name: str = Field(..., description="Display name")
    slug: str = Field(..., description="URL-friendly identifier")
    is_active: bool = Field(default=True, description="Whether tenant is active")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # LINE Bot (decrypted)
    line_channel_id: str = Field(..., description="LINE Channel ID")
    line_channel_access_token: str = Field(..., description="LINE Access Token")
    line_channel_secret: str = Field(..., description="LINE Channel Secret")

    # Notion (decrypted)
    notion_api_key: str = Field(..., description="Notion API Key")
    notion_database_id: str = Field(..., description="Notion Database ID")

    # Google AI
    google_api_key: Optional[str] = Field(
        default=None, description="Tenant-specific Google API Key"
    )
    use_shared_google_api: bool = Field(
        default=True, description="Use shared Google API key"
    )

    # Limits
    daily_card_limit: int = Field(default=50, description="Daily card limit per user")
    batch_size_limit: int = Field(default=10, description="Batch size limit")

    class Config:
        from_attributes = True


class TenantCreateRequest(BaseModel):
    """Request model for creating a new tenant"""

    name: str = Field(..., min_length=1, max_length=100)
    slug: Optional[str] = Field(default=None, max_length=50)

    # LINE Bot
    line_channel_id: str = Field(..., min_length=1)
    line_channel_access_token: str = Field(..., min_length=1)
    line_channel_secret: str = Field(..., min_length=1)

    # Notion
    notion_api_key: str = Field(..., min_length=1)
    notion_database_id: str = Field(..., min_length=1)

    # Google AI (optional)
    google_api_key: Optional[str] = None
    use_shared_google_api: bool = True

    # Limits
    daily_card_limit: int = Field(default=50, ge=1, le=1000)
    batch_size_limit: int = Field(default=10, ge=1, le=50)


class TenantUpdateRequest(BaseModel):
    """Request model for updating a tenant"""

    name: Optional[str] = Field(default=None, max_length=100)
    is_active: Optional[bool] = None

    # LINE Bot (optional updates)
    line_channel_access_token: Optional[str] = None
    line_channel_secret: Optional[str] = None

    # Notion (optional updates)
    notion_api_key: Optional[str] = None
    notion_database_id: Optional[str] = None

    # Google AI
    google_api_key: Optional[str] = None
    use_shared_google_api: Optional[bool] = None

    # Limits
    daily_card_limit: Optional[int] = Field(default=None, ge=1, le=1000)
    batch_size_limit: Optional[int] = Field(default=None, ge=1, le=50)


class TenantContext:
    """
    Runtime context for processing requests with tenant-specific services.

    Lazy-loads service instances to avoid unnecessary initialization.
    """

    def __init__(self, tenant: TenantConfig):
        self.tenant = tenant
        self._line_bot_api: Optional[LineBotApi] = None
        self._card_processor: Optional[Any] = None
        self._notion_client: Optional[Any] = None

    @property
    def tenant_id(self) -> str:
        """Get tenant ID"""
        return self.tenant.id

    @property
    def tenant_name(self) -> str:
        """Get tenant name"""
        return self.tenant.name

    @property
    def line_bot_api(self) -> LineBotApi:
        """Lazy-loaded LINE Bot API instance"""
        if self._line_bot_api is None:
            self._line_bot_api = LineBotApi(self.tenant.line_channel_access_token)
        return self._line_bot_api

    @property
    def card_processor(self) -> Any:
        """Lazy-loaded Card Processor instance"""
        if self._card_processor is None:
            from src.namecard.infrastructure.ai.card_processor import CardProcessor
            from simple_config import settings

            # Use tenant-specific key or fall back to shared
            api_key = self.tenant.google_api_key
            if self.tenant.use_shared_google_api or not api_key:
                api_key = settings.google_api_key

            fallback_key = settings.google_api_key_fallback

            self._card_processor = CardProcessor(
                api_key=api_key, fallback_api_key=fallback_key
            )
        return self._card_processor

    @property
    def notion_client(self) -> Any:
        """Lazy-loaded Notion Client instance"""
        if self._notion_client is None:
            from src.namecard.infrastructure.storage.notion_client import NotionClient

            self._notion_client = NotionClient(
                api_key=self.tenant.notion_api_key,
                database_id=self.tenant.notion_database_id,
            )
        return self._notion_client

    def get_redis_key_prefix(self) -> str:
        """Get Redis key prefix for this tenant"""
        return f"namecard:{self.tenant_id}"


class UsageStats(BaseModel):
    """Usage statistics for a tenant"""

    tenant_id: str
    date: str
    cards_processed: int = 0
    cards_saved: int = 0
    api_calls: int = 0
    errors: int = 0


class AdminUser(BaseModel):
    """Admin user model"""

    id: str
    username: str
    password_hash: str
    is_super_admin: bool = False
    created_at: datetime = Field(default_factory=datetime.now)
    last_login: Optional[datetime] = None
