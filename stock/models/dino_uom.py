from odoo import fields, models, _

class DinoUoM(models.Model):
    _name = 'dino.uom'
    _description = 'Dino Unit of Measure'

    name = fields.Char(string=_('Name'), required=True)
    rounding = fields.Float(string=_('Rounding'), default=0.01)
    active = fields.Boolean(default=True)
