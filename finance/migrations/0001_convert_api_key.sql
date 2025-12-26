-- Migration: convert api_key from varchar to text
-- Run this in the database of your Odoo instance (dino24_dev) as the DB superuser or via psql connection
-- Example:
--   psql -d dino24_dev -c "ALTER TABLE dino_bank ALTER COLUMN api_key TYPE text;"

BEGIN;
ALTER TABLE dino_bank ALTER COLUMN api_key TYPE text;
COMMIT;