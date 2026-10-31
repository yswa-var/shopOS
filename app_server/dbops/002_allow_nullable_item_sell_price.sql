-- PostgreSQL 14+
-- Migration 002: optional sell price for catalog items
BEGIN;

ALTER TABLE items
    ALTER COLUMN sell_price DROP NOT NULL,
    ALTER COLUMN sell_price DROP DEFAULT;

COMMIT;
