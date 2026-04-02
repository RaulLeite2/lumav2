-- Migration 013: weekly missions for engagement loop
-- Created: 2026-04-02

CREATE TABLE IF NOT EXISTS user_weekly_missions (
    user_id BIGINT PRIMARY KEY,
    week_key VARCHAR(16) NOT NULL,
    mission_key VARCHAR(64) NOT NULL,
    target_count INT NOT NULL,
    progress_count INT NOT NULL DEFAULT 0,
    reward_coins INT NOT NULL,
    assigned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    claimed_at TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_user_weekly_missions_week_key ON user_weekly_missions(week_key);
CREATE INDEX IF NOT EXISTS idx_user_weekly_missions_claimed_at ON user_weekly_missions(claimed_at);
CREATE INDEX IF NOT EXISTS idx_user_weekly_missions_assigned_at ON user_weekly_missions(assigned_at);
