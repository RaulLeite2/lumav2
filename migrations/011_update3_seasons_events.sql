-- Migration 011: update 3 foundations (seasons, economy events, anti-raid v2)
-- Created: 2026-03-21

CREATE TABLE IF NOT EXISTS economy_seasons (
    season_key VARCHAR(16) PRIMARY KEY,
    starts_at TIMESTAMP NOT NULL,
    ends_at TIMESTAMP NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS economy_transactions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    guild_id BIGINT,
    delta INT NOT NULL,
    balance_after INT,
    tx_type VARCHAR(32) NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_economy_transactions_user_time ON economy_transactions(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_economy_transactions_type_time ON economy_transactions(tx_type, created_at);
CREATE INDEX IF NOT EXISTS idx_economy_transactions_guild_time ON economy_transactions(guild_id, created_at);

ALTER TABLE guild_raid_settings
    ADD COLUMN IF NOT EXISTS mode VARCHAR(16) NOT NULL DEFAULT 'lockdown';

ALTER TABLE guild_raid_settings
    ADD COLUMN IF NOT EXISTS recovery_cooldown_minutes INT NOT NULL DEFAULT 10;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_guild_raid_mode'
    ) THEN
        ALTER TABLE guild_raid_settings
            ADD CONSTRAINT chk_guild_raid_mode CHECK (mode IN ('preventive', 'lockdown', 'recovery'));
    END IF;
END $$;
