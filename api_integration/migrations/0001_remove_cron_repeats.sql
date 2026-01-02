-- Remove cron_repeats column as all crons are infinite
ALTER TABLE dino_api_endpoint 
DROP COLUMN IF EXISTS cron_repeats;

-- Remove cron_weekdays column (replaced with individual boolean fields)
ALTER TABLE dino_api_endpoint 
DROP COLUMN IF EXISTS cron_weekdays;
