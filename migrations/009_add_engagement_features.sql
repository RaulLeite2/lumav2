-- Migration 009: engagement systems (reputation, daily missions, achievements)
-- Created: 2026-03-21

CREATE TABLE IF NOT EXISTS user_reputation (
    user_id BIGINT PRIMARY KEY,
    rep_points INT NOT NULL DEFAULT 0,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rep_cooldowns (
    giver_id BIGINT PRIMARY KEY,
    last_given_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_daily_missions (
    user_id BIGINT PRIMARY KEY,
    mission_key VARCHAR(64) NOT NULL,
    target_count INT NOT NULL,
    progress_count INT NOT NULL DEFAULT 0,
    reward_coins INT NOT NULL,
    assigned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    claimed_at TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_user_daily_missions_claimed_at ON user_daily_missions(claimed_at);
CREATE INDEX IF NOT EXISTS idx_user_daily_missions_assigned_at ON user_daily_missions(assigned_at);

CREATE TABLE IF NOT EXISTS user_achievements (
    user_id BIGINT NOT NULL,
    achievement_key VARCHAR(64) NOT NULL,
    unlocked_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, achievement_key)
);

CREATE INDEX IF NOT EXISTS idx_user_achievements_user_id ON user_achievements(user_id);
