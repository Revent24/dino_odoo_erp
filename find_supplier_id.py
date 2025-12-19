#!/usr/bin/env python3
import odoo
from odoo import api
odoo.tools.config.parse_config(['-d', 'dino24_dev', '--addons-path=addons,../odoo_projects/dino24_addons'])
with api.Environment.manage():
    env = api.Environment(cr=None, uid=1, context={})
    tags = env['dino.partner.tag'].search([('role', '=', 'vendor')])
    print('Vendor tag IDs:', tags.ids if tags else 'Не найдены')