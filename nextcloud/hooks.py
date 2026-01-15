#
#  -*- File: nextcloud/hooks.py -*-
#
#
#  -*- File: nextcloud/hooks.py -*-
#

from odoo import api, SUPERUSER_ID


def _ensure_ir_model_data(env, record_id):
    """Ensure ir.model.data has the mapping dino_erp.nextcloud_client_default -> record_id"""
    Imd = env['ir.model.data']
    found = Imd.search([('module', '=', 'dino_erp'), ('name', '=', 'nextcloud_client_default')], limit=1)
    if found:
        if found.res_id != record_id or found.model != 'nextcloud.client':
            found.write({'res_id': record_id, 'model': 'nextcloud.client'})
    else:
        Imd.create({'module': 'dino_erp', 'name': 'nextcloud_client_default', 'model': 'nextcloud.client', 'res_id': record_id, 'noupdate': True})


def post_init_hook(cr, registry):
    """Ensure exactly one Nextcloud client configuration exists.

    - If none exist: create a default record and register its external id.
    - If multiple exist: keep the oldest (smallest ID), remove the rest, and register the keeper.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    Client = env['nextcloud.client']
    records = Client.search([], order='id')
    if not records:
        rec = Client.create({
            'name': 'Default Nextcloud Connection',
            'url': 'http://localhost:8080',
            'username': 'admin',
            'password': 'admin',
            'state': 'draft',
        })
        _ensure_ir_model_data(env, rec.id)
    elif len(records) > 1:
        keep = records[0]
        (records - keep).unlink()
        _ensure_ir_model_data(env, keep.id)
    else:
        # Single existing record — ensure mapping is present
        _ensure_ir_model_data(env, records[0].id)

# End of file nextcloud/hooks.py
# End of file nextcloud/hooks.py
