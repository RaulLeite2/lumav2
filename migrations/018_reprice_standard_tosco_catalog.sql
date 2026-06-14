-- Migration 018: reprice standard tosco catalog by tier
-- Created: 2026-06-14

-- Tier 1: common junk
UPDATE shop_items
SET price = 100,
    updated_at = CURRENT_TIMESTAMP
WHERE item_key ~ '^std_0[0-9][0-9]$'
   OR item_key = 'std_100';

-- Tier 2: uncommon junk
UPDATE shop_items
SET price = 250,
    updated_at = CURRENT_TIMESTAMP
WHERE item_key ~ '^std_1[0-5][0-9]$'
   OR item_key = 'std_160';

-- Tier 3: cursed/late catalog
UPDATE shop_items
SET price = 500,
    updated_at = CURRENT_TIMESTAMP
WHERE item_key ~ '^std_1[6-9][0-9]$'
   OR item_key = 'std_200';
