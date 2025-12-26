from odoo import api, fields, models, _


class DinoCurrencyRate(models.Model):
    _name = 'dino.currency.rate'
    _description = _('Currency Rate')
    _order = 'date desc'

    name = fields.Char(string=_('Name'))
    currency_id = fields.Many2one('res.currency', string=_('Currency'), required=True, index=True)
    rate = fields.Float(string=_('Rate'), digits=(12, 6))
    date = fields.Date(string=_('Rate Date'), required=True, index=True)
    source = fields.Selection([('nbu', 'NBU'), ('commercial', 'Commercial')], string=_('Source'), default='commercial', index=True)

    @api.constrains('currency_id', 'date', 'source')
    def _check_unique_rate(self):
        for record in self:
            existing = self.search([
                ('currency_id', '=', record.currency_id.id),
                ('date', '=', record.date),
                ('source', '=', record.source),
                ('id', '!=', record.id)
            ])
            if existing:
                raise models.ValidationError('Rate for this currency/date/source already exists')