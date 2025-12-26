This folder contains manual migration scripts for the finance module.

0001_convert_api_key.sql
- Alters `dino_bank.api_key` column type from varchar to text to allow arbitrarily long tokens.

Usage (example):
  psql -d dino24_dev -c "ALTER TABLE dino_bank ALTER COLUMN api_key TYPE text;"

Run these scripts manually during module upgrade or DB maintenance. Ensure you have a DB backup before running migrations.