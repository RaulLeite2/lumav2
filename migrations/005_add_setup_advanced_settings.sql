-- Migration 005: advanced setup settings
-- Created: 2026-03-12

ALTER TABLE guilds
ADD COLUMN IF NOT EXISTS ticket_default_category_id BIGINT;

ALTER TABLE guilds
ADD COLUMN IF NOT EXISTS ticket_default_support_role_id BIGINT;

ALTER TABLE guilds
ADD COLUMN IF NOT EXISTS ai_enabled BOOLEAN DEFAULT TRUE;
