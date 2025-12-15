from odoo import api, fields, models, _


class DinoBankTransaction(models.Model):
    _name = 'dino.bank.transaction'
    _description = _('Bank Transaction Buffer')

    name = fields.Char(string=_('Reference'))
    bank_txn_id = fields.Char(string=_('Bank Transaction ID'), index=True)
    date = fields.Date(string=_('Date'))
    amount = fields.Monetary(string=_('Amount'))
    currency_id = fields.Many2one('res.currency', string=_('Currency'))
    description = fields.Text(string=_('Description'))
#    journal_id = fields.Many2one('account.journal', string=_('Journal'))
    state = fields.Selection([('draft', 'Draft'), ('processed', 'Processed')], default='draft')

    @api.model
    def create_from_bank(self, vals):
        # helper to create record from external payload
        return self.create(vals)