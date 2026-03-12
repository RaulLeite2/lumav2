-- Migration 004: add guild language setting
-- Created: 2026-03-12

ALTER TABLE guilds
ADD COLUMN IF NOT EXISTS language_code VARCHAR(5) DEFAULT 'pt';

UPDATE guilds
SET language_code = 'pt'
WHERE language_code IS NULL;
