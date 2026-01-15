#
#  -*- File: scripts/run_import_nbu.py -*-
#
#!/usr/bin/env python3
import sys
import odoo
from odoo.tools import config

# Minimal config parse to set DB
config.parse_config(['odoo', '--db-filter=dino24_dev'])

# Preload registry
odoo.service.server.preload_registries()

DB = 'dino24_dev'
with odoo.registry(DB).cursor() as cr:
    env = odoo.api.Environment(cr, 1, {})
    bank = env['dino.bank'].search([('mfo', '=', '300001')], limit=1)
    if not bank:
        print('NBU bank (MFO=300001) not found')
        sys.exit(1)
    print('NBU import for bank MFO 300001')
    res = bank.import_nbu_rates()
    print('Import result:', res)
    # optionally, print some sample skipped details if available
    # this method currently returns counts only

print('Done')# End of file scripts/run_import_nbu.py
