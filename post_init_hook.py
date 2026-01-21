def post_init_hook(cr):
    # Update new project_type column from old data and drop old column
    cr.execute("""
        UPDATE dino_project
        SET project_type = dpt.id
        FROM dino_project_type dpt
        WHERE dpt.code = dino_project.project_type_old
    """)
    cr.execute("ALTER TABLE dino_project DROP COLUMN project_type_old")