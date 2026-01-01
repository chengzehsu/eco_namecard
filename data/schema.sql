-- Multi-Tenant Schema for LINE Bot Namecard System
-- Version: 1.0.0

-- Tenants table: Core tenant configuration
CREATE TABLE IF NOT EXISTS tenants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    is_active INTEGER DEFAULT 1,
    -- Activation status: 'pending' (awaiting LINE Bot auto-detection), 'active', 'inactive'
    activation_status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),

    -- LINE Bot Configuration (encrypted)
    -- line_channel_id is nullable for auto-detection feature
    line_channel_id TEXT UNIQUE,
    line_channel_access_token_encrypted TEXT NOT NULL,
    line_channel_secret_encrypted TEXT NOT NULL,

    -- Notion Configuration (encrypted) - api_key optional if using shared
    notion_api_key_encrypted TEXT,
    notion_database_id TEXT NOT NULL,
    use_shared_notion_api INTEGER DEFAULT 1,

    -- Google AI Configuration (optional - use shared if null)
    google_api_key_encrypted TEXT,
    use_shared_google_api INTEGER DEFAULT 1,

    -- Rate limiting
    daily_card_limit INTEGER DEFAULT 50,
    batch_size_limit INTEGER DEFAULT 10
);

-- Admin users table
CREATE TABLE IF NOT EXISTS admin_users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_super_admin INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    last_login TEXT
);

-- Usage statistics table
CREATE TABLE IF NOT EXISTS usage_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    date TEXT NOT NULL,
    cards_processed INTEGER DEFAULT 0,
    cards_saved INTEGER DEFAULT 0,
    api_calls INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    UNIQUE(tenant_id, date)
);

-- Audit log table
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id TEXT,
    action TEXT NOT NULL,
    target_tenant_id TEXT,
    details TEXT,
    ip_address TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (admin_id) REFERENCES admin_users(id),
    FOREIGN KEY (target_tenant_id) REFERENCES tenants(id)
);

-- User statistics table (per user per day)
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

-- LINE users table (user profile information)
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

-- Indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_tenants_line_channel_id ON tenants(line_channel_id);
CREATE INDEX IF NOT EXISTS idx_tenants_slug ON tenants(slug);
CREATE INDEX IF NOT EXISTS idx_tenants_is_active ON tenants(is_active);
CREATE INDEX IF NOT EXISTS idx_tenants_activation_status ON tenants(activation_status);
CREATE INDEX IF NOT EXISTS idx_usage_stats_tenant_date ON usage_stats(tenant_id, date);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_user_stats_tenant ON user_stats(tenant_id);
CREATE INDEX IF NOT EXISTS idx_user_stats_user ON user_stats(line_user_id);
CREATE INDEX IF NOT EXISTS idx_line_users_tenant ON line_users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_line_users_user ON line_users(line_user_id);
