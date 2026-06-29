-- Migration 019: extra indexes for hot queries and growth
-- Created: 2026-06-29

CREATE INDEX IF NOT EXISTS idx_ai_usage_events_guild_user_time
ON ai_usage_events(guild_id, user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_command_usage_stats_guild_used
ON command_usage_stats(guild_id, used_count DESC);

CREATE INDEX IF NOT EXISTS idx_metric_counters_guild_metric
ON metric_counters(guild_id, metric_name);

CREATE INDEX IF NOT EXISTS idx_audit_logs_guild_action_created
ON audit_logs(guild_id, action_name, created_at DESC);
