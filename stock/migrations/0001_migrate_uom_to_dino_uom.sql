-- Migration: Convert system uom.uom to custom dino.uom
-- This migration creates dino.uom records from existing uom.uom references
-- and updates all related fields

-- Step 1: Create dino.uom records for each unique uom.uom found in specifications
INSERT INTO dino_uom (name, rounding, conversion_factor, active, create_uid, create_date, write_uid, write_date)
SELECT DISTINCT 
    u.name,
    COALESCE(u.rounding, 0.01) as rounding,
    1.0 as conversion_factor,
    true as active,
    1 as create_uid,
    NOW() as create_date,
    1 as write_uid,
    NOW() as write_date
FROM uom_uom u
WHERE u.id IN (
    SELECT DISTINCT uom_id 
    FROM dino_operation_document_specification 
    WHERE uom_id IS NOT NULL
)
AND u.name NOT IN (SELECT name FROM dino_uom)
ON CONFLICT (name) DO NOTHING;

-- Step 2: Update document specifications - map old uom_id to new dino_uom_id
UPDATE dino_operation_document_specification spec
SET dino_uom_id = (
    SELECT d.id 
    FROM dino_uom d
    INNER JOIN uom_uom u ON u.name = d.name
    WHERE u.id = spec.uom_id
    LIMIT 1
)
WHERE spec.uom_id IS NOT NULL
AND spec.dino_uom_id IS NULL;

-- Step 3: Create dino.uom records for partner nomenclature units
INSERT INTO dino_uom (name, rounding, conversion_factor, active, create_uid, create_date, write_uid, write_date)
SELECT DISTINCT 
    u.name,
    COALESCE(u.rounding, 0.01) as rounding,
    1.0 as conversion_factor,
    true as active,
    1 as create_uid,
    NOW() as create_date,
    1 as write_uid,
    NOW() as write_date
FROM uom_uom u
WHERE u.id IN (
    SELECT DISTINCT uom_id 
    FROM dino_partner_nomenclature 
    WHERE uom_id IS NOT NULL
)
AND u.name NOT IN (SELECT name FROM dino_uom)
ON CONFLICT (name) DO NOTHING;

-- Step 4: Update partner nomenclature - map old uom_id to new dino_uom_id and warehouse_uom_id
UPDATE dino_partner_nomenclature pn
SET 
    dino_uom_id = (
        SELECT d.id 
        FROM dino_uom d
        INNER JOIN uom_uom u ON u.name = d.name
        WHERE u.id = pn.uom_id
        LIMIT 1
    ),
    warehouse_uom_id = (
        SELECT d.id 
        FROM dino_uom d
        INNER JOIN uom_uom u ON u.name = d.name
        WHERE u.id = pn.uom_id
        LIMIT 1
    )
WHERE pn.uom_id IS NOT NULL
AND pn.dino_uom_id IS NULL;

-- Step 5: Set default unit for records without any unit
UPDATE dino_operation_document_specification
SET dino_uom_id = (SELECT id FROM dino_uom WHERE name = 'шт' LIMIT 1)
WHERE dino_uom_id IS NULL;

-- Migration complete
