-- Multi-Tenant Schema for LINE Bot Namecard System
-- Version: 1.0.0

-- Tenants table: Core tenant configuration
CREATE TABLE IF NOT EXISTS tenants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),

    -- LINE Bot Configuration (encrypted)
    line_channel_id TEXT NOT NULL UNIQUE,
    line_channel_access_token_encrypted TEXT NOT NULL,
    line_channel_secret_encrypted TEXT NOT NULL,

    -- Notion Configuration (encrypted)
    notion_api_key_encrypted TEXT,
    notion_database_id TEXT NOT NULL,

    -- Notion API Configuration (optional - use shared if null)
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

-- Indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_tenants_line_channel_id ON tenants(line_channel_id);
CREATE INDEX IF NOT EXISTS idx_tenants_slug ON tenants(slug);
CREATE INDEX IF NOT EXISTS idx_tenants_is_active ON tenants(is_active);
CREATE INDEX IF NOT EXISTS idx_usage_stats_tenant_date ON usage_stats(tenant_id, date);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at);
