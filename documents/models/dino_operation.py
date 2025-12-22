from odoo import fields, models


class DinoOperation(models.Model):
    _name = 'dino.operation'
    _description = 'Operation'
    _rec_name = 'name'

    name = fields.Char(string='Name', required=True)
    partner_id = fields.Many2one('dino.partner', string='Partner')
    currency_id = fields.Many2one('res.currency', string='Currency')
    vat_rate = fields.Float(string='VAT Rate (%)', default=20.0)
    note = fields.Text(string='Notes')
