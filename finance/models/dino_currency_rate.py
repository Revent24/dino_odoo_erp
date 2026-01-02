from odoo import api, fields, models, _


class DinoCurrencyRate(models.Model):
    _name = 'dino.currency.rate'
    _description = _('Currency Rate')
    _order = 'date desc'

    name = fields.Char(string=_('Name'))
    currency_id = fields.Many2one('res.currency', string=_('Currency'), required=True, index=True)
    rate = fields.Float(string=_('Rate'), digits=(12, 6), required=True)  # Основная ставка курса
    date = fields.Date(string=_('Rate Date'), required=True, index=True)
    source = fields.Selection([('nbu', 'NBU'), ('privat', 'PrivatBank'), ('mono', 'MonoBank'), ('commercial', 'Commercial')], string=_('Source'), default='commercial', index=True)
    rate_type = fields.Selection([('official', 'Official'), ('buy', 'Buy'), ('sell', 'Sell')], string=_('Rate Type'), default='official', index=True)

    @api.constrains('currency_id', 'date', 'source', 'rate_type')
    def _check_unique_rate(self):
        for record in self:
            existing = self.search([
                ('currency_id', '=', record.currency_id.id),
                ('date', '=', record.date),
                ('source', '=', record.source),
                ('rate_type', '=', record.rate_type),
                ('id', '!=', record.id)
            ])
            if existing:
                raise models.ValidationError('Rate for this currency/date/source/type already exists')