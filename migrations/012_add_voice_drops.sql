-- Migration 012: add voice drops configuration and daily aggregates
-- Created: 2026-03-21

ALTER TABLE guilds
    ADD COLUMN IF NOT EXISTS voice_drops_enabled BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE guilds
    ADD COLUMN IF NOT EXISTS voice_drops_channel_id BIGINT;

ALTER TABLE guilds
    ADD COLUMN IF NOT EXISTS voice_drops_interval_minutes INT NOT NULL DEFAULT 15;

ALTER TABLE guilds
    ADD COLUMN IF NOT EXISTS voice_drops_reminder_minutes INT NOT NULL DEFAULT 15;

ALTER TABLE guilds
    ADD COLUMN IF NOT EXISTS voice_drops_min_members INT NOT NULL DEFAULT 2;

ALTER TABLE guilds
    ADD COLUMN IF NOT EXISTS voice_drops_min_amount INT NOT NULL DEFAULT 20;

ALTER TABLE guilds
    ADD COLUMN IF NOT EXISTS voice_drops_max_amount INT NOT NULL DEFAULT 45;

ALTER TABLE guilds
    ADD COLUMN IF NOT EXISTS voice_drops_daily_cap INT NOT NULL DEFAULT 500;

ALTER TABLE guilds
    ADD COLUMN IF NOT EXISTS voice_drops_party_bonus_percent INT NOT NULL DEFAULT 10;

CREATE TABLE IF NOT EXISTS user_voice_drops_daily (
    guild_id BIGINT NOT NULL REFERENCES guilds(guild_id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    day_key DATE NOT NULL,
    total_amount INT NOT NULL DEFAULT 0,
    total_intervals INT NOT NULL DEFAULT 0,
    last_drop_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (guild_id, user_id, day_key)
);

CREATE INDEX IF NOT EXISTS idx_user_voice_drops_daily_guild_day ON user_voice_drops_daily(guild_id, day_key);
CREATE INDEX IF NOT EXISTS idx_user_voice_drops_daily_user_day ON user_voice_drops_daily(user_id, day_key);