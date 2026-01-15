#
#  -*- File: scripts/add_partner_fields.py -*-
#
#!/usr/bin/env python3
"""
Скрипт для добавления полей в таблицы dino_partner и dino_bank_transaction
Запускать через: odoo-bin shell -d dino24 -c odoo19.conf < add_partner_fields.py
"""

def add_fields():
    """Добавляет недостающие поля в таблицы"""
    cr = env.cr
    
    # Добавляем поля в dino_partner
    partner_fields = [
        ('iban', 'VARCHAR'),
        ('bank_name', 'VARCHAR'),
        ('bank_city', 'VARCHAR'),
    ]
    
    for field_name, field_type in partner_fields:
        try:
            cr.execute(f"""
                ALTER TABLE dino_partner 
                ADD COLUMN IF NOT EXISTS {field_name} {field_type}
            """)
            print(f"✓ Поле dino_partner.{field_name} добавлено")
        except Exception as e:
            print(f"✗ Ошибка при добавлении dino_partner.{field_name}: {e}")
    
    # Добавляем поле partner_id в dino_bank_transaction
    try:
        cr.execute("""
            ALTER TABLE dino_bank_transaction 
            ADD COLUMN IF NOT EXISTS partner_id INTEGER
        """)
        print("✓ Поле dino_bank_transaction.partner_id добавлено")
        
        # Создаём индекс
        cr.execute("""
            CREATE INDEX IF NOT EXISTS dino_bank_transaction_partner_id_index 
            ON dino_bank_transaction(partner_id)
        """)
        print("✓ Индекс dino_bank_transaction_partner_id_index создан")
        
        # Добавляем foreign key constraint
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
        print("✓ Foreign key constraint добавлен")
        
    except Exception as e:
        print(f"✗ Ошибка при добавлении partner_id: {e}")
    
    # Commit изменений
    cr.commit()
    print("\n✅ Все изменения применены успешно!")

# Выполняем
add_fields()
# End of file scripts/add_partner_fields.py
