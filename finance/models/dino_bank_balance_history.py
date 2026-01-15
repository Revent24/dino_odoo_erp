#
#  -*- File: finance/models/dino_bank_balance_history.py -*-
#
# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class DinoBankBalanceHistory(models.Model):
    _name = 'dino.bank.balance.history'
    _description = _('Bank Balance History')
    _order = 'date desc, bank_account_id'
    _rec_name = 'display_name'

    # Core Fields
    date = fields.Date(string=_('Date'), required=True, index=True)
    bank_account_id = fields.Many2one('dino.bank.account', string=_('Bank Account'), required=True, ondelete='cascade', index=True)
    currency_id = fields.Many2one(related='bank_account_id.currency_id', store=True, readonly=True)
    
    # Balance Fields
    balance_start = fields.Monetary(
        string=_('Opening Balance'),
        currency_field='currency_id',
        help=_("Balance at the beginning of the day")
    )
    balance_end = fields.Monetary(
        string=_('Closing Balance'),
        currency_field='currency_id',
        help=_("Balance at the end of the day")
    )
    turnover_debit = fields.Monetary(
        string=_('Turnover Debit'),
        currency_field='currency_id',
        help=_("Total incoming transactions (receipts)")
    )
    turnover_credit = fields.Monetary(
        string=_('Turnover Credit'),
        currency_field='currency_id',
        help=_("Total outgoing transactions (payments)")
    )
    
    # Technical Fields
    is_final = fields.Boolean(
        string=_('Final Balance'),
        default=False,
        help=_("Indicates if this is a final balance for a closed operational day")
    )
    last_movement_date = fields.Date(
        string=_('Last Movement Date'),
        help=_("Date of last transaction on this account")
    )
    external_id = fields.Char(
        string=_('External ID'),
        help=_("Unique identifier from bank's API")
    )
    import_date = fields.Datetime(
        string=_('Import Date'),
        default=fields.Datetime.now,
        readonly=True
    )
    
    # Computed Fields
    display_name = fields.Char(string=_('Display Name'), compute='_compute_display_name', store=True)
    balance_change = fields.Monetary(
        string=_('Balance Change'),
        compute='_compute_balance_change',
        currency_field='currency_id',
        store=True
    )
    
    _sql_constraints = [
        ('date_account_uniq', 'unique(date, bank_account_id)', 'Balance for this date and account already exists!')
    ]

    @api.depends('bank_account_id', 'date')
    def _compute_display_name(self):
        for record in self:
            if record.bank_account_id and record.date:
                record.display_name = f"{record.bank_account_id.name} - {record.date}"
            else:
                record.display_name = _('Balance History')

    @api.depends('balance_start', 'balance_end')
    def _compute_balance_change(self):
        for record in self:
            record.balance_change = record.balance_end - record.balance_start
# End of file finance/models/dino_bank_balance_history.py
