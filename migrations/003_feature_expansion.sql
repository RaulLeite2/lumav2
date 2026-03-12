-- Migration 003: feature expansion (AI controls, stats, audit, reaction roles, tickets)
-- Created: 2026-03-12

-- AI usage events for rate limits and analytics
CREATE TABLE IF NOT EXISTS ai_usage_events (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    used_cached_response BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ai_usage_events_guild_time ON ai_usage_events(guild_id, created_at);
CREATE INDEX IF NOT EXISTS idx_ai_usage_events_user_time ON ai_usage_events(user_id, created_at);

-- AI response cache by normalized question and guild
CREATE TABLE IF NOT EXISTS ai_response_cache (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    question_key VARCHAR(300) NOT NULL,
    original_question TEXT NOT NULL,
    answer TEXT NOT NULL,
    hits INT DEFAULT 0,
    last_hit_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (guild_id, question_key)
);

CREATE INDEX IF NOT EXISTS idx_ai_response_cache_guild_question ON ai_response_cache(guild_id, question_key);

-- Generic command usage statistics
CREATE TABLE IF NOT EXISTS command_usage_stats (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    command_name VARCHAR(120) NOT NULL,
    used_count BIGINT DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (guild_id, command_name)
);

CREATE INDEX IF NOT EXISTS idx_command_usage_stats_guild ON command_usage_stats(guild_id);

-- Generic metric counters (warns_applied, ai_used_api, ai_used_cache, etc)
CREATE TABLE IF NOT EXISTS metric_counters (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    metric_name VARCHAR(120) NOT NULL,
    metric_value BIGINT DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (guild_id, metric_name)
);

CREATE INDEX IF NOT EXISTS idx_metric_counters_guild ON metric_counters(guild_id);

-- Unified audit logs for commands and moderation actions
CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    action_name VARCHAR(120) NOT NULL,
    executor_id BIGINT,
    target_id BIGINT,
    reason TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_guild_created ON audit_logs(guild_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_logs_executor ON audit_logs(executor_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_target ON audit_logs(target_id);

-- Reaction role panels
CREATE TABLE IF NOT EXISTS role_panels (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    message_id BIGINT,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_by BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_role_panels_guild_active ON role_panels(guild_id, is_active);

CREATE TABLE IF NOT EXISTS role_panel_options (
    id BIGSERIAL PRIMARY KEY,
    panel_id BIGINT NOT NULL REFERENCES role_panels(id) ON DELETE CASCADE,
    role_id BIGINT NOT NULL,
    label VARCHAR(100) NOT NULL,
    description VARCHAR(100),
    emoji VARCHAR(50),
    position INT DEFAULT 0,
    UNIQUE (panel_id, role_id)
);

CREATE INDEX IF NOT EXISTS idx_role_panel_options_panel ON role_panel_options(panel_id);

-- Ticket panels and ticket channels
CREATE TABLE IF NOT EXISTS ticket_panels (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    message_id BIGINT,
    category_id BIGINT,
    support_role_id BIGINT,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_by BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ticket_panels_guild_active ON ticket_panels(guild_id, is_active);

CREATE TABLE IF NOT EXISTS ticket_threads (
    id BIGSERIAL PRIMARY KEY,
    panel_id BIGINT REFERENCES ticket_panels(id) ON DELETE SET NULL,
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL UNIQUE,
    user_id BIGINT NOT NULL,
    status VARCHAR(20) DEFAULT 'open',
    opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ticket_threads_guild_status ON ticket_threads(guild_id, status);
CREATE INDEX IF NOT EXISTS idx_ticket_threads_user_status ON ticket_threads(user_id, status);
