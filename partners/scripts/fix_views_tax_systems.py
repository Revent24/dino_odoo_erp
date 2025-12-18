#!/usr/bin/env python3
"""Fix DB-stored views that still reference legacy 'tax_system_ids'.

Intended to be run inside Odoo environment (e.g., via odoo shell):

./odoo-bin shell -d <db>
>>> from partners.scripts.fix_views_tax_systems import fix_views
>>> fix_views(env.cr, env.registry)

This will remove occurrences of '<field ... name="tax_system_ids" ...>' blocks from
`ir.ui.view.arch_db` and `ir.ui.view.arch` fields. It creates backups under `/tmp/dino_view_backups`.
"""
from odoo import api, SUPERUSER_ID

def fix_views(cr, registry):
    from odoo.api import Environment
    env = Environment(cr, SUPERUSER_ID, {})
    View = env['ir.ui.view']

    domain = ['|', ('arch_db', 'ilike', 'tax_system_ids'), ('arch', 'ilike', 'tax_system_ids')]
    views = View.search(domain)
    if not views:
        print('No views found referencing "tax_system_ids"')
        return

    print('Found %s views referencing "tax_system_ids"' % len(views))
    import os, re
    backup_dir = '/tmp/dino_view_backups'
    os.makedirs(backup_dir, exist_ok=True)

    # Pattern matches <field name="tax_system_ids" .../> and blocks with nested <list>...</list>
    pattern = re.compile(r'<field[^>]*name=["\']tax_system_ids["\'][\s\S]*?>\s*(?:<list[\s\S]*?</list>\s*)?</field>|<field[^>]*name=["\']tax_system_ids["\'][^>]*/>', re.IGNORECASE)

    for v in views:
        changed = False
        if v.arch_db and 'tax_system_ids' in v.arch_db:
            backup_path = os.path.join(backup_dir, f'{v.id}_arch_db.xml')
            if not os.path.exists(backup_path):
                with open(backup_path, 'w', encoding='utf-8') as fh:
                    fh.write(v.arch_db)
            new_arch_db = pattern.sub('', v.arch_db)
            if new_arch_db != v.arch_db:
                v.write({'arch_db': new_arch_db})
                changed = True
        if v.arch and 'tax_system_ids' in v.arch:
            backup_path = os.path.join(backup_dir, f'{v.id}_arch.xml')
            if not os.path.exists(backup_path):
                with open(backup_path, 'w', encoding='utf-8') as fh:
                    fh.write(v.arch)
            new_arch = pattern.sub('', v.arch)
            if new_arch != v.arch:
                v.write({'arch': new_arch})
                changed = True
        print('Updated view %s (id=%s): changed=%s' % (v.name, v.id, changed))

    print('Done. Please restart Odoo and try updating module if needed.')
