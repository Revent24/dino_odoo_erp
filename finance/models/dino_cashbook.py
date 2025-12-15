from odoo import api, fields, models, _


class DinoCashbook(models.Model):
    _name = 'dino.cashbook'
    _description = _('Cashbook Entry')

    date = fields.Date(string=_('Date'), required=True, default=fields.Date.today)
    purpose = fields.Char(string=_('Purpose'), required=True)
    amount = fields.Monetary(string=_('Amount'), required=True)
    currency_id = fields.Many2one('res.currency', string=_('Currency'), default=lambda self: self.env.ref('base.UAH', raise_if_not_found=False) or self.env.company.currency_id)