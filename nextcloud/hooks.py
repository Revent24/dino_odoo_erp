from odoo import api, SUPERUSER_ID

def post_init_hook(cr, registry):
    """Ensure exactly one Nextcloud client configuration exists.

    - If none exist: create a default record.
    - If multiple exist: keep the oldest (smallest ID) and remove the rest.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    Client = env['nextcloud.client']
    records = Client.search([], order='id')
    if not records:
        Client.create({
            'name': 'Default Nextcloud Connection',
            'url': 'http://localhost:8080',
            'username': 'admin',
            'password': 'admin',
            'state': 'draft',
        })
    elif len(records) > 1:
        keep = records[0]
        (records - keep).unlink()
