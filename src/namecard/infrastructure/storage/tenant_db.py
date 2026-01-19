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
            os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            ),
            "data",
            "schema.sql",
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
                    # Also run migrations to ensure commercialization tables exist
                    self._run_migrations(conn)
                else:
                    # Inline schema if file not found
                    self._create_inline_schema(conn)
            else:
                # Run migrations for existing databases
                self._run_migrations(conn)

    def _run_migrations(self, conn: sqlite3.Connection):
        """Run schema migrations for existing databases"""
        # Check if user_stats table exists, create if not
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='user_stats'"
        )
        if cursor.fetchone() is None:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS user_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    line_user_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    cards_processed INTEGER DEFAULT 0,
                    cards_saved INTEGER DEFAULT 0,
                    errors INTEGER DEFAULT 0,
                    UNIQUE(tenant_id, line_user_id, date)
                );

                CREATE INDEX IF NOT EXISTS idx_user_stats_tenant ON user_stats(tenant_id);
                CREATE INDEX IF NOT EXISTS idx_user_stats_user ON user_stats(line_user_id);
            """
            )
            logger.info("Migration: user_stats table created")

        # Check if use_shared_notion_api column exists, add if not
        cursor = conn.execute("PRAGMA table_info(tenants)")
        columns = [row[1] for row in cursor.fetchall()]
        if "use_shared_notion_api" not in columns:
            conn.execute("ALTER TABLE tenants ADD COLUMN use_shared_notion_api INTEGER DEFAULT 1")
            logger.info("Migration: use_shared_notion_api column added to tenants")

        # Check if line_users table exists, create if not
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='line_users'"
        )
        if cursor.fetchone() is None:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS line_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    line_user_id TEXT NOT NULL,
                    display_name TEXT,
                    picture_url TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(tenant_id, line_user_id)
                );

                CREATE INDEX IF NOT EXISTS idx_line_users_tenant ON line_users(tenant_id);
                CREATE INDEX IF NOT EXISTS idx_line_users_user ON line_users(line_user_id);
            """
            )
            logger.info("Migration: line_users table created")

        # Check if Google Drive columns exist in tenants table
        cursor = conn.execute("PRAGMA table_info(tenants)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "google_drive_folder_url" not in columns:
            conn.execute("ALTER TABLE tenants ADD COLUMN google_drive_folder_url TEXT")
            logger.info("Migration: google_drive_folder_url column added to tenants")
        
        if "google_drive_last_sync" not in columns:
            conn.execute("ALTER TABLE tenants ADD COLUMN google_drive_last_sync TEXT")
            logger.info("Migration: google_drive_last_sync column added to tenants")
        
        if "google_drive_sync_status" not in columns:
            conn.execute("ALTER TABLE tenants ADD COLUMN google_drive_sync_status TEXT DEFAULT 'idle'")
            logger.info("Migration: google_drive_sync_status column added to tenants")
        
        if "google_drive_sync_schedule" not in columns:
            conn.execute("ALTER TABLE tenants ADD COLUMN google_drive_sync_schedule TEXT")
            logger.info("Migration: google_drive_sync_schedule column added to tenants")
        
        if "google_drive_sync_enabled" not in columns:
            conn.execute("ALTER TABLE tenants ADD COLUMN google_drive_sync_enabled INTEGER DEFAULT 0")
            logger.info("Migration: google_drive_sync_enabled column added to tenants")
        
        # Check if drive_sync_logs table exists, create if not
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='drive_sync_logs'"
        )
        if cursor.fetchone() is None:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS drive_sync_logs (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    folder_url TEXT,
                    folder_id TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    total_files INTEGER DEFAULT 0,
                    processed_files INTEGER DEFAULT 0,
                    success_count INTEGER DEFAULT 0,
                    error_count INTEGER DEFAULT 0,
                    skipped_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'processing',
                    error_log TEXT,
                    is_scheduled INTEGER DEFAULT 0,
                    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
                );

                CREATE INDEX IF NOT EXISTS idx_drive_sync_logs_tenant ON drive_sync_logs(tenant_id);
                CREATE INDEX IF NOT EXISTS idx_drive_sync_logs_status ON drive_sync_logs(status);
            """
            )
            logger.info("Migration: drive_sync_logs table created")
        else:
            # Add is_scheduled column if missing
            cursor = conn.execute("PRAGMA table_info(drive_sync_logs)")
            sync_log_columns = [row[1] for row in cursor.fetchall()]
            if "is_scheduled" not in sync_log_columns:
                conn.execute("ALTER TABLE drive_sync_logs ADD COLUMN is_scheduled INTEGER DEFAULT 0")
                logger.info("Migration: is_scheduled column added to drive_sync_logs")

        # ==================== Commercialization Tables ====================
        
        # Check if subscription_plans table exists, create if not
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='subscription_plans'"
        )
        if cursor.fetchone() is None:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS subscription_plans (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    description TEXT,
                    is_active INTEGER DEFAULT 1,
                    sort_order INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now'))
                );
                
                CREATE INDEX IF NOT EXISTS idx_subscription_plans_name ON subscription_plans(name);
            """
            )
            logger.info("Migration: subscription_plans table created")
            
            # Insert default plans
            default_plans = [
                ("free", "Free", "免費試用方案", 1, 0),
                ("starter", "Starter", "小型團隊方案", 1, 1),
                ("business", "Business", "中型企業方案", 1, 2),
                ("enterprise", "Enterprise", "大型企業方案", 1, 3),
            ]
            for plan_id, display_name, desc, is_active, sort_order in default_plans:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO subscription_plans (id, name, display_name, description, is_active, sort_order)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (plan_id, plan_id, display_name, desc, is_active, sort_order)
                )
            logger.info("Migration: Default subscription plans inserted")
        
        # Check if plan_versions table exists, create if not
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='plan_versions'"
        )
        if cursor.fetchone() is None:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS plan_versions (
                    id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    version_number INTEGER NOT NULL,
                    user_limit INTEGER DEFAULT 5,
                    monthly_scan_quota INTEGER DEFAULT 50,
                    daily_card_limit INTEGER DEFAULT 10,
                    batch_size_limit INTEGER DEFAULT 5,
                    price_monthly INTEGER DEFAULT 0,
                    price_yearly INTEGER,
                    is_current INTEGER DEFAULT 1,
                    effective_from TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(plan_id, version_number),
                    FOREIGN KEY (plan_id) REFERENCES subscription_plans(id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_plan_versions_plan ON plan_versions(plan_id);
                CREATE INDEX IF NOT EXISTS idx_plan_versions_current ON plan_versions(is_current);
            """
            )
            logger.info("Migration: plan_versions table created")
            
            # Insert default plan versions (v1)
            # uuid already imported at module level
            default_versions = [
                # (plan_id, user_limit, monthly_scan_quota, daily_card_limit, batch_size_limit, price_monthly)
                ("free", 5, 50, 10, 5, 0),
                ("starter", 20, 500, 20, 10, 29900),
                ("business", 100, 3000, 50, 20, 99900),
                ("enterprise", None, 10000, 100, 50, 299900),
            ]
            for plan_id, user_limit, scan_quota, daily_limit, batch_limit, price in default_versions:
                version_id = str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT OR IGNORE INTO plan_versions 
                    (id, plan_id, version_number, user_limit, monthly_scan_quota, 
                     daily_card_limit, batch_size_limit, price_monthly, is_current, effective_from)
                    VALUES (?, ?, 1, ?, ?, ?, ?, ?, 1, datetime('now'))
                    """,
                    (version_id, plan_id, user_limit, scan_quota, daily_limit, batch_limit, price)
                )
            logger.info("Migration: Default plan versions (v1) inserted")
        
        # Check if quota_transactions table exists, create if not
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='quota_transactions'"
        )
        if cursor.fetchone() is None:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS quota_transactions (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    transaction_type TEXT NOT NULL,
                    quota_amount INTEGER NOT NULL,
                    balance_after INTEGER NOT NULL,
                    description TEXT,
                    payment_reference TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    created_by TEXT,
                    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_quota_trans_tenant ON quota_transactions(tenant_id);
                CREATE INDEX IF NOT EXISTS idx_quota_trans_date ON quota_transactions(created_at);
            """
            )
            logger.info("Migration: quota_transactions table created")
        
        # Add new columns to tenants table for commercialization
        cursor = conn.execute("PRAGMA table_info(tenants)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "plan_version_id" not in columns:
            conn.execute("ALTER TABLE tenants ADD COLUMN plan_version_id TEXT")
            logger.info("Migration: plan_version_id column added to tenants")
        
        if "plan_started_at" not in columns:
            conn.execute("ALTER TABLE tenants ADD COLUMN plan_started_at TEXT")
            logger.info("Migration: plan_started_at column added to tenants")
        
        if "plan_expires_at" not in columns:
            conn.execute("ALTER TABLE tenants ADD COLUMN plan_expires_at TEXT")
            logger.info("Migration: plan_expires_at column added to tenants")
        
        if "next_plan_version_id" not in columns:
            conn.execute("ALTER TABLE tenants ADD COLUMN next_plan_version_id TEXT")
            logger.info("Migration: next_plan_version_id column added to tenants")
        
        if "bonus_scan_quota" not in columns:
            conn.execute("ALTER TABLE tenants ADD COLUMN bonus_scan_quota INTEGER DEFAULT 0")
            logger.info("Migration: bonus_scan_quota column added to tenants")
        
        if "current_month_scans" not in columns:
            conn.execute("ALTER TABLE tenants ADD COLUMN current_month_scans INTEGER DEFAULT 0")
            logger.info("Migration: current_month_scans column added to tenants")
        
        if "quota_reset_date" not in columns:
            conn.execute("ALTER TABLE tenants ADD COLUMN quota_reset_date TEXT")
            logger.info("Migration: quota_reset_date column added to tenants")
        
        if "quota_reset_cycle" not in columns:
            conn.execute("ALTER TABLE tenants ADD COLUMN quota_reset_cycle TEXT DEFAULT 'monthly'")
            logger.info("Migration: quota_reset_cycle column added to tenants")
        
        if "quota_reset_day" not in columns:
            conn.execute("ALTER TABLE tenants ADD COLUMN quota_reset_day INTEGER DEFAULT 1")
            logger.info("Migration: quota_reset_day column added to tenants")
        
        if "registration_status" not in columns:
            conn.execute("ALTER TABLE tenants ADD COLUMN registration_status TEXT DEFAULT 'active'")
            logger.info("Migration: registration_status column added to tenants")
        
        if "registered_email" not in columns:
            conn.execute("ALTER TABLE tenants ADD COLUMN registered_email TEXT")
            logger.info("Migration: registered_email column added to tenants")

    def _create_inline_schema(self, conn: sqlite3.Connection):
        """Create schema inline if schema.sql not found"""
        conn.executescript(
            """
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
                notion_api_key_encrypted TEXT,
                notion_database_id TEXT NOT NULL,
                use_shared_notion_api INTEGER DEFAULT 1,
                google_api_key_encrypted TEXT,
                use_shared_google_api INTEGER DEFAULT 1,
                daily_card_limit INTEGER DEFAULT 50,
                batch_size_limit INTEGER DEFAULT 10,
                google_drive_folder_url TEXT,
                google_drive_last_sync TEXT,
                google_drive_sync_status TEXT DEFAULT 'idle',
                google_drive_sync_schedule TEXT,
                google_drive_sync_enabled INTEGER DEFAULT 0,
                -- Commercialization columns
                plan_version_id TEXT,
                plan_started_at TEXT,
                plan_expires_at TEXT,
                next_plan_version_id TEXT,
                bonus_scan_quota INTEGER DEFAULT 0,
                current_month_scans INTEGER DEFAULT 0,
                quota_reset_date TEXT,
                quota_reset_cycle TEXT DEFAULT 'monthly',
                quota_reset_day INTEGER DEFAULT 1,
                registration_status TEXT DEFAULT 'active',
                registered_email TEXT
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

            CREATE TABLE IF NOT EXISTS user_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                line_user_id TEXT NOT NULL,
                date TEXT NOT NULL,
                cards_processed INTEGER DEFAULT 0,
                cards_saved INTEGER DEFAULT 0,
                errors INTEGER DEFAULT 0,
                UNIQUE(tenant_id, line_user_id, date)
            );

            CREATE TABLE IF NOT EXISTS line_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                line_user_id TEXT NOT NULL,
                display_name TEXT,
                picture_url TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                UNIQUE(tenant_id, line_user_id)
            );
            
            -- Commercialization tables
            CREATE TABLE IF NOT EXISTS subscription_plans (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                description TEXT,
                is_active INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            );
            
            CREATE TABLE IF NOT EXISTS plan_versions (
                id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                version_number INTEGER NOT NULL,
                user_limit INTEGER DEFAULT 5,
                monthly_scan_quota INTEGER DEFAULT 50,
                daily_card_limit INTEGER DEFAULT 10,
                batch_size_limit INTEGER DEFAULT 5,
                price_monthly INTEGER DEFAULT 0,
                price_yearly INTEGER,
                is_current INTEGER DEFAULT 1,
                effective_from TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE(plan_id, version_number),
                FOREIGN KEY (plan_id) REFERENCES subscription_plans(id)
            );
            
            CREATE TABLE IF NOT EXISTS quota_transactions (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                transaction_type TEXT NOT NULL,
                quota_amount INTEGER NOT NULL,
                balance_after INTEGER NOT NULL,
                description TEXT,
                payment_reference TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                created_by TEXT,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id)
            );

            CREATE INDEX IF NOT EXISTS idx_tenants_line_channel_id ON tenants(line_channel_id);
            CREATE INDEX IF NOT EXISTS idx_tenants_slug ON tenants(slug);
            CREATE INDEX IF NOT EXISTS idx_user_stats_tenant ON user_stats(tenant_id);
            CREATE INDEX IF NOT EXISTS idx_user_stats_user ON user_stats(line_user_id);
            CREATE INDEX IF NOT EXISTS idx_line_users_tenant ON line_users(tenant_id);
            CREATE INDEX IF NOT EXISTS idx_line_users_user ON line_users(line_user_id);
            CREATE INDEX IF NOT EXISTS idx_subscription_plans_name ON subscription_plans(name);
            CREATE INDEX IF NOT EXISTS idx_plan_versions_plan ON plan_versions(plan_id);
            CREATE INDEX IF NOT EXISTS idx_plan_versions_current ON plan_versions(is_current);
            CREATE INDEX IF NOT EXISTS idx_quota_trans_tenant ON quota_transactions(tenant_id);
            CREATE INDEX IF NOT EXISTS idx_quota_trans_date ON quota_transactions(created_at);
        """
        )
        logger.info("Database schema created inline")
        
        # Insert default plans and versions
        self._insert_default_plans(conn)

    def _insert_default_plans(self, conn: sqlite3.Connection):
        """Insert default subscription plans and initial versions"""
        # uuid already imported at module level
        
        # Check if plans already exist
        cursor = conn.execute("SELECT COUNT(*) FROM subscription_plans")
        if cursor.fetchone()[0] > 0:
            return
        
        # Insert default plans
        default_plans = [
            ("free", "Free", "免費試用方案", 1, 0),
            ("starter", "Starter", "小型團隊方案", 1, 1),
            ("business", "Business", "中型企業方案", 1, 2),
            ("enterprise", "Enterprise", "大型企業方案", 1, 3),
        ]
        for plan_id, display_name, desc, is_active, sort_order in default_plans:
            conn.execute(
                """
                INSERT OR IGNORE INTO subscription_plans (id, name, display_name, description, is_active, sort_order)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (plan_id, plan_id, display_name, desc, is_active, sort_order)
            )
        
        # Insert default plan versions (v1)
        default_versions = [
            # (plan_id, user_limit, monthly_scan_quota, daily_card_limit, batch_size_limit, price_monthly)
            ("free", 5, 50, 10, 5, 0),
            ("starter", 20, 500, 20, 10, 29900),
            ("business", 100, 3000, 50, 20, 99900),
            ("enterprise", None, 10000, 100, 50, 299900),
        ]
        for plan_id, user_limit, scan_quota, daily_limit, batch_limit, price in default_versions:
            version_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT OR IGNORE INTO plan_versions 
                (id, plan_id, version_number, user_limit, monthly_scan_quota, 
                 daily_card_limit, batch_size_limit, price_monthly, is_current, effective_from)
                VALUES (?, ?, 1, ?, ?, ?, ?, ?, 1, datetime('now'))
                """,
                (version_id, plan_id, user_limit, scan_quota, daily_limit, batch_limit, price)
            )
        
        logger.info("Default subscription plans and versions inserted")

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
                    notion_database_id, use_shared_notion_api, google_api_key_encrypted,
                    use_shared_google_api, daily_card_limit, batch_size_limit
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    1 if data.get("use_shared_notion_api", True) else 0,
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
            cursor = conn.execute("SELECT * FROM tenants WHERE id = ?", (tenant_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_tenant_by_channel_id(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """Get tenant by LINE Channel ID"""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM tenants WHERE line_channel_id = ?", (channel_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_tenant_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        """Get tenant by slug"""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM tenants WHERE slug = ?", (slug,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_tenants(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """List all tenants"""
        with self.get_connection() as conn:
            if include_inactive:
                cursor = conn.execute("SELECT * FROM tenants ORDER BY created_at DESC")
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
            "name",
            "slug",
            "is_active",
            "line_channel_id",
            "line_channel_access_token_encrypted",
            "line_channel_secret_encrypted",
            "notion_api_key_encrypted",
            "notion_database_id",
            "use_shared_notion_api",
            "google_api_key_encrypted",
            "use_shared_google_api",
            "daily_card_limit",
            "batch_size_limit",
            "quota_reset_cycle",
            "quota_reset_day",
            "google_drive_folder_url",
            "google_drive_last_sync",
            "google_drive_sync_status",
            "google_drive_sync_schedule",
            "google_drive_sync_enabled",
        ]

        for field in allowed_fields:
            if field in data and data[field] is not None:
                if field == "is_active":
                    fields.append(f"{field} = ?")
                    values.append(1 if data[field] else 0)
                elif field in ("use_shared_google_api", "use_shared_notion_api"):
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
            conn.execute(f"UPDATE tenants SET {', '.join(fields)} WHERE id = ?", values)

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
                    (datetime.now().isoformat(), tenant_id),
                )
            else:
                cursor = conn.execute("DELETE FROM tenants WHERE id = ?", (tenant_id,))

            deleted = cursor.rowcount > 0

        if deleted:
            logger.info("Tenant deleted", tenant_id=tenant_id, soft_delete=soft_delete)

        return deleted

    # ==================== Admin User Operations ====================

    def create_admin(
        self, username: str, password_hash: str, is_super: bool = False
    ) -> Dict[str, Any]:
        """Create admin user"""
        admin_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO admin_users (id, username, password_hash, is_super_admin, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (admin_id, username, password_hash, 1 if is_super else 0, now),
            )

        logger.info("Admin user created", admin_id=admin_id, username=username)
        return self.get_admin_by_id(admin_id)

    def get_admin_by_id(self, admin_id: str) -> Optional[Dict[str, Any]]:
        """Get admin by ID"""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM admin_users WHERE id = ?", (admin_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_admin_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get admin by username"""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM admin_users WHERE username = ?", (username,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_admin_last_login(self, admin_id: str):
        """Update admin last login time"""
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE admin_users SET last_login = ? WHERE id = ?",
                (datetime.now().isoformat(), admin_id),
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
                (password_hash, username),
            )
            return cursor.rowcount > 0

    # ==================== Usage Stats Operations ====================

    def record_usage(
        self,
        tenant_id: str,
        cards_processed: int = 0,
        cards_saved: int = 0,
        api_calls: int = 0,
        errors: int = 0,
    ):
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
                (tenant_id, today, cards_processed, cards_saved, api_calls, errors),
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
                (tenant_id, f"-{days} days"),
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
                (today,),
            )
            row = cursor.fetchone()

            return {
                "total_tenants": total_tenants,
                "today_cards_processed": row[0] or 0,
                "today_cards_saved": row[1] or 0,
                "today_errors": row[2] or 0,
            }

    def get_today_stats_by_tenant(self) -> Dict[str, Dict[str, int]]:
        """Get today's usage stats for all tenants"""
        today = datetime.now().strftime("%Y-%m-%d")
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT tenant_id, cards_processed, cards_saved, errors
                FROM usage_stats WHERE date = ?
                """,
                (today,),
            )
            result = {}
            for row in cursor.fetchall():
                result[row["tenant_id"]] = {
                    "cards_processed": row["cards_processed"] or 0,
                    "cards_saved": row["cards_saved"] or 0,
                    "errors": row["errors"] or 0,
                }
            return result

    # ==================== Audit Log Operations ====================

    def log_audit(
        self,
        action: str,
        admin_id: Optional[str] = None,
        target_tenant_id: Optional[str] = None,
        details: Optional[str] = None,
        ip_address: Optional[str] = None,
    ):
        """Log an audit event"""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO audit_logs (admin_id, action, target_tenant_id, details, ip_address)
                VALUES (?, ?, ?, ?, ?)
                """,
                (admin_id, action, target_tenant_id, details, ip_address),
            )

    # ==================== User Stats Operations ====================

    def record_user_usage(
        self,
        tenant_id: str,
        line_user_id: str,
        cards_processed: int = 0,
        cards_saved: int = 0,
        errors: int = 0,
    ):
        """Record usage statistics for a specific user"""
        today = datetime.now().strftime("%Y-%m-%d")

        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO user_stats (tenant_id, line_user_id, date, cards_processed, cards_saved, errors)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, line_user_id, date) DO UPDATE SET
                    cards_processed = cards_processed + excluded.cards_processed,
                    cards_saved = cards_saved + excluded.cards_saved,
                    errors = errors + excluded.errors
                """,
                (tenant_id, line_user_id, today, cards_processed, cards_saved, errors),
            )

    def get_tenant_users_stats(self, tenant_id: str, days: int = 30) -> List[Dict[str, Any]]:
        """Get aggregated stats for all users of a tenant"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT
                    line_user_id,
                    SUM(cards_processed) as total_processed,
                    SUM(cards_saved) as total_saved,
                    SUM(errors) as total_errors,
                    COUNT(DISTINCT date) as active_days,
                    MAX(date) as last_active
                FROM user_stats
                WHERE tenant_id = ? AND date >= date('now', ?)
                GROUP BY line_user_id
                ORDER BY total_processed DESC
                """,
                (tenant_id, f"-{days} days"),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_top_users(
        self, tenant_id: str, limit: int = 10, days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get top users by usage for a tenant, including user profile info"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT
                    us.line_user_id,
                    lu.display_name,
                    lu.picture_url,
                    SUM(us.cards_processed) as total_processed,
                    SUM(us.cards_saved) as total_saved,
                    SUM(us.errors) as total_errors,
                    ROUND(CAST(SUM(us.cards_saved) AS FLOAT) / NULLIF(SUM(us.cards_processed), 0) * 100, 1) as success_rate
                FROM user_stats us
                LEFT JOIN line_users lu ON us.tenant_id = lu.tenant_id AND us.line_user_id = lu.line_user_id
                WHERE us.tenant_id = ? AND us.date >= date('now', ?)
                GROUP BY us.line_user_id
                ORDER BY total_processed DESC
                LIMIT ?
                """,
                (tenant_id, f"-{days} days", limit),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_user_stats(
        self, tenant_id: str, line_user_id: str, days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get daily stats for a specific user"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM user_stats
                WHERE tenant_id = ? AND line_user_id = ? AND date >= date('now', ?)
                ORDER BY date DESC
                """,
                (tenant_id, line_user_id, f"-{days} days"),
            )
            return [dict(row) for row in cursor.fetchall()]

    # ==================== Extended Stats Operations ====================

    def get_tenant_stats_monthly(self, tenant_id: str, months: int = 12) -> List[Dict[str, Any]]:
        """Get monthly aggregated stats for a tenant"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT
                    strftime('%Y-%m', date) as month,
                    SUM(cards_processed) as cards_processed,
                    SUM(cards_saved) as cards_saved,
                    SUM(api_calls) as api_calls,
                    SUM(errors) as errors,
                    COUNT(DISTINCT date) as active_days
                FROM usage_stats
                WHERE tenant_id = ? AND date >= date('now', ?)
                GROUP BY strftime('%Y-%m', date)
                ORDER BY month DESC
                """,
                (tenant_id, f"-{months} months"),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_tenant_stats_yearly(self, tenant_id: str, years: int = 3) -> List[Dict[str, Any]]:
        """Get yearly aggregated stats for a tenant"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT
                    strftime('%Y', date) as year,
                    SUM(cards_processed) as cards_processed,
                    SUM(cards_saved) as cards_saved,
                    SUM(api_calls) as api_calls,
                    SUM(errors) as errors,
                    COUNT(DISTINCT date) as active_days
                FROM usage_stats
                WHERE tenant_id = ? AND date >= date('now', ?)
                GROUP BY strftime('%Y', date)
                ORDER BY year DESC
                """,
                (tenant_id, f"-{years} years"),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_tenant_stats_range(
        self, tenant_id: str, start_date: str, end_date: str
    ) -> List[Dict[str, Any]]:
        """Get stats for a tenant within a date range"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM usage_stats
                WHERE tenant_id = ? AND date >= ? AND date <= ?
                ORDER BY date DESC
                """,
                (tenant_id, start_date, end_date),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_tenant_stats_summary(self, tenant_id: str, days: int = 30) -> Dict[str, Any]:
        """Get summary statistics for a tenant"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT
                    SUM(cards_processed) as total_processed,
                    SUM(cards_saved) as total_saved,
                    SUM(errors) as total_errors,
                    SUM(api_calls) as total_api_calls,
                    COUNT(DISTINCT date) as active_days,
                    AVG(cards_processed) as avg_daily_processed
                FROM usage_stats
                WHERE tenant_id = ? AND date >= date('now', ?)
                """,
                (tenant_id, f"-{days} days"),
            )
            row = cursor.fetchone()
            if row:
                return {
                    "total_processed": row["total_processed"] or 0,
                    "total_saved": row["total_saved"] or 0,
                    "total_errors": row["total_errors"] or 0,
                    "total_api_calls": row["total_api_calls"] or 0,
                    "active_days": row["active_days"] or 0,
                    "avg_daily_processed": round(row["avg_daily_processed"] or 0, 1),
                    "success_rate": round(
                        (row["total_saved"] or 0) / max(row["total_processed"] or 1, 1) * 100, 1
                    ),
                    "error_rate": round(
                        (row["total_errors"] or 0) / max(row["total_processed"] or 1, 1) * 100, 1
                    ),
                }
            return {
                "total_processed": 0,
                "total_saved": 0,
                "total_errors": 0,
                "total_api_calls": 0,
                "active_days": 0,
                "avg_daily_processed": 0,
                "success_rate": 0,
                "error_rate": 0,
            }

    def get_all_tenants_summary(self, days: int = 30) -> Dict[str, Any]:
        """Get summary statistics across all tenants"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT
                    SUM(cards_processed) as total_processed,
                    SUM(cards_saved) as total_saved,
                    SUM(errors) as total_errors,
                    COUNT(DISTINCT tenant_id) as active_tenants
                FROM usage_stats
                WHERE date >= date('now', ?)
                """,
                (f"-{days} days",),
            )
            row = cursor.fetchone()
            return {
                "total_processed": row["total_processed"] or 0,
                "total_saved": row["total_saved"] or 0,
                "total_errors": row["total_errors"] or 0,
                "active_tenants": row["active_tenants"] or 0,
            }

    def get_user_count_by_tenant(self, tenant_id: str, days: int = 30) -> int:
        """Get count of unique users for a tenant"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT COUNT(DISTINCT line_user_id) as user_count
                FROM user_stats
                WHERE tenant_id = ? AND date >= date('now', ?)
                """,
                (tenant_id, f"-{days} days"),
            )
            row = cursor.fetchone()
            return row["user_count"] if row else 0

    # ==================== LINE User Operations ====================

    def upsert_line_user(
        self,
        tenant_id: str,
        line_user_id: str,
        display_name: Optional[str] = None,
        picture_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Insert or update LINE user information.

        Args:
            tenant_id: Tenant ID
            line_user_id: LINE user ID
            display_name: User's display name
            picture_url: User's profile picture URL

        Returns:
            User data dict
        """
        now = datetime.now().isoformat()

        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO line_users (tenant_id, line_user_id, display_name, picture_url, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, line_user_id) DO UPDATE SET
                    display_name = COALESCE(excluded.display_name, display_name),
                    picture_url = COALESCE(excluded.picture_url, picture_url),
                    updated_at = excluded.updated_at
                """,
                (tenant_id, line_user_id, display_name, picture_url, now, now),
            )

        return self.get_line_user(tenant_id, line_user_id)

    def get_line_user(self, tenant_id: str, line_user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get LINE user information.

        Args:
            tenant_id: Tenant ID
            line_user_id: LINE user ID

        Returns:
            User data dict or None if not found
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM line_users
                WHERE tenant_id = ? AND line_user_id = ?
                """,
                (tenant_id, line_user_id),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_line_users_by_tenant(self, tenant_id: str) -> List[Dict[str, Any]]:
        """
        Get all LINE users for a tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            List of user data dicts
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM line_users
                WHERE tenant_id = ?
                ORDER BY updated_at DESC
                """,
                (tenant_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    # ==================== Drive Sync Operations ====================

    def create_drive_sync_log(
        self,
        tenant_id: str,
        folder_url: str,
        folder_id: str = None,
        is_scheduled: bool = False,
    ) -> Dict[str, Any]:
        """
        Create a new drive sync log entry.

        Args:
            tenant_id: Tenant ID
            folder_url: Google Drive folder URL
            folder_id: Parsed folder ID
            is_scheduled: Whether this is a scheduled sync (vs manual)

        Returns:
            Created log entry
        """
        log_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO drive_sync_logs (
                    id, tenant_id, folder_url, folder_id, started_at, status, is_scheduled
                ) VALUES (?, ?, ?, ?, ?, 'processing', ?)
                """,
                (log_id, tenant_id, folder_url, folder_id, now, 1 if is_scheduled else 0),
            )

        logger.info("Drive sync log created", log_id=log_id, tenant_id=tenant_id, is_scheduled=is_scheduled)
        return self.get_drive_sync_log(log_id)

    def get_drive_sync_log(self, log_id: str) -> Optional[Dict[str, Any]]:
        """Get a drive sync log by ID"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM drive_sync_logs WHERE id = ?", (log_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_drive_sync_log(
        self,
        log_id: str,
        total_files: int = None,
        processed_files: int = None,
        success_count: int = None,
        error_count: int = None,
        skipped_count: int = None,
        status: str = None,
        error_log: str = None,
        completed: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Update a drive sync log entry.

        Args:
            log_id: Log ID
            Various fields to update
            completed: If True, set completed_at timestamp

        Returns:
            Updated log entry or None if not found
        """
        fields = []
        values = []

        if total_files is not None:
            fields.append("total_files = ?")
            values.append(total_files)
        if processed_files is not None:
            fields.append("processed_files = ?")
            values.append(processed_files)
        if success_count is not None:
            fields.append("success_count = ?")
            values.append(success_count)
        if error_count is not None:
            fields.append("error_count = ?")
            values.append(error_count)
        if skipped_count is not None:
            fields.append("skipped_count = ?")
            values.append(skipped_count)
        if status is not None:
            fields.append("status = ?")
            values.append(status)
        if error_log is not None:
            fields.append("error_log = ?")
            values.append(error_log)
        if completed:
            fields.append("completed_at = ?")
            values.append(datetime.now().isoformat())

        if not fields:
            return self.get_drive_sync_log(log_id)

        values.append(log_id)

        with self.get_connection() as conn:
            conn.execute(
                f"UPDATE drive_sync_logs SET {', '.join(fields)} WHERE id = ?",
                values,
            )

        return self.get_drive_sync_log(log_id)

    def get_tenant_drive_sync_logs(
        self, tenant_id: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent drive sync logs for a tenant"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM drive_sync_logs
                WHERE tenant_id = ?
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (tenant_id, limit),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_active_drive_sync(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get the currently active (processing) drive sync for a tenant"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM drive_sync_logs
                WHERE tenant_id = ? AND status = 'processing'
                ORDER BY started_at DESC
                LIMIT 1
                """,
                (tenant_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None


# Global database instance
_db_instance: Optional[TenantDatabase] = None


def get_tenant_db(db_path: Optional[str] = None) -> TenantDatabase:
    """Get or create the global database instance"""
    global _db_instance
    if _db_instance is None:
        _db_instance = TenantDatabase(db_path)
    return _db_instance
