-- Migration 006: leveling system base schema

ALTER TABLE guilds
ADD COLUMN IF NOT EXISTS leveling_enabled BOOLEAN DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS leveling_settings (
    guild_id BIGINT PRIMARY KEY,
    xp_multiplier NUMERIC(5,2) DEFAULT 1.00,
    cooldown_seconds INT DEFAULT 45,
    level_up_message TEXT DEFAULT 'Congratulations {user}, you have reached level {level}!',
    FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_levels (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL REFERENCES guilds(guild_id) ON DELETE CASCADE,
    xp BIGINT NOT NULL DEFAULT 0,
    messages_count BIGINT NOT NULL DEFAULT 0,
    last_message_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, guild_id)
);

CREATE INDEX IF NOT EXISTS idx_user_levels_guild_xp ON user_levels(guild_id, xp DESC);
CREATE INDEX IF NOT EXISTS idx_user_levels_user_guild ON user_levels(user_id, guild_id);

INSERT INTO leveling_settings (guild_id)
SELECT guild_id FROM guilds
ON CONFLICT (guild_id) DO NOTHING;