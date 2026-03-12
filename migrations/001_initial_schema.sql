-- Migration 001: Create initial schema for Luma bot
-- Created: 2026-03-08

-- Create guilds table
CREATE TABLE IF NOT EXISTS guilds (
    guild_id BIGINT PRIMARY KEY,
    log_channel_id BIGINT,
    auto_moderation BOOLEAN DEFAULT FALSE,
    quant_warnings INT DEFAULT 3,
    acao VARCHAR(20) DEFAULT 'kick',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create users table (for tracking warned users)
CREATE TABLE IF NOT EXISTS user_warnings (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL REFERENCES guilds(guild_id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    warning_count INT DEFAULT 0,
    warned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(guild_id, user_id)
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_user_warnings_guild_user ON user_warnings(guild_id, user_id);
CREATE INDEX IF NOT EXISTS idx_user_warnings_guild ON user_warnings(guild_id);

-- Create moderation logs table
CREATE TABLE IF NOT EXISTS moderation_logs (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL REFERENCES guilds(guild_id) ON DELETE CASCADE,
    moderator_id BIGINT,
    user_id BIGINT NOT NULL,
    action VARCHAR(20) NOT NULL,
    reason VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for moderation logs
CREATE INDEX IF NOT EXISTS idx_moderation_logs_guild ON moderation_logs(guild_id);
CREATE INDEX IF NOT EXISTS idx_moderation_logs_user ON moderation_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_moderation_logs_created ON moderation_logs(created_at);
