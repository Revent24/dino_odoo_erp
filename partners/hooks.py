"""Hooks for partners module"""
import logging

_logger = logging.getLogger(__name__)


def migrate_tax_systems(cr, registry):
    # No-op: tax systems removed
    return True


def post_init_hook(cr, registry):
    """
    Post-initialization hook to add missing fields to database
    """
    _logger.info("Running post_init_hook for partners module")
    
    # Add fields to dino_partner
    cr.execute("""
        ALTER TABLE dino_partner 
        ADD COLUMN IF NOT EXISTS iban VARCHAR;
    """)
    _logger.info("Added iban field to dino_partner")
    
    cr.execute("""
        ALTER TABLE dino_partner 
        ADD COLUMN IF NOT EXISTS bank_name VARCHAR;
    """)
    _logger.info("Added bank_name field to dino_partner")
    
    cr.execute("""
        ALTER TABLE dino_partner 
        ADD COLUMN IF NOT EXISTS bank_city VARCHAR;
    """)
    _logger.info("Added bank_city field to dino_partner")
    
    # Add partner_id to dino_bank_transaction
    cr.execute("""
        ALTER TABLE dino_bank_transaction 
        ADD COLUMN IF NOT EXISTS partner_id INTEGER;
    """)
    _logger.info("Added partner_id field to dino_bank_transaction")
    
    # Create index
    cr.execute("""
        CREATE INDEX IF NOT EXISTS dino_bank_transaction_partner_id_index 
        ON dino_bank_transaction(partner_id);
    """)
    _logger.info("Created index on partner_id")
    
    # Add foreign key constraint
    cr.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints 
                WHERE constraint_name = 'dino_bank_transaction_partner_id_fkey'
            ) THEN
                ALTER TABLE dino_bank_transaction 
                ADD CONSTRAINT dino_bank_transaction_partner_id_fkey 
                FOREIGN KEY (partner_id) REFERENCES dino_partner(id) ON DELETE SET NULL;
            END IF;
        END $$;
    """)
    _logger.info("Added foreign key constraint")
    
    _logger.info("✅ Post-init hook completed successfully")
