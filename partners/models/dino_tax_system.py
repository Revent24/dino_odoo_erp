from odoo import models, fields, _

class DinoTaxSystem(models.Model):
    _name = 'dino.tax.system'
    _description = 'Tax System'

    name = fields.Char(string='Name', required=True, translate=True)
    vat_rate = fields.Float(string='VAT Rate (%)')
