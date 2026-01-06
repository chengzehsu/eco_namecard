"""
Google Drive Sync Service for Business Card Processing

Coordinates the end-to-end process:
1. Fetch images from Google Drive folder
2. Process with AI (CardProcessor)
3. Save to Notion
4. Rename processed files in Google Drive
"""

import uuid
from datetime import datetime
from typing import Optional, Dict, List, Callable
from dataclasses import dataclass, field
import structlog

from src.namecard.infrastructure.storage.google_drive_client import (
    GoogleDriveClient,
    GoogleDriveError,
    get_google_drive_client,
)
from src.namecard.infrastructure.ai.card_processor import CardProcessor
from src.namecard.infrastructure.storage.notion_client import NotionClient
from src.namecard.core.models.card import BusinessCard

logger = structlog.get_logger()


@dataclass
class SyncProgress:
    """Represents the progress of a sync operation."""
    total_files: int = 0
    processed_files: int = 0
    success_count: int = 0
    error_count: int = 0
    skipped_count: int = 0
    current_file: str = ""
    status: str = "pending"  # pending, processing, completed, failed, cancelled
    errors: List[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    @property
    def progress_percent(self) -> float:
        if self.total_files == 0:
            return 0.0
        return (self.processed_files / self.total_files) * 100
    
    def to_dict(self) -> Dict:
        return {
            'total_files': self.total_files,
            'processed_files': self.processed_files,
            'success_count': self.success_count,
            'error_count': self.error_count,
            'skipped_count': self.skipped_count,
            'current_file': self.current_file,
            'status': self.status,
            'progress_percent': round(self.progress_percent, 1),
            'errors': self.errors[-5:],  # Last 5 errors only
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }


class DriveSyncService:
    """
    Orchestrates the Google Drive sync process for a tenant.
    
    Workflow:
    1. List unprocessed images from Google Drive folder
    2. For each image:
       a. Download from Drive
       b. Process with CardProcessor (AI recognition)
       c. Save to Notion
       d. Rename file in Drive (mark as processed)
    """
    
    # File naming patterns
    PROCESSED_PREFIX = "[已處理]"
    FAILED_PREFIX = "[處理失敗]"
    
    def __init__(
        self,
        tenant_id: str,
        drive_client: Optional[GoogleDriveClient] = None,
        card_processor: Optional[CardProcessor] = None,
        notion_client: Optional[NotionClient] = None,
        google_api_key: Optional[str] = None,
        notion_api_key: Optional[str] = None,
        notion_database_id: Optional[str] = None,
    ):
        """
        Initialize the sync service.
        
        Args:
            tenant_id: The tenant ID for this sync operation
            drive_client: Optional GoogleDriveClient instance
            card_processor: Optional CardProcessor instance
            notion_client: Optional NotionClient instance
            google_api_key: Google API key for card processing
            notion_api_key: Notion API key
            notion_database_id: Notion database ID
        """
        self.tenant_id = tenant_id
        self.drive_client = drive_client or get_google_drive_client()
        
        # Initialize CardProcessor with tenant's API key if provided
        if card_processor:
            self.card_processor = card_processor
        else:
            self.card_processor = CardProcessor(api_key=google_api_key)
        
        # Initialize NotionClient with tenant's credentials if provided
        if notion_client:
            self.notion_client = notion_client
        elif notion_api_key and notion_database_id:
            self.notion_client = NotionClient(
                api_key=notion_api_key,
                database_id=notion_database_id
            )
        else:
            self.notion_client = None
        
        self._progress = SyncProgress()
        self._cancelled = False
    
    @property
    def progress(self) -> SyncProgress:
        """Get current sync progress."""
        return self._progress
    
    def cancel(self):
        """Request cancellation of the current sync."""
        self._cancelled = True
        logger.info("drive_sync_cancelled", tenant_id=self.tenant_id)
    
    def sync_folder(
        self,
        folder_url: str,
        progress_callback: Optional[Callable[[SyncProgress], None]] = None,
        user_id: str = "drive_sync"
    ) -> SyncProgress:
        """
        Sync all unprocessed images from a Google Drive folder.
        
        Args:
            folder_url: Google Drive folder URL
            progress_callback: Optional callback for progress updates
            user_id: User ID for card processing (used in Notion)
            
        Returns:
            Final SyncProgress with results
        """
        self._progress = SyncProgress()
        self._progress.started_at = datetime.now()
        self._progress.status = "processing"
        self._cancelled = False
        
        if not self.drive_client:
            self._progress.status = "failed"
            self._progress.errors.append("Google Drive 服務未設定")
            return self._progress
        
        if not self.notion_client:
            self._progress.status = "failed"
            self._progress.errors.append("Notion 服務未設定")
            return self._progress
        
        # Get folder ID
        folder_id = GoogleDriveClient.extract_folder_id(folder_url)
        if not folder_id:
            self._progress.status = "failed"
            self._progress.errors.append("無法解析資料夾 URL")
            return self._progress
        
        try:
            # List images
            images = self.drive_client.list_images(folder_id)
            
            # Filter out already processed files
            unprocessed = [
                img for img in images
                if not img['name'].startswith(self.PROCESSED_PREFIX)
                and not img['name'].startswith(self.FAILED_PREFIX)
            ]
            
            self._progress.total_files = len(unprocessed)
            self._progress.skipped_count = len(images) - len(unprocessed)
            
            logger.info(
                "drive_sync_started",
                tenant_id=self.tenant_id,
                folder_id=folder_id,
                total_images=len(images),
                unprocessed=len(unprocessed)
            )
            
            if progress_callback:
                progress_callback(self._progress)
            
            # Process each image
            for img in unprocessed:
                if self._cancelled:
                    self._progress.status = "cancelled"
                    break
                
                self._process_single_image(img, user_id)
                self._progress.processed_files += 1
                
                if progress_callback:
                    progress_callback(self._progress)
            
            # Mark as completed if not cancelled
            if self._progress.status != "cancelled":
                self._progress.status = "completed"
            
            self._progress.completed_at = datetime.now()
            
            logger.info(
                "drive_sync_completed",
                tenant_id=self.tenant_id,
                status=self._progress.status,
                success=self._progress.success_count,
                errors=self._progress.error_count
            )
            
            return self._progress
            
        except GoogleDriveError as e:
            self._progress.status = "failed"
            self._progress.errors.append(str(e))
            logger.error("drive_sync_failed", tenant_id=self.tenant_id, error=str(e))
            return self._progress
        except Exception as e:
            self._progress.status = "failed"
            self._progress.errors.append(f"未預期的錯誤：{str(e)}")
            logger.error("drive_sync_unexpected_error", tenant_id=self.tenant_id, error=str(e))
            return self._progress
    
    def _process_single_image(self, file_info: Dict, user_id: str):
        """
        Process a single image file.
        
        Args:
            file_info: File metadata from Google Drive
            user_id: User ID for Notion records
        """
        file_id = file_info['id']
        original_name = file_info['name']
        self._progress.current_file = original_name
        
        logger.info(
            "drive_sync_processing_file",
            tenant_id=self.tenant_id,
            file_id=file_id,
            filename=original_name
        )
        
        try:
            # 1. Download image
            image_data = self.drive_client.download_image(file_id)
            
            # 2. Process with AI
            cards = self.card_processor.process_image(image_data, user_id)
            
            if not cards:
                # No cards detected
                self._mark_file_failed(file_id, original_name, "未偵測到名片")
                self._progress.error_count += 1
                return
            
            # 3. Save to Notion (first card)
            card = cards[0]
            result = self.notion_client.save_business_card(card)
            
            if result:
                # 4. Rename file in Drive
                new_name = self._generate_processed_filename(card, original_name)
                self.drive_client.rename_file(file_id, new_name)
                self._progress.success_count += 1
                
                logger.info(
                    "drive_sync_file_success",
                    tenant_id=self.tenant_id,
                    file_id=file_id,
                    card_name=card.name,
                    new_filename=new_name
                )
            else:
                # Notion save failed
                self._mark_file_failed(file_id, original_name, "Notion 儲存失敗")
                self._progress.error_count += 1
                
        except GoogleDriveError as e:
            self._progress.error_count += 1
            self._progress.errors.append(f"{original_name}: {str(e)}")
            logger.error(
                "drive_sync_file_error",
                tenant_id=self.tenant_id,
                file_id=file_id,
                error=str(e)
            )
        except Exception as e:
            self._progress.error_count += 1
            self._progress.errors.append(f"{original_name}: {str(e)}")
            
            # Try to mark as failed
            try:
                self._mark_file_failed(file_id, original_name, str(e))
            except Exception:
                pass
            
            logger.error(
                "drive_sync_file_unexpected_error",
                tenant_id=self.tenant_id,
                file_id=file_id,
                error=str(e)
            )
    
    def _generate_processed_filename(self, card: BusinessCard, original_name: str) -> str:
        """
        Generate a new filename for a processed card.
        
        Format: [已處理]_姓名_公司_原檔名
        
        Args:
            card: Processed business card
            original_name: Original filename
            
        Returns:
            New filename
        """
        # Extract extension
        parts = original_name.rsplit('.', 1)
        base_name = parts[0]
        extension = parts[1] if len(parts) > 1 else ''
        
        # Build new name components
        name_part = card.name or "未知"
        company_part = card.company or "未知公司"
        
        # Clean up special characters that might cause issues
        name_part = name_part.replace('/', '_').replace('\\', '_')[:20]
        company_part = company_part.replace('/', '_').replace('\\', '_')[:20]
        
        new_name = f"{self.PROCESSED_PREFIX}_{name_part}_{company_part}_{base_name}"
        
        if extension:
            new_name = f"{new_name}.{extension}"
        
        return new_name
    
    def _mark_file_failed(self, file_id: str, original_name: str, reason: str):
        """
        Rename a file to indicate processing failure.
        
        Args:
            file_id: Google Drive file ID
            original_name: Original filename
            reason: Failure reason (for logging)
        """
        try:
            # Extract extension
            parts = original_name.rsplit('.', 1)
            base_name = parts[0]
            extension = parts[1] if len(parts) > 1 else ''
            
            new_name = f"{self.FAILED_PREFIX}_{base_name}"
            if extension:
                new_name = f"{new_name}.{extension}"
            
            self.drive_client.rename_file(file_id, new_name)
            
            logger.info(
                "drive_sync_file_marked_failed",
                tenant_id=self.tenant_id,
                file_id=file_id,
                reason=reason
            )
        except Exception as e:
            logger.warning(
                "drive_sync_could_not_mark_failed",
                tenant_id=self.tenant_id,
                file_id=file_id,
                error=str(e)
            )
