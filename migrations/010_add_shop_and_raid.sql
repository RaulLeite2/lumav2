-- Migration 010: economy shop and intelligent anti-raid
-- Created: 2026-03-21

CREATE TABLE IF NOT EXISTS shop_items (
    item_key VARCHAR(64) PRIMARY KEY,
    item_name VARCHAR(120) NOT NULL,
    item_description TEXT NOT NULL,
    price INT NOT NULL CHECK (price >= 0),
    category VARCHAR(32) NOT NULL DEFAULT 'utility',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_inventory (
    user_id BIGINT NOT NULL,
    item_key VARCHAR(64) NOT NULL REFERENCES shop_items(item_key) ON DELETE CASCADE,
    quantity INT NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, item_key)
);

CREATE INDEX IF NOT EXISTS idx_user_inventory_user_id ON user_inventory(user_id);

CREATE TABLE IF NOT EXISTS user_item_effects (
    user_id BIGINT NOT NULL,
    effect_key VARCHAR(64) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, effect_key)
);

CREATE INDEX IF NOT EXISTS idx_user_item_effects_expires_at ON user_item_effects(expires_at);

CREATE TABLE IF NOT EXISTS user_profile_badges (
    user_id BIGINT NOT NULL,
    badge_key VARCHAR(64) NOT NULL,
    unlocked_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, badge_key)
);

CREATE INDEX IF NOT EXISTS idx_user_profile_badges_user_id ON user_profile_badges(user_id);

INSERT INTO shop_items (item_key, item_name, item_description, price, category, is_active)
VALUES
    ('xp_boost_1h', 'XP Boost 1h', 'Active your leveling journey: grants a personal XP bonus token for 1 hour.', 350, 'boost', TRUE),
    ('lucky_crate', 'Lucky Crate', 'A crate with random economy surprises (future expansion item).', 500, 'crate', TRUE),
    ('profile_badge', 'Profile Badge', 'Collectible profile badge to show your support in future profile cards.', 750, 'cosmetic', TRUE)
ON CONFLICT (item_key) DO NOTHING;

CREATE TABLE IF NOT EXISTS guild_raid_settings (
    guild_id BIGINT PRIMARY KEY,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    join_threshold INT NOT NULL DEFAULT 7 CHECK (join_threshold >= 3),
    window_seconds INT NOT NULL DEFAULT 15 CHECK (window_seconds >= 5),
    min_account_age_days INT NOT NULL DEFAULT 7 CHECK (min_account_age_days >= 0),
    auto_lock_minutes INT NOT NULL DEFAULT 10 CHECK (auto_lock_minutes >= 1),
    action VARCHAR(16) NOT NULL DEFAULT 'kick',
    notify_channel_id BIGINT,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_guild_raid_action CHECK (action IN ('kick', 'ban'))
);

CREATE TABLE IF NOT EXISTS raid_incidents (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    detected_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    window_seconds INT NOT NULL,
    join_count INT NOT NULL,
    action VARCHAR(16) NOT NULL,
    lock_until TIMESTAMP NOT NULL,
    resolved_at TIMESTAMP,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_raid_incidents_guild_detected ON raid_incidents(guild_id, detected_at);
