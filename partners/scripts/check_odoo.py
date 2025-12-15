from odoo import api, registry, SUPERUSER_ID

db='dino24_dev'
with registry(db).cursor() as cr:
    env=api.Environment(cr, SUPERUSER_ID, {})
    mod=env['ir.module.module'].search([('name','=','dino_erp_vendors')], limit=1)
    print('MODULE:', mod.name if mod else 'NOT FOUND', 'state=' + (mod.state if mod else 'n/a'))
    model = env['dino.vendor'] if 'dino.vendor' in env else None
    if model:
        print('\nMODEL FIELDS:')
        for f in sorted(model._fields.keys()):
            print(f)
    else:
        print('MODEL dino.vendor not in env')
    cr.execute("""SELECT column_name FROM information_schema.columns WHERE table_name='dino_vendor' ORDER BY column_name;""")
    rows = cr.fetchall()
    print('\nDB COLUMNS:')
    if rows:
        for r in rows:
            print(r[0])
    else:
        print('No columns returned')
