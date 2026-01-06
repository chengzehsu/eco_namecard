"""
Google Drive Client for Business Card Processing

Provides functionality to:
- Parse Google Drive folder URLs
- List image files in a shared folder
- Download images for processing
- Rename files after processing
"""

import re
import io
import json
from typing import Optional, List, Dict, Tuple
import structlog

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    from googleapiclient.errors import HttpError
    GOOGLE_DRIVE_AVAILABLE = True
except Exception as e:
    GOOGLE_DRIVE_AVAILABLE = False

from simple_config import settings

logger = structlog.get_logger()

# Google Drive API Scopes
SCOPES = ['https://www.googleapis.com/auth/drive']

# Supported image MIME types
IMAGE_MIME_TYPES = [
    'image/jpeg',
    'image/png',
    'image/gif',
    'image/webp',
    'image/bmp',
]


class GoogleDriveError(Exception):
    """Base exception for Google Drive operations"""
    pass


class GoogleDriveAuthError(GoogleDriveError):
    """Authentication/credential errors"""
    pass


class GoogleDriveFolderNotFoundError(GoogleDriveError):
    """Folder not found or no access"""
    pass


class GoogleDriveClient:
    """
    Google Drive API Client for accessing shared folders.
    
    Uses Service Account authentication for server-side access.
    Customers must share their folders with the Service Account email.
    """
    
    def __init__(self, credentials_json: Optional[str] = None):
        """
        Initialize the Google Drive client.
        
        Args:
            credentials_json: JSON string of service account credentials.
                             Falls back to settings.google_service_account_json if not provided.
        """
        if not GOOGLE_DRIVE_AVAILABLE:
            raise GoogleDriveError(
                "Google Drive API dependencies not installed. "
                "Please install google-api-python-client and google-auth."
            )
        
        self._credentials_json = credentials_json or settings.google_service_account_json
        self._service = None
        self._credentials = None
        
        if self._credentials_json:
            self._initialize_service()
    
    def _initialize_service(self):
        """Initialize the Google Drive service with credentials."""
        try:
            if isinstance(self._credentials_json, str):
                creds_dict = json.loads(self._credentials_json)
            else:
                creds_dict = self._credentials_json
            
            self._credentials = service_account.Credentials.from_service_account_info(
                creds_dict,
                scopes=SCOPES
            )
            self._service = build('drive', 'v3', credentials=self._credentials)
            
            logger.info(
                "google_drive_client_initialized",
                service_account_email=creds_dict.get('client_email', 'unknown')
            )
        except json.JSONDecodeError as e:
            raise GoogleDriveAuthError(f"Invalid JSON credentials: {e}")
        except Exception as e:
            raise GoogleDriveAuthError(f"Failed to initialize Google Drive service: {e}")
    
    @property
    def service_account_email(self) -> Optional[str]:
        """Get the service account email for sharing instructions."""
        if self._credentials_json:
            try:
                creds_dict = json.loads(self._credentials_json) if isinstance(
                    self._credentials_json, str
                ) else self._credentials_json
                return creds_dict.get('client_email')
            except Exception:
                return None
        return None
    
    @staticmethod
    def extract_folder_id(url: str) -> Optional[str]:
        """
        Extract folder ID from various Google Drive URL formats.
        
        Supported formats:
        - https://drive.google.com/drive/folders/FOLDER_ID
        - https://drive.google.com/drive/folders/FOLDER_ID?usp=sharing
        - https://drive.google.com/drive/u/0/folders/FOLDER_ID
        - https://drive.google.com/open?id=FOLDER_ID
        - Just the folder ID itself
        
        Args:
            url: Google Drive folder URL or ID
            
        Returns:
            Folder ID or None if not found
        """
        if not url:
            return None
        
        url = url.strip()
        
        # Pattern 1: /folders/FOLDER_ID
        match = re.search(r'/folders/([a-zA-Z0-9_-]+)', url)
        if match:
            return match.group(1)
        
        # Pattern 2: ?id=FOLDER_ID or &id=FOLDER_ID
        match = re.search(r'[?&]id=([a-zA-Z0-9_-]+)', url)
        if match:
            return match.group(1)
        
        # Pattern 3: Just the ID (alphanumeric with - and _)
        if re.match(r'^[a-zA-Z0-9_-]+$', url) and len(url) > 10:
            return url
        
        return None
    
    def validate_folder_access(self, folder_url: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        Validate access to a Google Drive folder.
        
        Args:
            folder_url: Google Drive folder URL
            
        Returns:
            Tuple of (success, message, folder_info)
            folder_info contains: name, id, file_count
        """
        if not self._service:
            return False, "Google Drive 服務未初始化。請檢查 Service Account 設定。", None
        
        folder_id = self.extract_folder_id(folder_url)
        if not folder_id:
            return False, "無法從 URL 解析資料夾 ID。請確認 URL 格式正確。", None
        
        try:
            # Get folder metadata
            folder = self._service.files().get(
                fileId=folder_id,
                fields='id, name, mimeType'
            ).execute()
            
            # Verify it's a folder
            if folder.get('mimeType') != 'application/vnd.google-apps.folder':
                return False, "此連結不是資料夾。請提供 Google Drive 資料夾連結。", None
            
            # Count image files
            images = self.list_images(folder_id)
            unprocessed = [f for f in images if not f['name'].startswith('[已處理]')]
            
            folder_info = {
                'id': folder_id,
                'name': folder.get('name', '未知資料夾'),
                'total_files': len(images),
                'unprocessed_files': len(unprocessed),
            }
            
            return True, f"成功連接！資料夾「{folder_info['name']}」", folder_info
            
        except HttpError as e:
            if e.resp.status == 404:
                return False, (
                    f"找不到資料夾或沒有存取權限。"
                    f"請將資料夾共享給：{self.service_account_email}"
                ), None
            elif e.resp.status == 403:
                return False, (
                    f"沒有資料夾存取權限。"
                    f"請將資料夾共享給：{self.service_account_email}"
                ), None
            else:
                logger.error("google_drive_api_error", error=str(e), status=e.resp.status)
                return False, f"Google Drive API 錯誤：{e.reason}", None
        except Exception as e:
            logger.error("google_drive_unexpected_error", error=str(e))
            return False, f"發生錯誤：{str(e)}", None
    
    def list_images(self, folder_id: str) -> List[Dict]:
        """
        List all image files in a folder.
        
        Args:
            folder_id: Google Drive folder ID
            
        Returns:
            List of file info dicts with: id, name, mimeType, size, createdTime
        """
        if not self._service:
            raise GoogleDriveError("Google Drive 服務未初始化")
        
        images = []
        page_token = None
        
        # Build query for images in this folder
        mime_query = " or ".join([f"mimeType='{mt}'" for mt in IMAGE_MIME_TYPES])
        query = f"'{folder_id}' in parents and ({mime_query}) and trashed=false"
        
        try:
            while True:
                response = self._service.files().list(
                    q=query,
                    fields='nextPageToken, files(id, name, mimeType, size, createdTime)',
                    pageSize=100,
                    pageToken=page_token,
                    orderBy='createdTime desc'
                ).execute()
                
                images.extend(response.get('files', []))
                page_token = response.get('nextPageToken')
                
                if not page_token:
                    break
            
            logger.info(
                "google_drive_list_images",
                folder_id=folder_id,
                image_count=len(images)
            )
            return images
            
        except HttpError as e:
            logger.error("google_drive_list_error", folder_id=folder_id, error=str(e))
            raise GoogleDriveError(f"無法列出資料夾內容：{e.reason}")
    
    def download_image(self, file_id: str) -> bytes:
        """
        Download an image file.
        
        Args:
            file_id: Google Drive file ID
            
        Returns:
            Image data as bytes
        """
        if not self._service:
            raise GoogleDriveError("Google Drive 服務未初始化")
        
        try:
            request = self._service.files().get_media(fileId=file_id)
            buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(buffer, request)
            
            done = False
            while not done:
                _, done = downloader.next_chunk()
            
            buffer.seek(0)
            data = buffer.read()
            
            logger.debug(
                "google_drive_download_complete",
                file_id=file_id,
                size=len(data)
            )
            return data
            
        except HttpError as e:
            logger.error("google_drive_download_error", file_id=file_id, error=str(e))
            raise GoogleDriveError(f"下載檔案失敗：{e.reason}")
    
    def rename_file(self, file_id: str, new_name: str) -> bool:
        """
        Rename a file in Google Drive.
        
        Args:
            file_id: Google Drive file ID
            new_name: New filename
            
        Returns:
            True if successful
        """
        if not self._service:
            raise GoogleDriveError("Google Drive 服務未初始化")
        
        try:
            self._service.files().update(
                fileId=file_id,
                body={'name': new_name}
            ).execute()
            
            logger.info(
                "google_drive_file_renamed",
                file_id=file_id,
                new_name=new_name
            )
            return True
            
        except HttpError as e:
            if e.resp.status == 403:
                logger.warning(
                    "google_drive_rename_permission_denied",
                    file_id=file_id,
                    error=str(e)
                )
                raise GoogleDriveError(
                    "沒有重新命名檔案的權限。請將資料夾共享設為「編輯者」權限。"
                )
            logger.error("google_drive_rename_error", file_id=file_id, error=str(e))
            raise GoogleDriveError(f"重新命名失敗：{e.reason}")
    
    def is_available(self) -> bool:
        """Check if the Google Drive client is properly configured."""
        return self._service is not None
    
    def get_file_info(self, file_id: str) -> Optional[Dict]:
        """Get file metadata."""
        if not self._service:
            return None
        
        try:
            return self._service.files().get(
                fileId=file_id,
                fields='id, name, mimeType, size, createdTime, modifiedTime'
            ).execute()
        except Exception as e:
            logger.error("google_drive_get_file_error", file_id=file_id, error=str(e))
            return None


# Factory function for easy instantiation
def get_google_drive_client() -> Optional[GoogleDriveClient]:
    """
    Get a configured Google Drive client instance.
    
    Returns:
        GoogleDriveClient if configured, None otherwise
    """
    if not settings.google_service_account_json:
        logger.warning("google_drive_not_configured", message="No service account JSON configured")
        return None
    
    try:
        return GoogleDriveClient()
    except Exception as e:
        logger.error("google_drive_client_creation_failed", error=str(e))
        return None
