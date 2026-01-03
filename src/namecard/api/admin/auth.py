"""
Admin Authentication Module

Handles admin user authentication using bcrypt for password hashing.
"""

import os
import bcrypt
from functools import wraps
from typing import Optional, Dict, Any
from flask import session, redirect, url_for
import structlog

from src.namecard.infrastructure.storage.tenant_db import get_tenant_db

logger = structlog.get_logger()


class AdminAuth:
    """Admin authentication manager"""

    def __init__(self):
        self.db = get_tenant_db()
        self._ensure_initial_admin()

    def _ensure_initial_admin(self):
        """Create initial admin user if none exists, or reset password if requested"""
        username = os.environ.get("INITIAL_ADMIN_USERNAME", "admin")
        password = os.environ.get("INITIAL_ADMIN_PASSWORD")
        reset_password = os.environ.get("RESET_ADMIN_PASSWORD", "").lower() in ("true", "1", "yes")

        if not self.db.admin_exists():
            # No admin exists, create one
            if not password:
                # Generate a random password if not provided
                import secrets
                password = secrets.token_urlsafe(16)
                logger.warning(
                    "No INITIAL_ADMIN_PASSWORD set. Generated random password.",
                    username=username,
                    password=password  # Only log once at startup
                )

            self.create_admin(username, password, is_super=True)
            logger.info("Initial admin user created", username=username)

        elif reset_password and password:
            # Admin exists and reset is requested with a new password
            password_hash = self.hash_password(password)
            if self.db.update_admin_password(username, password_hash):
                logger.info(
                    "Admin password reset successfully",
                    username=username,
                    hint="Remember to set RESET_ADMIN_PASSWORD=false after reset"
                )
            else:
                logger.warning(
                    "Failed to reset admin password - user not found",
                    username=username
                )

    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt"""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a password against its hash"""
        try:
            return bcrypt.checkpw(
                password.encode("utf-8"),
                password_hash.encode("utf-8")
            )
        except Exception as e:
            logger.error("Password verification failed", error=str(e))
            return False

    def create_admin(self, username: str, password: str, is_super: bool = False) -> str:
        """
        Create a new admin user

        Args:
            username: Admin username
            password: Plain text password
            is_super: Whether this is a super admin

        Returns:
            Admin user ID
        """
        password_hash = self.hash_password(password)
        admin = self.db.create_admin(username, password_hash, is_super)
        logger.info("Admin created", admin_id=admin["id"], username=username)
        return admin["id"]

    def authenticate(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Authenticate an admin user

        Args:
            username: Admin username
            password: Plain text password

        Returns:
            Admin dict if authenticated, None otherwise
        """
        admin = self.db.get_admin_by_username(username)
        if not admin:
            logger.warning("Login attempt for unknown user", username=username)
            return None

        if self.verify_password(password, admin["password_hash"]):
            # Update last login
            self.db.update_admin_last_login(admin["id"])
            logger.info("Admin authenticated", admin_id=admin["id"], username=username)
            return admin
        else:
            logger.warning("Invalid password for user", username=username)
            return None

    def login(self, admin: dict):
        """Set session after successful login"""
        session["admin_id"] = admin["id"]
        session["admin_username"] = admin["username"]
        session["is_super_admin"] = bool(admin.get("is_super_admin", 0))

    def logout(self):
        """Clear session on logout"""
        session.pop("admin_id", None)
        session.pop("admin_username", None)
        session.pop("is_super_admin", None)

    def get_current_admin(self) -> Optional[Dict[str, Any]]:
        """Get current logged-in admin from session"""
        admin_id = session.get("admin_id")
        if admin_id:
            return self.db.get_admin_by_id(admin_id)
        return None

    def is_logged_in(self) -> bool:
        """Check if user is logged in"""
        return "admin_id" in session


def login_required(f):
    """Decorator to require login for a route"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "admin_id" not in session:
            return redirect(url_for("admin.login"))
        return f(*args, **kwargs)
    return decorated_function


# Global auth instance
_auth_instance = None


def get_admin_auth() -> AdminAuth:
    """Get or create the global AdminAuth instance"""
    global _auth_instance
    if _auth_instance is None:
        _auth_instance = AdminAuth()
    return _auth_instance
