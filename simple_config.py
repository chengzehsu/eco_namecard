import os
from pydantic import BaseSettings, Field
from typing import Optional


class Settings(BaseSettings):
    """應用程式設定"""
    
    # LINE Bot Configuration
    line_channel_access_token: str = Field(..., env="LINE_CHANNEL_ACCESS_TOKEN")
    line_channel_secret: str = Field(..., env="LINE_CHANNEL_SECRET")
    
    # Google AI Configuration
    google_api_key: str = Field(..., env="GOOGLE_API_KEY")
    google_api_key_fallback: Optional[str] = Field(None, env="GOOGLE_API_KEY_FALLBACK")
    
    # Notion Configuration
    notion_api_key: str = Field(..., env="NOTION_API_KEY")
    notion_database_id: str = Field(..., env="NOTION_DATABASE_ID")
    
    # Application Configuration
    app_port: int = Field(5002, env="APP_PORT")
    app_host: str = Field("0.0.0.0", env="APP_HOST")
    flask_env: str = Field("production", env="FLASK_ENV")
    secret_key: str = Field(..., env="SECRET_KEY")
    
    # Security Configuration
    rate_limit_per_user: int = Field(50, env="RATE_LIMIT_PER_USER")
    batch_size_limit: int = Field(10, env="BATCH_SIZE_LIMIT")
    max_image_size: int = Field(10485760, env="MAX_IMAGE_SIZE")  # 10MB
    
    # Monitoring Configuration
    sentry_dsn: Optional[str] = Field(None, env="SENTRY_DSN")
    
    # Development
    debug: bool = Field(False, env="DEBUG")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# 全域設定實例
settings = Settings()