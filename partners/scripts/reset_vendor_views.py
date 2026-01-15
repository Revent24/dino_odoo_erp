#
#  -*- File: partners/scripts/reset_vendor_views.py -*-
#
#!/usr/bin/env python3
"""
Backup and delete ir.ui.view records for model 'dino.vendor'.
Writes backup to /tmp/dino_vendor_views_backup.json
"""
import json
from odoo import api, registry, SUPERUSER_ID

DB = 'dino24_dev'
OUT = '/tmp/dino_vendor_views_backup.json'

with registry(DB).cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    View = env['ir.ui.view']
    views = View.search([('model', '=', 'dino.vendor')])
    data = []
    for v in views:
        data.append({
            'id': v.id,
            'name': v.name,
            'module': v.module,
            'priority': v.priority,
            'type': v.type,
            'arch': v.arch,
        })
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print('Backed up %d views to %s' % (len(data), OUT))
    # now delete
    if views:
        views.unlink()
        print('Deleted %d views from DB' % len(data))
    else:
        print('No views to delete')
    cr.commit()
# End of file partners/scripts/reset_vendor_views.py
