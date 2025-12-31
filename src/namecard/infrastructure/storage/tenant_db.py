"""
SQLite Database Operations for Multi-Tenant System

Handles database initialization, connection management, and CRUD operations
for tenants and admin users.
"""

import sqlite3
import os
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
from pathlib import Path
import structlog

logger = structlog.get_logger()

# Default database path
DEFAULT_DB_PATH = "data/tenants.db"


class TenantDatabase:
    """SQLite database manager for tenant data"""

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the database manager.

        Args:
            db_path: Path to SQLite database file. Defaults to data/tenants.db
        """
        self.db_path = db_path or os.environ.get("TENANT_DB_PATH", DEFAULT_DB_PATH)
        self._ensure_db_directory()
        self._initialize_schema()

    def _ensure_db_directory(self):
        """Ensure the database directory exists"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            Path(db_dir).mkdir(parents=True, exist_ok=True)

    def _initialize_schema(self):
        """Initialize database schema if not exists"""
        schema_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))),
            "data",
            "schema.sql"
        )

        with self.get_connection() as conn:
            # Check if tenants table exists
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='tenants'"
            )
            if cursor.fetchone() is None:
                # Load and execute schema
                if os.path.exists(schema_path):
                    with open(schema_path, "r") as f:
                        schema_sql = f.read()
                    conn.executescript(schema_sql)
                    logger.info("Database schema initialized", db_path=self.db_path)
                else:
                    # Inline schema if file not found
                    self._create_inline_schema(conn)

    def _create_inline_schema(self, conn: sqlite3.Connection):
        """Create schema inline if schema.sql not found"""
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tenants (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                line_channel_id TEXT NOT NULL UNIQUE,
                line_channel_access_token_encrypted TEXT NOT NULL,
                line_channel_secret_encrypted TEXT NOT NULL,
                notion_api_key_encrypted TEXT NOT NULL,
                notion_database_id TEXT NOT NULL,
                google_api_key_encrypted TEXT,
                use_shared_google_api INTEGER DEFAULT 1,
                daily_card_limit INTEGER DEFAULT 50,
                batch_size_limit INTEGER DEFAULT 10
            );

            CREATE TABLE IF NOT EXISTS admin_users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_super_admin INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                last_login TEXT
            );

            CREATE TABLE IF NOT EXISTS usage_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                date TEXT NOT NULL,
                cards_processed INTEGER DEFAULT 0,
                cards_saved INTEGER DEFAULT 0,
                api_calls INTEGER DEFAULT 0,
                errors INTEGER DEFAULT 0,
                UNIQUE(tenant_id, date)
            );

            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id TEXT,
                action TEXT NOT NULL,
                target_tenant_id TEXT,
                details TEXT,
                ip_address TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_tenants_line_channel_id ON tenants(line_channel_id);
            CREATE INDEX IF NOT EXISTS idx_tenants_slug ON tenants(slug);
        """)
        logger.info("Database schema created inline")

    @contextmanager
    def get_connection(self):
        """Get a database connection as a context manager"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    # ==================== Tenant Operations ====================

    def create_tenant(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new tenant.

        Args:
            data: Tenant data including encrypted credentials

        Returns:
            Created tenant data
        """
        tenant_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO tenants (
                    id, name, slug, is_active, created_at, updated_at,
                    line_channel_id, line_channel_access_token_encrypted,
                    line_channel_secret_encrypted, notion_api_key_encrypted,
                    notion_database_id, google_api_key_encrypted,
                    use_shared_google_api, daily_card_limit, batch_size_limit
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tenant_id,
                    data["name"],
                    data["slug"],
                    1 if data.get("is_active", True) else 0,
                    now,
                    now,
                    data["line_channel_id"],
                    data["line_channel_access_token_encrypted"],
                    data["line_channel_secret_encrypted"],
                    data["notion_api_key_encrypted"],
                    data["notion_database_id"],
                    data.get("google_api_key_encrypted"),
                    1 if data.get("use_shared_google_api", True) else 0,
                    data.get("daily_card_limit", 50),
                    data.get("batch_size_limit", 10),
                ),
            )

        logger.info("Tenant created", tenant_id=tenant_id, name=data["name"])
        return self.get_tenant_by_id(tenant_id)

    def get_tenant_by_id(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get tenant by ID"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM tenants WHERE id = ?", (tenant_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_tenant_by_channel_id(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """Get tenant by LINE Channel ID"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM tenants WHERE line_channel_id = ?", (channel_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_tenant_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        """Get tenant by slug"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM tenants WHERE slug = ?", (slug,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_tenants(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """List all tenants"""
        with self.get_connection() as conn:
            if include_inactive:
                cursor = conn.execute(
                    "SELECT * FROM tenants ORDER BY created_at DESC"
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM tenants WHERE is_active = 1 ORDER BY created_at DESC"
                )
            return [dict(row) for row in cursor.fetchall()]

    def update_tenant(self, tenant_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Update tenant data.

        Args:
            tenant_id: Tenant ID
            data: Fields to update

        Returns:
            Updated tenant data or None if not found
        """
        # Build dynamic UPDATE query
        fields = []
        values = []

        allowed_fields = [
            "name", "slug", "is_active",
            "line_channel_access_token_encrypted", "line_channel_secret_encrypted",
            "notion_api_key_encrypted", "notion_database_id",
            "google_api_key_encrypted", "use_shared_google_api",
            "daily_card_limit", "batch_size_limit"
        ]

        for field in allowed_fields:
            if field in data and data[field] is not None:
                if field == "is_active":
                    fields.append(f"{field} = ?")
                    values.append(1 if data[field] else 0)
                elif field == "use_shared_google_api":
                    fields.append(f"{field} = ?")
                    values.append(1 if data[field] else 0)
                else:
                    fields.append(f"{field} = ?")
                    values.append(data[field])

        if not fields:
            return self.get_tenant_by_id(tenant_id)

        fields.append("updated_at = ?")
        values.append(datetime.now().isoformat())
        values.append(tenant_id)

        with self.get_connection() as conn:
            conn.execute(
                f"UPDATE tenants SET {', '.join(fields)} WHERE id = ?",
                values
            )

        logger.info("Tenant updated", tenant_id=tenant_id)
        return self.get_tenant_by_id(tenant_id)

    def delete_tenant(self, tenant_id: str, soft_delete: bool = True) -> bool:
        """
        Delete a tenant.

        Args:
            tenant_id: Tenant ID
            soft_delete: If True, just set is_active=0. If False, permanently delete.

        Returns:
            True if deleted, False if not found
        """
        with self.get_connection() as conn:
            if soft_delete:
                cursor = conn.execute(
                    "UPDATE tenants SET is_active = 0, updated_at = ? WHERE id = ?",
                    (datetime.now().isoformat(), tenant_id)
                )
            else:
                cursor = conn.execute("DELETE FROM tenants WHERE id = ?", (tenant_id,))

            deleted = cursor.rowcount > 0

        if deleted:
            logger.info("Tenant deleted", tenant_id=tenant_id, soft_delete=soft_delete)

        return deleted

    # ==================== Admin User Operations ====================

    def create_admin(self, username: str, password_hash: str, is_super: bool = False) -> Dict[str, Any]:
        """Create admin user"""
        admin_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO admin_users (id, username, password_hash, is_super_admin, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (admin_id, username, password_hash, 1 if is_super else 0, now)
            )

        logger.info("Admin user created", admin_id=admin_id, username=username)
        return self.get_admin_by_id(admin_id)

    def get_admin_by_id(self, admin_id: str) -> Optional[Dict[str, Any]]:
        """Get admin by ID"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM admin_users WHERE id = ?", (admin_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_admin_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get admin by username"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM admin_users WHERE username = ?", (username,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_admin_last_login(self, admin_id: str):
        """Update admin last login time"""
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE admin_users SET last_login = ? WHERE id = ?",
                (datetime.now().isoformat(), admin_id)
            )

    def admin_exists(self) -> bool:
        """Check if any admin user exists"""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM admin_users")
            return cursor.fetchone()[0] > 0

    def update_admin_password(self, username: str, password_hash: str) -> bool:
        """
        Update admin password by username

        Args:
            username: Admin username
            password_hash: New bcrypt password hash

        Returns:
            True if updated, False if user not found
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                "UPDATE admin_users SET password_hash = ? WHERE username = ?",
                (password_hash, username)
            )
            return cursor.rowcount > 0

    # ==================== Usage Stats Operations ====================

    def record_usage(self, tenant_id: str, cards_processed: int = 0,
                     cards_saved: int = 0, api_calls: int = 0, errors: int = 0):
        """Record usage statistics for a tenant"""
        today = datetime.now().strftime("%Y-%m-%d")

        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO usage_stats (tenant_id, date, cards_processed, cards_saved, api_calls, errors)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, date) DO UPDATE SET
                    cards_processed = cards_processed + excluded.cards_processed,
                    cards_saved = cards_saved + excluded.cards_saved,
                    api_calls = api_calls + excluded.api_calls,
                    errors = errors + excluded.errors
                """,
                (tenant_id, today, cards_processed, cards_saved, api_calls, errors)
            )

    def get_tenant_stats(self, tenant_id: str, days: int = 30) -> List[Dict[str, Any]]:
        """Get usage stats for a tenant"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM usage_stats
                WHERE tenant_id = ? AND date >= date('now', ?)
                ORDER BY date DESC
                """,
                (tenant_id, f"-{days} days")
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_overall_stats(self) -> Dict[str, Any]:
        """Get overall statistics across all tenants"""
        with self.get_connection() as conn:
            # Total tenants
            cursor = conn.execute("SELECT COUNT(*) FROM tenants WHERE is_active = 1")
            total_tenants = cursor.fetchone()[0]

            # Today's usage
            today = datetime.now().strftime("%Y-%m-%d")
            cursor = conn.execute(
                """
                SELECT SUM(cards_processed), SUM(cards_saved), SUM(errors)
                FROM usage_stats WHERE date = ?
                """,
                (today,)
            )
            row = cursor.fetchone()

            return {
                "total_tenants": total_tenants,
                "today_cards_processed": row[0] or 0,
                "today_cards_saved": row[1] or 0,
                "today_errors": row[2] or 0,
            }

    # ==================== Audit Log Operations ====================

    def log_audit(self, action: str, admin_id: Optional[str] = None,
                  target_tenant_id: Optional[str] = None,
                  details: Optional[str] = None, ip_address: Optional[str] = None):
        """Log an audit event"""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO audit_logs (admin_id, action, target_tenant_id, details, ip_address)
                VALUES (?, ?, ?, ?, ?)
                """,
                (admin_id, action, target_tenant_id, details, ip_address)
            )


# Global database instance
_db_instance: Optional[TenantDatabase] = None


def get_tenant_db(db_path: Optional[str] = None) -> TenantDatabase:
    """Get or create the global database instance"""
    global _db_instance
    if _db_instance is None:
        _db_instance = TenantDatabase(db_path)
    return _db_instance
