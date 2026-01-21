def pre_init_hook(cr):
    # Rename old column before model init
    cr.execute("ALTER TABLE dino_project RENAME COLUMN project_type TO project_type_old")