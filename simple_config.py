import os
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """應用程式設定"""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )
    
    # LINE Bot Configuration
    line_channel_id: Optional[str] = Field(default=None, description="LINE Bot User ID for default tenant (starts with U)")
    line_channel_access_token: str = Field(default="", description="LINE Channel Access Token")
    line_channel_secret: str = Field(default="", description="LINE Channel Secret")
    
    # Google AI Configuration
    google_api_key: str = Field(default="", description="Google API Key")
    google_api_key_fallback: Optional[str] = Field(default=None, description="Fallback Google API Key")
    
    # ImgBB Configuration (圖片儲存)
    imgbb_api_key: Optional[str] = Field(default=None, description="ImgBB API Key for image upload")

    # Notion Configuration
    notion_api_key: str = Field(default="", description="Shared Notion API Key for all tenants")
    notion_database_id: str = Field(default="", description="Notion Database ID (for default tenant)")
    notion_shared_parent_page_id: str = Field(
        default="2db08f881bb881a997b2c2e8610f84d7",
        description="Shared parent page ID for auto-creating tenant databases"
    )
    # Note: notion_api_key serves as the shared key for tenants who don't have their own
    
    # Application Configuration
    app_port: int = Field(default=5002, alias="PORT")  # Zeabur 使用 PORT 環境變數
    app_host: str = Field(default="0.0.0.0")
    flask_env: str = Field(default="production")
    secret_key: str = Field(default="fallback-secret-key-change-in-production")
    
    # Security Configuration
    rate_limit_per_user: int = Field(default=50)
    batch_size_limit: int = Field(default=10)
    max_image_size: int = Field(default=10485760)  # 10MB

    # Redis Configuration (for session persistence and rate limiting)
    redis_enabled: bool = Field(default=True, description="Enable Redis for persistence")
    redis_url: Optional[str] = Field(default=None, description="Redis connection URL (redis://host:port/db)")
    redis_host: str = Field(default="localhost", description="Redis host")
    redis_port: int = Field(default=6379, description="Redis port")
    redis_password: Optional[str] = Field(default=None, description="Redis password")
    redis_db: int = Field(default=0, description="Redis database number")
    redis_decode_responses: bool = Field(default=True, description="Decode Redis responses to strings")
    redis_socket_timeout: int = Field(default=5, description="Redis socket timeout in seconds")
    redis_max_connections: int = Field(default=50, description="Max Redis connection pool size")

    # Development
    debug: bool = Field(default=False)
    verbose_errors: bool = Field(default=False, description="Show detailed technical errors (for debugging)")


# 全域設定實例
settings = Settings()