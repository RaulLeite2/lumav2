-- Migration 008: customizable welcome/leave embed settings
-- Created: 2026-03-15

CREATE TABLE IF NOT EXISTS guild_entry_exit_embeds (
    guild_id BIGINT PRIMARY KEY REFERENCES guilds(guild_id) ON DELETE CASCADE,
    welcome_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    welcome_channel_id BIGINT,
    welcome_title VARCHAR(256),
    welcome_description TEXT,
    welcome_color VARCHAR(16),
    leave_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    leave_channel_id BIGINT,
    leave_title VARCHAR(256),
    leave_description TEXT,
    leave_color VARCHAR(16),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
