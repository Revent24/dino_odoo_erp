-- Remove obsolete API and cron fields from dino_bank
-- These fields moved to dino.api.endpoint model

ALTER TABLE dino_bank DROP COLUMN IF EXISTS api_client_id;
ALTER TABLE dino_bank DROP COLUMN IF EXISTS api_key;
ALTER TABLE dino_bank DROP COLUMN IF EXISTS start_sync_date;
ALTER TABLE dino_bank DROP COLUMN IF EXISTS last_sync_date;
ALTER TABLE dino_bank DROP COLUMN IF EXISTS cron_enable;
ALTER TABLE dino_bank DROP COLUMN IF EXISTS cron_overwrite_existing_rates;
ALTER TABLE dino_bank DROP COLUMN IF EXISTS cron_interval_number;
ALTER TABLE dino_bank DROP COLUMN IF EXISTS cron_interval_type;
ALTER TABLE dino_bank DROP COLUMN IF EXISTS cron_nextcall;
ALTER TABLE dino_bank DROP COLUMN IF EXISTS cron_numbercall;
ALTER TABLE dino_bank DROP COLUMN IF EXISTS cron_time_of_day_hours;
