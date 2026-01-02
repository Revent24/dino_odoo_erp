-- Migration: Add partner link and bank fields to partners and transactions
-- Author: System
-- Date: 2026-01-02

-- Add new fields to dino_partner
ALTER TABLE dino_partner 
ADD COLUMN IF NOT EXISTS iban VARCHAR,
ADD COLUMN IF NOT EXISTS bank_name VARCHAR,
ADD COLUMN IF NOT EXISTS bank_city VARCHAR;

-- Add partner_id to dino_bank_transaction
ALTER TABLE dino_bank_transaction
ADD COLUMN IF NOT EXISTS partner_id INTEGER REFERENCES dino_partner(id) ON DELETE SET NULL;

-- Create index on partner_id for performance
CREATE INDEX IF NOT EXISTS dino_bank_transaction_partner_id_index 
ON dino_bank_transaction(partner_id);

-- Add comments
COMMENT ON COLUMN dino_partner.iban IS 'Bank account number (IBAN)';
COMMENT ON COLUMN dino_partner.bank_name IS 'Name of the bank';
COMMENT ON COLUMN dino_partner.bank_city IS 'City of the bank';
COMMENT ON COLUMN dino_bank_transaction.partner_id IS 'Linked partner (counterparty)';
