-- Migration 015: add auto role assignment for entry/exit flow
-- Created: 2026-04-10

ALTER TABLE guild_entry_exit_embeds
ADD COLUMN IF NOT EXISTS auto_role_id BIGINT;
