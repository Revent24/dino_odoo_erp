#
#  -*- File: partners/scripts/migrate_tag_roles.py -*-
#
#!/usr/bin/env python3
"""
Простая утилита для проставления поля `role` у существующих записей dino.partner.tag
по имени тега (поддерживает рус/англ). Запустить из-под виртуального окружения Odoo.

Примеры использования:
  cd ~/OdooApps/odoo19
  source ~/OdooApps/odoo19-venv/bin/activate
  python3 ../odoo_projects/dino24_addons/dino_erp/partners/scripts/migrate_tag_roles.py

"""
import odoo
from odoo import api

odoo.tools.config.parse_config(['-d', 'dino24_dev', '--addons-path=addons,../odoo_projects/dino24_addons'])
with api.Environment.manage():
    db = 'dino24_dev'
    registry = odoo.registry(db)
    with registry.cursor() as cr:
        env = api.Environment(cr, 1, {})
        Tag = env['dino.partner.tag']
        mapping = {
            'Поставщик': 'vendor',
            'Покупатель': 'customer',
            'Vendor': 'vendor',
            'Customer': 'customer',
        }
        updated = []
        for name, role in mapping.items():
            tags = Tag.search([('name', '=', name)])
            if tags:
                tags.write({'role': role})
                updated.append((name, tags.ids))

        print('Updated tags:', updated)
# End of file partners/scripts/migrate_tag_roles.py
