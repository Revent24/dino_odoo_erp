-- Миграция: заполнение document_type_id для существующих документов
-- Устанавливаем дефолтный тип "Інше" для всех документов без типа

-- Обновляем все документы без типа
UPDATE dino_operation_document 
SET document_type_id = (
    SELECT id 
    FROM dino_document_type 
    WHERE code = 'other' 
    LIMIT 1
)
WHERE document_type_id IS NULL;

-- Если записи типа "other" нет, создаем её и обновляем документы
DO $$
DECLARE
    other_type_id INTEGER;
BEGIN
    -- Проверяем, есть ли тип "other"
    SELECT id INTO other_type_id FROM dino_document_type WHERE code = 'other' LIMIT 1;
    
    -- Если нет, создаем
    IF other_type_id IS NULL THEN
        INSERT INTO dino_document_type (name, code, sequence, active, create_uid, create_date, write_uid, write_date)
        VALUES ('Інше', 'other', 100, true, 1, NOW(), 1, NOW())
        RETURNING id INTO other_type_id;
        
        -- Обновляем документы
        UPDATE dino_operation_document 
        SET document_type_id = other_type_id 
        WHERE document_type_id IS NULL;
    END IF;
END $$;
