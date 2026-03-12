-- Migration 002: add modmail category support
-- Created: 2026-03-10

ALTER TABLE guilds
ADD COLUMN IF NOT EXISTS modmail_category_id BIGINT;

-- migration.sql
ALTER TABLE guilds ADD COLUMN IF NOT EXISTS smart_antiflood BOOLEAN DEFAULT FALSE;