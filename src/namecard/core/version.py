#!/usr/bin/env python3
"""
版本管理模組
提供版本號、Git commit hash 和部署資訊
"""

import os
import subprocess
import sys
from datetime import datetime
from typing import Optional, Dict, Any


class VersionManager:
    """版本管理器"""
    
    def __init__(self):
        self._version = "1.0.0"
        self._git_commit = None
        self._git_branch = None
        self._build_time = datetime.now().isoformat()
        
        # 嘗試獲取 Git 資訊
        self._load_git_info()
    
    def _load_git_info(self) -> None:
        """載入 Git 資訊"""
        try:
            # 獲取 commit hash
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                self._git_commit = result.stdout.strip()[:8]  # 使用短 hash
            
            # 獲取 branch 名稱
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                self._git_branch = result.stdout.strip()
        
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
            # 無法獲取 Git 資訊時使用環境變數或預設值
            self._git_commit = os.getenv('GIT_COMMIT', 'unknown')[:8]
            self._git_branch = os.getenv('GIT_BRANCH', 'unknown')
    
    @property
    def version(self) -> str:
        """應用程式版本號"""
        return self._version
    
    @property
    def git_commit(self) -> str:
        """Git commit hash (短版本)"""
        return self._git_commit or 'unknown'
    
    @property
    def git_branch(self) -> str:
        """Git branch 名稱"""
        return self._git_branch or 'unknown'
    
    @property
    def release_name(self) -> str:
        """Sentry release 名稱"""
        if self._git_commit:
            return f"{self._version}+{self._git_commit}"
        return self._version
    
    @property
    def build_time(self) -> str:
        """建置時間"""
        return self._build_time
    
    def get_version_info(self) -> Dict[str, Any]:
        """獲取完整版本資訊"""
        return {
            "version": self.version,
            "git_commit": self.git_commit,
            "git_branch": self.git_branch,
            "release_name": self.release_name,
            "build_time": self.build_time,
            "python_version": sys.version,
            "platform": sys.platform
        }
    
    def get_sentry_release_info(self) -> Dict[str, str]:
        """獲取 Sentry Release 資訊"""
        return {
            "release": self.release_name,
            "environment": os.getenv('FLASK_ENV', 'production'),
            "dist": self.git_commit,
        }


# 全域版本管理器實例
version_manager = VersionManager()