-- Migration 016: add drops wallet and shop currency split
-- Created: 2026-06-14

ALTER TABLE economy
    ADD COLUMN IF NOT EXISTS drop_balance INT NOT NULL DEFAULT 0;

ALTER TABLE shop_items
    ADD COLUMN IF NOT EXISTS currency_type VARCHAR(16) NOT NULL DEFAULT 'lumicoins';

UPDATE shop_items
SET currency_type = 'lumicoins'
WHERE currency_type IS NULL OR TRIM(currency_type) = '';

CREATE INDEX IF NOT EXISTS idx_shop_items_currency_type ON shop_items(currency_type);

INSERT INTO shop_items (item_key, item_name, item_description, price, category, currency_type, is_active)
VALUES
    ('drop_focus_30m', 'Drop Focus 30m', 'Boost your next drop streak with a lightweight focus enhancer.', 120, 'drop_boost', 'drops', TRUE),
    ('drop_radar', 'Drop Radar', 'Improves your visibility on upcoming wave windows.', 240, 'drop_utility', 'drops', TRUE),
    ('drop_badge_neon', 'Neon Drop Badge', 'Exclusive badge style unlocked through drop currency.', 360, 'drop_cosmetic', 'drops', TRUE)
ON CONFLICT (item_key) DO UPDATE
SET currency_type = EXCLUDED.currency_type,
    category = EXCLUDED.category,
    is_active = EXCLUDED.is_active,
    updated_at = CURRENT_TIMESTAMP;
