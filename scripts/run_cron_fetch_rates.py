#
#  -*- File: scripts/run_cron_fetch_rates.py -*-
#
#!/usr/bin/env python3
import odoo
from odoo.tools import config

config.parse_config(['odoo', '--db-filter=dino24_dev'])
# preload registries
odoo.service.server.preload_registries()
DB = 'dino24_dev'
with odoo.registry(DB).cursor() as cr:
    env = odoo.api.Environment(cr, 1, {})
    print('Running cron_fetch_rates...')
    env['dino.bank'].cron_fetch_rates()
    cr.commit()
    print('cron_fetch_rates done')
# End of file scripts/run_cron_fetch_rates.py
